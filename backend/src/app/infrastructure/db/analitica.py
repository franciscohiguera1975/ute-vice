"""Consultas agregadas para el tablero.

Todo se resuelve en la base con agregaciones. La alternativa —traer las filas y
contar en Python— seria correcta y desastrosa: el tablero pasaria de milisegundos
a decenas de segundos en cuanto el padron creciera.
"""

from __future__ import annotations

from datetime import date, datetime, time
from typing import Any

from sqlalchemy import Integer, case, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import EstadoConsulta, EstadoTitulo, NivelTitulo
from app.domain.ports.analitica import (
    ConteoEtiquetado,
    PuntoSerie,
    ResumenCobertura,
    ResumenConsultas,
    ResumenTitulos,
)
from app.infrastructure.db.modelos import ConsultaLogModel, PersonaModel, TituloModel


def _porcentajes(conteos: list[tuple[str, int]]) -> list[ConteoEtiquetado]:
    total = sum(v for _, v in conteos) or 1
    return [
        ConteoEtiquetado(
            etiqueta=etiqueta or "(sin especificar)",
            valor=valor,
            porcentaje=round(valor / total * 100, 2),
        )
        for etiqueta, valor in conteos
    ]


def _inicio_del_dia(dia: date) -> datetime:
    from datetime import UTC

    return datetime.combine(dia, time.min, tzinfo=UTC)


def _fin_del_dia(dia: date) -> datetime:
    from datetime import UTC

    return datetime.combine(dia, time.max, tzinfo=UTC)


class RepositorioAnaliticaSQL:
    """Implementacion del puerto `RepositorioAnalitica`."""

    def __init__(self, sesion: AsyncSession) -> None:
        self._s = sesion

    async def resumen_cobertura(self, *, desde: date, hasta: date) -> ResumenCobertura:
        # Una sola pasada sobre `personas` con agregados condicionales: mas
        # rapido y coherente que seis conteos independientes.
        fila = (
            await self._s.execute(
                select(
                    func.count().label("total"),
                    func.sum(cast(PersonaModel.activo, Integer)).label("activas"),
                    func.sum(case((PersonaModel.titulos_registrados > 0, 1), else_=0)).label(
                        "con_titulos"
                    ),
                    func.sum(case((PersonaModel.ultima_consulta_en.is_(None), 1), else_=0)).label(
                        "nunca"
                    ),
                    func.sum(
                        case(
                            (
                                PersonaModel.ultima_consulta_exitosa_en >= _inicio_del_dia(desde),
                                1,
                            ),
                            else_=0,
                        )
                    ).label("en_periodo"),
                    func.sum(
                        case(
                            (
                                PersonaModel.ultima_consulta_estado.in_(
                                    [
                                        EstadoConsulta.ERROR_PROVEEDOR.value,
                                        EstadoConsulta.ERROR_RED.value,
                                        EstadoConsulta.ERROR_DATOS.value,
                                        EstadoConsulta.RECHAZADO.value,
                                    ]
                                ),
                                1,
                            ),
                            else_=0,
                        )
                    ).label("con_error"),
                )
            )
        ).one()

        total = fila.total or 0
        activas = fila.activas or 0
        con_titulos = fila.con_titulos or 0
        return ResumenCobertura(
            total_personas=total,
            personas_activas=activas,
            con_titulos=con_titulos,
            sin_titulos=max(0, activas - con_titulos),
            nunca_consultadas=fila.nunca or 0,
            consultadas_en_periodo=fila.en_periodo or 0,
            con_error_ultima_consulta=fila.con_error or 0,
        )

    async def resumen_titulos(self) -> ResumenTitulos:
        fila = (
            await self._s.execute(
                select(
                    func.count().label("total"),
                    func.sum(
                        case((TituloModel.estado == EstadoTitulo.VIGENTE.value, 1), else_=0)
                    ).label("vigentes"),
                    func.sum(
                        case((TituloModel.estado == EstadoTitulo.RETIRADO.value, 1), else_=0)
                    ).label("retirados"),
                    func.sum(
                        case(
                            (TituloModel.estado == EstadoTitulo.POR_VERIFICAR.value, 1),
                            else_=0,
                        )
                    ).label("por_verificar"),
                    func.sum(cast(TituloModel.verificado, Integer)).label("verificados"),
                    func.sum(
                        case(
                            (
                                TituloModel.nivel.in_(
                                    [
                                        NivelTitulo.ESPECIALIZACION.value,
                                        NivelTitulo.MAESTRIA.value,
                                        NivelTitulo.DOCTORADO.value,
                                    ]
                                ),
                                1,
                            ),
                            else_=0,
                        )
                    ).label("posgrados"),
                )
            )
        ).one()

        por_nivel = (
            await self._s.execute(
                select(TituloModel.nivel, func.count())
                .group_by(TituloModel.nivel)
                .order_by(func.count().desc())
            )
        ).all()

        por_institucion = (
            await self._s.execute(
                select(TituloModel.institucion, func.count())
                .group_by(TituloModel.institucion)
                .order_by(func.count().desc())
                .limit(15)
            )
        ).all()

        return ResumenTitulos(
            total=fila.total or 0,
            vigentes=fila.vigentes or 0,
            retirados=fila.retirados or 0,
            por_verificar=fila.por_verificar or 0,
            verificados=fila.verificados or 0,
            posgrados=fila.posgrados or 0,
            por_nivel=_porcentajes([(str(n), c) for n, c in por_nivel]),
            por_institucion=_porcentajes([(str(i), c) for i, c in por_institucion]),
        )

    async def resumen_consultas(self, *, desde: date, hasta: date) -> ResumenConsultas:
        inicio, fin = _inicio_del_dia(desde), _fin_del_dia(hasta)
        rango = (ConsultaLogModel.iniciado_en >= inicio, ConsultaLogModel.iniciado_en <= fin)

        fila = (
            await self._s.execute(
                select(
                    func.count().label("total"),
                    func.sum(
                        case((ConsultaLogModel.estado == EstadoConsulta.EXITO.value, 1), else_=0)
                    ).label("exitosas"),
                    func.sum(
                        case(
                            (ConsultaLogModel.estado == EstadoConsulta.SIN_DATOS.value, 1),
                            else_=0,
                        )
                    ).label("sin_datos"),
                    func.sum(
                        case(
                            (
                                ConsultaLogModel.estado.in_(
                                    [
                                        EstadoConsulta.ERROR_PROVEEDOR.value,
                                        EstadoConsulta.ERROR_RED.value,
                                        EstadoConsulta.ERROR_DATOS.value,
                                        EstadoConsulta.RECHAZADO.value,
                                    ]
                                ),
                                1,
                            ),
                            else_=0,
                        )
                    ).label("con_error"),
                    func.sum(
                        case(
                            (
                                ConsultaLogModel.estado == EstadoConsulta.DESAFIO_PENDIENTE.value,
                                1,
                            ),
                            else_=0,
                        )
                    ).label("esperando"),
                    func.sum(
                        case(
                            (
                                (ConsultaLogModel.titulos_nuevos > 0)
                                | (ConsultaLogModel.titulos_actualizados > 0)
                                | (ConsultaLogModel.titulos_retirados > 0),
                                1,
                            ),
                            else_=0,
                        )
                    ).label("con_cambios"),
                    func.avg(ConsultaLogModel.duracion_ms).label("duracion"),
                ).where(*rango)
            )
        ).one()

        por_estado = (
            await self._s.execute(
                select(ConsultaLogModel.estado, func.count())
                .where(*rango)
                .group_by(ConsultaLogModel.estado)
                .order_by(func.count().desc())
            )
        ).all()

        tendencia = (
            await self._s.execute(
                select(
                    func.date(ConsultaLogModel.iniciado_en).label("dia"),
                    func.count(),
                )
                .where(*rango)
                .group_by(func.date(ConsultaLogModel.iniciado_en))
                .order_by(func.date(ConsultaLogModel.iniciado_en))
            )
        ).all()

        return ResumenConsultas(
            total_periodo=fila.total or 0,
            exitosas=fila.exitosas or 0,
            sin_datos=fila.sin_datos or 0,
            con_error=fila.con_error or 0,
            esperando_desafio=fila.esperando or 0,
            con_cambios=fila.con_cambios or 0,
            duracion_promedio_ms=int(fila.duracion or 0),
            por_estado=_porcentajes([(str(e), c) for e, c in por_estado]),
            tendencia_diaria=[
                PuntoSerie(fecha=_a_fecha(dia), valor=cantidad) for dia, cantidad in tendencia
            ],
        )

    async def personas_por_unidad(self, *, limite: int = 15) -> list[ConteoEtiquetado]:
        filas = (
            await self._s.execute(
                select(PersonaModel.unidad, func.count())
                .where(PersonaModel.activo.is_(True))
                .group_by(PersonaModel.unidad)
                .order_by(func.count().desc())
                .limit(limite)
            )
        ).all()
        return _porcentajes([(u or "", c) for u, c in filas])

    async def personas_por_vinculacion(self) -> list[ConteoEtiquetado]:
        filas = (
            await self._s.execute(
                select(PersonaModel.tipo_vinculacion, func.count())
                .where(PersonaModel.activo.is_(True))
                .group_by(PersonaModel.tipo_vinculacion)
                .order_by(func.count().desc())
            )
        ).all()
        return _porcentajes([(str(v), c) for v, c in filas])


def _a_fecha(valor: Any) -> date:
    if isinstance(valor, date):
        return valor
    if isinstance(valor, datetime):
        return valor.date()
    return date.fromisoformat(str(valor))
