"""Agregaciones del distributivo docente para su tablero.

Mismo criterio que `analitica.py`: se cuenta en la base, no en Python. El
distributivo pasa de las 16.000 filas y crece un periodo cada semestre; traerlas
para contar cuatro estados convertiria el tablero en una espera.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any
from uuid import UUID

from sqlalchemy import Float, Select, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import EstadoValidacion
from app.domain.ports.analitica import (
    AvanceDeFacultad,
    ConteoEtiquetado,
    EstadosDeFacultad,
    FilaComparativa,
    GrupoDePeriodos,
    PeriodoDisponible,
    TiempoParcialPorCarrera,
    TiempoParcialPorFacultad,
    TotalesTiempoParcial,
    ValidacionDeGrupo,
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

#: Como escribe el catalogo la dedicacion de tiempo parcial. Es el filtro fijo
#: de la pantalla de tiempo parcial, no un valor que se elija.
_TIEMPO_PARCIAL = "TIEMPO PARCIAL"

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
    async def validacion_de_grupo(self, paos: Sequence[UUID]) -> ValidacionDeGrupo | None:
        """Como quedo la validacion del grupo entero.

        Los docentes se cuentan distintos sobre el grupo, no sumando periodo a
        periodo: quien dicta en grado y en posgrado el mismo semestre es una
        persona, no dos.
        """
        if not paos:
            return None

        estado = FilaDistributivoModel.estado_validacion
        fila = (
            await self._s.execute(
                select(
                    func.count().label("total"),
                    _cuenta_si(estado == EstadoValidacion.OK.value).label("solo_ok"),
                    _cuenta_si(estado == EstadoValidacion.OK_EXCEPCION.value).label("excepciones"),
                    _cuenta_si(estado == EstadoValidacion.PENDIENTE.value).label("pendientes"),
                    _cuenta_si(estado == EstadoValidacion.ERROR.value).label("con_error"),
                    _cuenta_si(estado.is_(None)).label("sin_estado"),
                    func.count(func.distinct(FilaDistributivoModel.docente_id)).label("docentes"),
                    func.coalesce(func.sum(FilaDistributivoModel.total_horas), 0.0).label("horas"),
                ).where(FilaDistributivoModel.pao_id.in_(list(paos)))
            )
        ).one()

        if not fila.total:
            return None

        etiquetas = (
            await self._s.execute(
                select(PaoModel.codigo, PaoModel.nombre)
                .where(PaoModel.id.in_(list(paos)))
                .order_by(PaoModel.codigo)
            )
        ).all()

        return ValidacionDeGrupo(
            codigos=tuple(e.codigo for e in etiquetas),
            nombres=tuple(e.nombre for e in etiquetas),
            total=fila.total,
            aprobadas=fila.solo_ok + fila.excepciones,
            pendientes=fila.pendientes,
            con_error=fila.con_error,
            sin_estado=fila.sin_estado,
            docentes=fila.docentes or 0,
            horas=round(float(fila.horas), 2),
            por_estado=_estados_con_porcentaje(fila),
        )

    async def validacion_por_facultad(
        self, *, grupo_a: Sequence[UUID], grupo_b: Sequence[UUID]
    ) -> list[FilaComparativa]:
        if not grupo_a and not grupo_b:
            return []

        estado = FilaDistributivoModel.estado_validacion
        pao = FilaDistributivoModel.pao_id
        en_a, en_b = pao.in_(list(grupo_a)), pao.in_(list(grupo_b))

        consulta: Select[Any] = (
            select(
                FacultadModel.nombre.label("etiqueta"),
                _cuenta_si(en_a).label("total_actual"),
                _cuenta_si(en_a & estado.in_(_APROBADOS)).label("aprobadas_actual"),
                _cuenta_si(en_a & estado.is_not(None)).label("evaluadas_actual"),
                _cuenta_si(en_b).label("total_anterior"),
                _cuenta_si(en_b & estado.in_(_APROBADOS)).label("aprobadas_anterior"),
                _cuenta_si(en_b & estado.is_not(None)).label("evaluadas_anterior"),
            )
            .select_from(FilaDistributivoModel)
            .join(FacultadModel, FacultadModel.id == FilaDistributivoModel.facultad_id)
            .where(or_(en_a, en_b))
            .group_by(FacultadModel.nombre)
            .order_by(func.count().desc())
        )

        return [
            FilaComparativa(
                etiqueta=f.etiqueta,
                total_actual=f.total_actual,
                aprobadas_actual=f.aprobadas_actual,
                evaluadas_actual=f.evaluadas_actual,
                total_anterior=f.total_anterior,
                aprobadas_anterior=f.aprobadas_anterior,
                evaluadas_anterior=f.evaluadas_anterior,
            )
            for f in (await self._s.execute(consulta)).all()
        ]

    # ---------------------------------------------------------- desgloses
    async def distribucion_de_grupo(
        self, paos: Sequence[UUID], *, campo: str, limite: int = 12
    ) -> list[ConteoEtiquetado]:
        destino = _DESGLOSES.get(campo)
        if destino is None or not paos:
            return []
        columna, modelo = destino

        consulta = (
            select(modelo.nombre.label("etiqueta"), func.count().label("valor"))
            .select_from(FilaDistributivoModel)
            .join(modelo, modelo.id == columna)
            .where(FilaDistributivoModel.pao_id.in_(list(paos)))
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

    # -------------------------------------------------- grupos de periodos
    async def totales_de_grupo(
        self, paos: Sequence[UUID], *, dedicacion_ids: Sequence[UUID] = ()
    ) -> GrupoDePeriodos:
        """Filas y docentes distintos del grupo entero.

        Los docentes se cuentan aqui y no sumando la columna por facultad: un
        docente que dicta en dos facultades saldria dos veces en esa suma.
        """
        if not paos:
            return GrupoDePeriodos(codigos=(), filas=0, docentes=0)

        condicion: Any = FilaDistributivoModel.pao_id.in_(list(paos))
        if dedicacion_ids:
            condicion = condicion & FilaDistributivoModel.dedicacion_id.in_(list(dedicacion_ids))

        fila = (
            await self._s.execute(
                select(
                    func.count().label("filas"),
                    func.count(func.distinct(FilaDistributivoModel.docente_id)).label("docentes"),
                ).where(condicion)
            )
        ).one()

        codigos = (
            await self._s.scalars(
                select(PaoModel.codigo).where(PaoModel.id.in_(list(paos))).order_by(PaoModel.codigo)
            )
        ).all()

        return GrupoDePeriodos(
            codigos=tuple(codigos), filas=fila.filas or 0, docentes=fila.docentes or 0
        )

    async def avance_por_facultad(
        self,
        *,
        grupo_a: Sequence[UUID],
        grupo_b: Sequence[UUID],
        dedicacion_ids: Sequence[UUID] = (),
    ) -> list[AvanceDeFacultad]:
        if not grupo_a and not grupo_b:
            return []

        pao = FilaDistributivoModel.pao_id
        docente = FilaDistributivoModel.docente_id
        estado = FilaDistributivoModel.estado_validacion
        en_a, en_b = pao.in_(list(grupo_a)), pao.in_(list(grupo_b))

        def distintos(condicion: Any) -> Any:
            return func.count(func.distinct(docente)).filter(condicion)

        consulta = (
            select(
                FacultadModel.codigo.label("codigo"),
                FacultadModel.nombre.label("nombre"),
                distintos(en_a).label("docentes_a"),
                distintos(en_b).label("docentes_b"),
                _cuenta_si(en_b & estado.in_(_APROBADOS)).label("filas_aprobadas_b"),
                _cuenta_si(en_b & estado.is_not(None)).label("filas_evaluadas_b"),
            )
            .select_from(FilaDistributivoModel)
            .join(FacultadModel, FacultadModel.id == FilaDistributivoModel.facultad_id)
            .where(or_(en_a, en_b))
        )
        if dedicacion_ids:
            consulta = consulta.where(FilaDistributivoModel.dedicacion_id.in_(list(dedicacion_ids)))
        consulta = consulta.group_by(FacultadModel.codigo, FacultadModel.nombre).order_by(
            FacultadModel.codigo
        )

        return [
            AvanceDeFacultad(
                codigo=f.codigo,
                nombre=f.nombre,
                docentes_a=f.docentes_a,
                docentes_b=f.docentes_b,
                filas_aprobadas_b=f.filas_aprobadas_b,
                filas_evaluadas_b=f.filas_evaluadas_b,
            )
            for f in (await self._s.execute(consulta)).all()
        ]

    async def estados_por_facultad(
        self, paos: Sequence[UUID], *, dedicacion_ids: Sequence[UUID] = ()
    ) -> list[EstadosDeFacultad]:
        if not paos:
            return []

        estado = FilaDistributivoModel.estado_validacion
        condicion: Any = FilaDistributivoModel.pao_id.in_(list(paos))
        if dedicacion_ids:
            condicion = condicion & FilaDistributivoModel.dedicacion_id.in_(list(dedicacion_ids))

        consulta = (
            select(
                FacultadModel.codigo.label("codigo"),
                FacultadModel.nombre.label("nombre"),
                _cuenta_si(estado == EstadoValidacion.OK.value).label("ok"),
                _cuenta_si(estado == EstadoValidacion.OK_EXCEPCION.value).label("ok_excepcion"),
                _cuenta_si(estado == EstadoValidacion.PENDIENTE.value).label("pendiente"),
                _cuenta_si(estado == EstadoValidacion.ERROR.value).label("con_error"),
                _cuenta_si(estado.is_(None)).label("sin_estado"),
            )
            .select_from(FilaDistributivoModel)
            .join(FacultadModel, FacultadModel.id == FilaDistributivoModel.facultad_id)
            .where(condicion)
            .group_by(FacultadModel.codigo, FacultadModel.nombre)
            .order_by(FacultadModel.codigo)
        )

        return [
            EstadosDeFacultad(
                codigo=f.codigo,
                nombre=f.nombre,
                ok=f.ok,
                ok_excepcion=f.ok_excepcion,
                pendiente=f.pendiente,
                con_error=f.con_error,
                sin_estado=f.sin_estado,
            )
            for f in (await self._s.execute(consulta)).all()
        ]

    # ----------------------------------------------------------- tiempo parcial
    async def totales_tiempo_parcial(self, paos: Sequence[UUID]) -> TotalesTiempoParcial:
        if not paos:
            return TotalesTiempoParcial(docentes=0, horas_da=0.0)

        fila = (
            await self._s.execute(
                select(
                    func.count(func.distinct(FilaDistributivoModel.docente_id)).label("docentes"),
                    func.coalesce(func.sum(_horas_da()), 0.0).label("horas_da"),
                )
                .select_from(FilaDistributivoModel)
                .join(DedicacionModel, DedicacionModel.id == FilaDistributivoModel.dedicacion_id)
                .where(FilaDistributivoModel.pao_id.in_(list(paos)))
                .where(func.upper(DedicacionModel.nombre) == _TIEMPO_PARCIAL)
            )
        ).one()

        return TotalesTiempoParcial(
            docentes=fila.docentes or 0, horas_da=round(float(fila.horas_da), 2)
        )

    async def tiempo_parcial_por_facultad(
        self, paos: Sequence[UUID]
    ) -> list[TiempoParcialPorFacultad]:
        if not paos:
            return []

        consulta = (
            select(
                FacultadModel.codigo.label("codigo"),
                FacultadModel.nombre.label("nombre"),
                func.count(func.distinct(FilaDistributivoModel.docente_id)).label("docentes"),
                func.coalesce(func.sum(_horas_da()), 0.0).label("horas_da"),
            )
            .select_from(FilaDistributivoModel)
            .join(FacultadModel, FacultadModel.id == FilaDistributivoModel.facultad_id)
            .join(DedicacionModel, DedicacionModel.id == FilaDistributivoModel.dedicacion_id)
            .where(FilaDistributivoModel.pao_id.in_(list(paos)))
            .where(func.upper(DedicacionModel.nombre) == _TIEMPO_PARCIAL)
            .group_by(FacultadModel.codigo, FacultadModel.nombre)
            .order_by(FacultadModel.codigo)
        )

        return [
            TiempoParcialPorFacultad(
                codigo=f.codigo,
                nombre=f.nombre,
                docentes=f.docentes,
                horas_da=round(float(f.horas_da), 2),
            )
            for f in (await self._s.execute(consulta)).all()
        ]

    async def tiempo_parcial_por_carrera(
        self, paos: Sequence[UUID]
    ) -> list[TiempoParcialPorCarrera]:
        if not paos:
            return []

        consulta = (
            select(
                FacultadModel.codigo.label("facultad_codigo"),
                FacultadModel.nombre.label("facultad_nombre"),
                CarreraModel.nombre.label("carrera"),
                func.count(func.distinct(FilaDistributivoModel.docente_id)).label("docentes"),
                func.coalesce(func.sum(_horas_da()), 0.0).label("horas_da"),
            )
            .select_from(FilaDistributivoModel)
            .join(FacultadModel, FacultadModel.id == FilaDistributivoModel.facultad_id)
            .join(CarreraModel, CarreraModel.id == FilaDistributivoModel.carrera_id)
            .join(DedicacionModel, DedicacionModel.id == FilaDistributivoModel.dedicacion_id)
            .where(FilaDistributivoModel.pao_id.in_(list(paos)))
            .where(func.upper(DedicacionModel.nombre) == _TIEMPO_PARCIAL)
            .group_by(FacultadModel.codigo, FacultadModel.nombre, CarreraModel.nombre)
            .order_by(FacultadModel.codigo, CarreraModel.nombre)
        )

        return [
            TiempoParcialPorCarrera(
                facultad_codigo=f.facultad_codigo,
                facultad_nombre=f.facultad_nombre,
                carrera=f.carrera,
                docentes=f.docentes,
                horas_da=round(float(f.horas_da), 2),
            )
            for f in (await self._s.execute(consulta)).all()
        ]


def _horas_da() -> Any:
    """Horas de la subactividad `Da`, la primera del bloque de docencia.

    Vive en el JSONB `horas_docencia` y no en una columna propia: es el unico
    detalle de ese bloque que esta pantalla necesita agregar.
    """
    return cast(FilaDistributivoModel.horas_docencia["Da"].astext, Float)


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
