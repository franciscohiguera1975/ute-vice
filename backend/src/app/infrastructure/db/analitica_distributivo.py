"""Agregaciones del distributivo docente para su tablero.

Mismo criterio que `analitica.py`: se cuenta en la base, no en Python. El
distributivo pasa de las 16.000 filas y crece un periodo cada semestre; traerlas
para contar cuatro estados convertiria el tablero en una espera.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import EstadoValidacion
from app.domain.ports.analitica import (
    ConteoEtiquetado,
    FilaComparativa,
    PeriodoDisponible,
    ValidacionDePeriodo,
)
from app.infrastructure.db.modelos_distributivo import (
    CarreraModel,
    CategoriaModel,
    DedicacionModel,
    FacultadModel,
    FilaDistributivoModel,
    NivelModel,
    PaoModel,
    SedeModel,
    TitularidadModel,
)

#: Estados que cuentan como carga valida. `OK_EXCEPCION` entra: dice que la
#: fila es valida por una excepcion concedida, no que este mal.
_APROBADOS = (EstadoValidacion.OK.value, EstadoValidacion.OK_EXCEPCION.value)

#: Catalogos por los que el tablero sabe desglosar un periodo. La clave es lo
#: que llega por la API; evita construir el `join` desde texto libre.
_DESGLOSES: dict[str, tuple[Any, Any]] = {
    "sede": (FilaDistributivoModel.sede_id, SedeModel),
    "dedicacion": (FilaDistributivoModel.dedicacion_id, DedicacionModel),
    "categoria": (FilaDistributivoModel.categoria_id, CategoriaModel),
    "titularidad": (FilaDistributivoModel.titularidad_id, TitularidadModel),
    "nivel": (FilaDistributivoModel.nivel_id, NivelModel),
    "carrera": (FilaDistributivoModel.carrera_id, CarreraModel),
    "facultad": (FilaDistributivoModel.facultad_id, FacultadModel),
}


def _cuenta_si(condicion: Any) -> Any:
    return func.count().filter(condicion)


class RepositorioAnaliticaDistributivoSQL:
    """Implementacion del puerto `RepositorioAnaliticaDistributivo`."""

    def __init__(self, sesion: AsyncSession) -> None:
        self._s = sesion

    # ------------------------------------------------------------ periodos
    async def periodos_con_filas(self) -> list[PeriodoDisponible]:
        """Solo los periodos que tienen carga.

        El catalogo puede tener periodos creados y todavia vacios; ofrecerlos en
        el selector del tablero llevaria a una pantalla con todo en cero.
        """
        consulta = (
            select(
                PaoModel.id,
                PaoModel.codigo,
                PaoModel.nombre,
                PaoModel.atributos["semestre"].astext.label("semestre"),
                func.count(FilaDistributivoModel.id).label("filas"),
            )
            .join(FilaDistributivoModel, FilaDistributivoModel.pao_id == PaoModel.id)
            .group_by(PaoModel.id, PaoModel.codigo, PaoModel.nombre, PaoModel.atributos)
            .order_by(PaoModel.codigo.desc())
        )
        return [
            PeriodoDisponible(
                id=fila.id,
                codigo=fila.codigo,
                nombre=fila.nombre,
                semestre=fila.semestre or "",
                filas=fila.filas,
            )
            for fila in (await self._s.execute(consulta)).all()
        ]

    # ---------------------------------------------------------- validacion
    async def validacion_de_periodo(self, pao_id: UUID) -> ValidacionDePeriodo | None:
        estado = FilaDistributivoModel.estado_validacion
        fila = (
            await self._s.execute(
                select(
                    PaoModel.codigo,
                    PaoModel.nombre,
                    func.count().label("total"),
                    _cuenta_si(estado == EstadoValidacion.OK.value).label("solo_ok"),
                    _cuenta_si(estado == EstadoValidacion.OK_EXCEPCION.value).label("excepciones"),
                    _cuenta_si(estado == EstadoValidacion.PENDIENTE.value).label("pendientes"),
                    _cuenta_si(estado == EstadoValidacion.ERROR.value).label("con_error"),
                    _cuenta_si(estado.is_(None)).label("sin_estado"),
                    func.count(func.distinct(FilaDistributivoModel.docente_id)).label("docentes"),
                    func.coalesce(func.sum(FilaDistributivoModel.total_horas), 0.0).label("horas"),
                )
                .join(PaoModel, PaoModel.id == FilaDistributivoModel.pao_id)
                .where(FilaDistributivoModel.pao_id == pao_id)
                .group_by(PaoModel.codigo, PaoModel.nombre)
            )
        ).one_or_none()

        if fila is None:
            return None

        return ValidacionDePeriodo(
            pao_id=pao_id,
            codigo=fila.codigo,
            nombre=fila.nombre,
            total=fila.total,
            aprobadas=fila.solo_ok + fila.excepciones,
            pendientes=fila.pendientes,
            con_error=fila.con_error,
            sin_estado=fila.sin_estado,
            docentes=fila.docentes,
            horas=round(float(fila.horas), 2),
            por_estado=_estados_con_porcentaje(fila),
        )

    async def validacion_por_facultad(
        self, *, actual: UUID, anterior: UUID | None
    ) -> list[FilaComparativa]:
        estado = FilaDistributivoModel.estado_validacion
        pao = FilaDistributivoModel.pao_id
        # `anterior` puede faltar —el primer periodo cargado no tiene con que
        # compararse—. Se usa el propio `actual` como marcador imposible para no
        # ramificar la consulta: las columnas «anterior» salen todas en cero.
        comparado = anterior if anterior is not None else actual
        sin_comparacion = anterior is None

        def columnas(destino: UUID, *, vacia: bool) -> tuple[Any, Any, Any]:
            if vacia:
                cero = func.count().filter(pao.is_(None))
                return cero, cero, cero
            es = pao == destino
            return (
                _cuenta_si(es),
                _cuenta_si(es & estado.in_(_APROBADOS)),
                _cuenta_si(es & estado.is_not(None)),
            )

        total_a, aprob_a, eval_a = columnas(actual, vacia=False)
        total_b, aprob_b, eval_b = columnas(comparado, vacia=sin_comparacion)

        consulta: Select[Any] = (
            select(
                FacultadModel.nombre.label("etiqueta"),
                total_a.label("total_actual"),
                aprob_a.label("aprobadas_actual"),
                eval_a.label("evaluadas_actual"),
                total_b.label("total_anterior"),
                aprob_b.label("aprobadas_anterior"),
                eval_b.label("evaluadas_anterior"),
            )
            .select_from(FilaDistributivoModel)
            .join(FacultadModel, FacultadModel.id == FilaDistributivoModel.facultad_id)
            .where(pao.in_([actual, comparado]))
            .group_by(FacultadModel.nombre)
            .order_by(func.count().desc())
        )

        return [
            FilaComparativa(
                etiqueta=fila.etiqueta,
                total_actual=fila.total_actual,
                aprobadas_actual=fila.aprobadas_actual,
                evaluadas_actual=fila.evaluadas_actual,
                total_anterior=fila.total_anterior,
                aprobadas_anterior=fila.aprobadas_anterior,
                evaluadas_anterior=fila.evaluadas_anterior,
            )
            for fila in (await self._s.execute(consulta)).all()
        ]

    # ---------------------------------------------------------- desgloses
    async def distribucion_de_periodo(
        self, pao_id: UUID, *, campo: str, limite: int = 12
    ) -> list[ConteoEtiquetado]:
        destino = _DESGLOSES.get(campo)
        if destino is None:
            return []
        columna, modelo = destino

        consulta = (
            select(modelo.nombre.label("etiqueta"), func.count().label("valor"))
            .select_from(FilaDistributivoModel)
            .join(modelo, modelo.id == columna)
            .where(FilaDistributivoModel.pao_id == pao_id)
            .group_by(modelo.nombre)
            .order_by(func.count().desc())
            .limit(limite)
        )
        filas = [(f.etiqueta, f.valor) for f in (await self._s.execute(consulta)).all()]
        total = sum(v for _, v in filas) or 1
        return [
            ConteoEtiquetado(etiqueta=e, valor=v, porcentaje=round(v / total * 100, 2))
            for e, v in filas
        ]


def _estados_con_porcentaje(fila: Any) -> list[ConteoEtiquetado]:
    """Los cuatro estados mas «sin estado», con su peso sobre el total.

    El porcentaje es sobre el total de filas y no sobre las evaluadas: esta
    lista alimenta el anillo, donde los sectores tienen que sumar el 100%.
    """
    crudos = [
        ("OK", fila.solo_ok),
        ("OK_EXCEPCION", fila.excepciones),
        ("PENDIENTE", fila.pendientes),
        ("ERROR", fila.con_error),
        ("SIN_ESTADO", fila.sin_estado),
    ]
    total = fila.total or 1
    return [
        ConteoEtiquetado(etiqueta=e, valor=v, porcentaje=round(v / total * 100, 2))
        for e, v in crudos
        if v > 0
    ]
