"""Repositorios de personas, titulos, historico y jobs sobre PostgreSQL."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Select, delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.consulta import ConsultaLog, ItemJob, JobCobertura
from app.domain.entities.persona import Persona
from app.domain.entities.titulo import Titulo
from app.domain.enums import EstadoConsulta, EstadoItemJob, EstadoJob, EstadoTitulo
from app.domain.ports.repositorios import (
    FiltroLogs,
    FiltroPersonas,
    FiltroTitulos,
    Pagina,
    Paginacion,
)
from app.domain.value_objects import Cedula, normalizar_texto
from app.infrastructure.db import mapeadores as m
from app.infrastructure.db.modelos import (
    ConsultaLogModel,
    ItemJobModel,
    JobCoberturaModel,
    PersonaModel,
    TituloModel,
)

#: Columnas por las que se admite ordenar. Se restringe a una lista blanca para
#: que un parametro de la peticion no pueda inyectar SQL en el ORDER BY.
_ORDEN_PERSONAS = {
    "apellidos": PersonaModel.apellidos,
    "nombres": PersonaModel.nombres,
    "cedula": PersonaModel.cedula,
    "unidad": PersonaModel.unidad,
    "ultima_consulta": PersonaModel.ultima_consulta_en,
    "titulos": PersonaModel.titulos_registrados,
    "creado_en": PersonaModel.creado_en,
}

_ORDEN_TITULOS = {
    "denominacion": TituloModel.denominacion,
    "institucion": TituloModel.institucion,
    "nivel": TituloModel.nivel,
    "fecha_registro": TituloModel.fecha_registro,
    "estado": TituloModel.estado,
    "creado_en": TituloModel.creado_en,
}


def _aplicar_orden(
    consulta: Select[Any],
    paginacion: Paginacion,
    mapa: Mapping[str, Any],
    por_defecto: Any,
) -> Select[Any]:
    """Aplica el ordenamiento pedido, restringido a la lista blanca `mapa`.

    Un campo desconocido cae al de por defecto en lugar de llegar al SQL: el
    `ORDER BY` nunca debe construirse con texto que venga de la peticion.
    """
    columna = mapa.get(paginacion.ordenar_por or "", por_defecto)
    return consulta.order_by(columna.desc() if paginacion.descendente else columna.asc())


# ===========================================================================
class RepositorioPersonasSQL:
    def __init__(self, sesion: AsyncSession) -> None:
        self._s = sesion

    async def obtener(self, persona_id: UUID) -> Persona | None:
        fila = await self._s.get(PersonaModel, persona_id)
        return m.persona_a_dominio(fila) if fila else None

    async def obtener_por_cedula(self, cedula: Cedula) -> Persona | None:
        fila = await self._s.scalar(select(PersonaModel).where(PersonaModel.cedula == cedula.valor))
        return m.persona_a_dominio(fila) if fila else None

    def _filtrar(self, consulta: Select[Any], filtro: FiltroPersonas) -> Select[Any]:
        if filtro.texto:
            # La clave de busqueda esta normalizada sin acentos; el termino del
            # usuario se normaliza igual antes de comparar.
            patron = f"%{normalizar_texto(filtro.texto)}%"
            consulta = consulta.where(
                or_(
                    PersonaModel.clave_busqueda.like(patron),
                    PersonaModel.cedula.like(f"%{filtro.texto.strip()}%"),
                )
            )
        if filtro.cedula:
            consulta = consulta.where(PersonaModel.cedula == filtro.cedula.strip())
        if filtro.unidad:
            consulta = consulta.where(PersonaModel.unidad.ilike(f"%{filtro.unidad}%"))
        if filtro.tipo_vinculacion:
            consulta = consulta.where(
                PersonaModel.tipo_vinculacion == filtro.tipo_vinculacion.value
            )
        if filtro.activo is not None:
            consulta = consulta.where(PersonaModel.activo == filtro.activo)
        if filtro.con_titulos is not None:
            consulta = consulta.where(
                PersonaModel.titulos_registrados > 0
                if filtro.con_titulos
                else PersonaModel.titulos_registrados == 0
            )
        if filtro.nunca_consultadas:
            consulta = consulta.where(PersonaModel.ultima_consulta_en.is_(None))
        if filtro.estado_ultima_consulta:
            consulta = consulta.where(
                PersonaModel.ultima_consulta_estado == filtro.estado_ultima_consulta.value
            )
        if filtro.consultadas_desde:
            consulta = consulta.where(PersonaModel.ultima_consulta_en >= filtro.consultadas_desde)
        if filtro.consultadas_hasta:
            consulta = consulta.where(PersonaModel.ultima_consulta_en <= filtro.consultadas_hasta)
        return consulta

    async def listar(self, filtro: FiltroPersonas, paginacion: Paginacion) -> Pagina[Persona]:
        base = self._filtrar(select(PersonaModel), filtro)
        total = (
            await self._s.scalar(
                self._filtrar(select(func.count()).select_from(PersonaModel), filtro)
            )
            or 0
        )
        consulta = _aplicar_orden(base, paginacion, _ORDEN_PERSONAS, PersonaModel.apellidos)
        filas = await self._s.scalars(consulta.offset(paginacion.offset).limit(paginacion.limite))
        return Pagina(
            items=[m.persona_a_dominio(f) for f in filas],
            total=total,
            pagina=paginacion.pagina,
            tamano=paginacion.tamano,
        )

    async def agregar(self, persona: Persona) -> Persona:
        self._s.add(m.persona_a_modelo(persona))
        await self._s.flush()
        return persona

    async def agregar_muchas(self, personas: list[Persona]) -> int:
        if not personas:
            return 0
        self._s.add_all([m.persona_a_modelo(p) for p in personas])
        await self._s.flush()
        return len(personas)

    async def actualizar(self, persona: Persona) -> Persona:
        modelo = await self._s.get(PersonaModel, persona.id)
        if modelo is None:
            raise ValueError(f"Persona inexistente: {persona.id}")
        m.persona_a_modelo(persona, modelo)
        await self._s.flush()
        return persona

    async def eliminar(self, persona_id: UUID) -> None:
        await self._s.execute(delete(PersonaModel).where(PersonaModel.id == persona_id))

    async def existe_cedula(self, cedula: Cedula, *, excluyendo: UUID | None = None) -> bool:
        consulta = (
            select(func.count())
            .select_from(PersonaModel)
            .where(PersonaModel.cedula == cedula.valor)
        )
        if excluyendo:
            consulta = consulta.where(PersonaModel.id != excluyendo)
        return bool(await self._s.scalar(consulta))

    async def seleccionar_para_cobertura(
        self, *, desde: datetime, hasta: datetime, limite: int | None = None
    ) -> list[Persona]:
        """Personas activas pendientes de consulta dentro del periodo.

        Entran tres grupos: las que nunca se consultaron, las cuya ultima
        consulta cae fuera del periodo, y las que fallaron dentro de el. Quien
        tenga una consulta correcta dentro de la ventana queda excluido — esa es
        la garantia de que nadie se repite hasta cubrir a todos.
        """
        consulta = (
            select(PersonaModel)
            .where(PersonaModel.activo.is_(True))
            .where(
                or_(
                    PersonaModel.ultima_consulta_en.is_(None),
                    PersonaModel.ultima_consulta_en < desde,
                    PersonaModel.ultima_consulta_estado.in_(
                        [
                            EstadoConsulta.ERROR_PROVEEDOR.value,
                            EstadoConsulta.ERROR_RED.value,
                            EstadoConsulta.RECHAZADO.value,
                        ]
                    ),
                )
            )
            .order_by(
                PersonaModel.ultima_consulta_en.asc().nullsfirst(),
                PersonaModel.creado_en.asc(),
            )
        )
        if limite:
            consulta = consulta.limit(limite)
        filas = await self._s.scalars(consulta)
        return [m.persona_a_dominio(f) for f in filas]

    async def contar_activas(self) -> int:
        return (
            await self._s.scalar(
                select(func.count()).select_from(PersonaModel).where(PersonaModel.activo.is_(True))
            )
            or 0
        )


# ===========================================================================
class RepositorioTitulosSQL:
    def __init__(self, sesion: AsyncSession) -> None:
        self._s = sesion

    async def obtener(self, titulo_id: UUID) -> Titulo | None:
        fila = await self._s.get(TituloModel, titulo_id)
        return m.titulo_a_dominio(fila) if fila else None

    def _filtrar(self, consulta: Select[Any], filtro: FiltroTitulos) -> Select[Any]:
        if filtro.texto:
            patron = f"%{filtro.texto.strip()}%"
            consulta = consulta.where(
                or_(
                    TituloModel.denominacion.ilike(patron),
                    TituloModel.institucion.ilike(patron),
                    TituloModel.area_conocimiento.ilike(patron),
                )
            )
        if filtro.persona_id:
            consulta = consulta.where(TituloModel.persona_id == filtro.persona_id)
        if filtro.nivel:
            consulta = consulta.where(TituloModel.nivel == filtro.nivel.value)
        if filtro.estado:
            consulta = consulta.where(TituloModel.estado == filtro.estado.value)
        if filtro.institucion:
            consulta = consulta.where(TituloModel.institucion.ilike(f"%{filtro.institucion}%"))
        if filtro.verificado is not None:
            consulta = consulta.where(TituloModel.verificado == filtro.verificado)
        if filtro.requiere_atencion:
            consulta = consulta.where(
                or_(
                    TituloModel.estado == EstadoTitulo.RETIRADO.value,
                    TituloModel.estado == EstadoTitulo.POR_VERIFICAR.value,
                    TituloModel.nivel == "NO_DETERMINADO",
                )
            )
        if filtro.registro_desde:
            consulta = consulta.where(TituloModel.fecha_registro >= filtro.registro_desde)
        if filtro.registro_hasta:
            consulta = consulta.where(TituloModel.fecha_registro <= filtro.registro_hasta)
        return consulta

    async def listar(self, filtro: FiltroTitulos, paginacion: Paginacion) -> Pagina[Titulo]:
        base = self._filtrar(select(TituloModel), filtro)
        total = (
            await self._s.scalar(
                self._filtrar(select(func.count()).select_from(TituloModel), filtro)
            )
            or 0
        )
        consulta = _aplicar_orden(base, paginacion, _ORDEN_TITULOS, TituloModel.denominacion)
        filas = await self._s.scalars(consulta.offset(paginacion.offset).limit(paginacion.limite))
        return Pagina(
            items=[m.titulo_a_dominio(f) for f in filas],
            total=total,
            pagina=paginacion.pagina,
            tamano=paginacion.tamano,
        )

    async def listar_por_persona(
        self, persona_id: UUID, *, incluir_retirados: bool = True
    ) -> list[Titulo]:
        consulta = select(TituloModel).where(TituloModel.persona_id == persona_id)
        if not incluir_retirados:
            consulta = consulta.where(TituloModel.estado != EstadoTitulo.RETIRADO.value)
        filas = await self._s.scalars(
            consulta.order_by(TituloModel.nivel, TituloModel.denominacion)
        )
        return [m.titulo_a_dominio(f) for f in filas]

    async def agregar(self, titulo: Titulo) -> Titulo:
        self._s.add(m.titulo_a_modelo(titulo))
        await self._s.flush()
        return titulo

    async def agregar_muchos(self, titulos: list[Titulo]) -> int:
        if not titulos:
            return 0
        self._s.add_all([m.titulo_a_modelo(t) for t in titulos])
        await self._s.flush()
        return len(titulos)

    async def actualizar(self, titulo: Titulo) -> Titulo:
        modelo = await self._s.get(TituloModel, titulo.id)
        if modelo is None:
            raise ValueError(f"Titulo inexistente: {titulo.id}")
        m.titulo_a_modelo(titulo, modelo)
        await self._s.flush()
        return titulo

    async def actualizar_muchos(self, titulos: list[Titulo]) -> int:
        for titulo in titulos:
            await self.actualizar(titulo)
        return len(titulos)

    async def eliminar(self, titulo_id: UUID) -> None:
        await self._s.execute(delete(TituloModel).where(TituloModel.id == titulo_id))

    async def contar_por_persona(self, persona_id: UUID) -> int:
        return (
            await self._s.scalar(
                select(func.count())
                .select_from(TituloModel)
                .where(TituloModel.persona_id == persona_id)
            )
            or 0
        )


# ===========================================================================
class RepositorioLogsSQL:
    def __init__(self, sesion: AsyncSession) -> None:
        self._s = sesion

    async def obtener(self, log_id: UUID) -> ConsultaLog | None:
        fila = await self._s.get(ConsultaLogModel, log_id)
        return m.log_a_dominio(fila) if fila else None

    def _filtrar(self, consulta: Select[Any], filtro: FiltroLogs) -> Select[Any]:
        if filtro.persona_id:
            consulta = consulta.where(ConsultaLogModel.persona_id == filtro.persona_id)
        if filtro.job_id:
            consulta = consulta.where(ConsultaLogModel.job_id == filtro.job_id)
        if filtro.cedula:
            consulta = consulta.where(ConsultaLogModel.cedula == filtro.cedula.strip())
        if filtro.estado:
            consulta = consulta.where(ConsultaLogModel.estado == filtro.estado.value)
        if filtro.solo_errores:
            consulta = consulta.where(
                ConsultaLogModel.estado.in_(
                    [
                        EstadoConsulta.ERROR_PROVEEDOR.value,
                        EstadoConsulta.ERROR_RED.value,
                        EstadoConsulta.ERROR_DATOS.value,
                        EstadoConsulta.RECHAZADO.value,
                    ]
                )
            )
        if filtro.solo_con_cambios:
            # Un registro sin cambios reales lleva un unico elemento de tipo
            # SIN_CAMBIOS o PRIMERA_CONSULTA; se descartan por conteo.
            consulta = consulta.where(
                (ConsultaLogModel.titulos_nuevos > 0)
                | (ConsultaLogModel.titulos_actualizados > 0)
                | (ConsultaLogModel.titulos_retirados > 0)
            )
        if filtro.desde:
            consulta = consulta.where(ConsultaLogModel.iniciado_en >= filtro.desde)
        if filtro.hasta:
            consulta = consulta.where(ConsultaLogModel.iniciado_en <= filtro.hasta)
        return consulta

    async def listar(self, filtro: FiltroLogs, paginacion: Paginacion) -> Pagina[ConsultaLog]:
        base = self._filtrar(select(ConsultaLogModel), filtro)
        total = (
            await self._s.scalar(
                self._filtrar(select(func.count()).select_from(ConsultaLogModel), filtro)
            )
            or 0
        )
        filas = await self._s.scalars(
            base.order_by(ConsultaLogModel.iniciado_en.desc())
            .offset(paginacion.offset)
            .limit(paginacion.limite)
        )
        return Pagina(
            items=[m.log_a_dominio(f) for f in filas],
            total=total,
            pagina=paginacion.pagina,
            tamano=paginacion.tamano,
        )

    async def agregar(self, log: ConsultaLog) -> ConsultaLog:
        self._s.add(m.log_a_modelo(log))
        await self._s.flush()
        return log

    async def ultimo_de_persona(self, persona_id: UUID) -> ConsultaLog | None:
        fila = await self._s.scalar(
            select(ConsultaLogModel)
            .where(ConsultaLogModel.persona_id == persona_id)
            .order_by(ConsultaLogModel.iniciado_en.desc())
            .limit(1)
        )
        return m.log_a_dominio(fila) if fila else None

    async def contar_en_ventana(self, desde: datetime, hasta: datetime) -> int:
        return (
            await self._s.scalar(
                select(func.count())
                .select_from(ConsultaLogModel)
                .where(
                    ConsultaLogModel.iniciado_en >= desde,
                    ConsultaLogModel.iniciado_en <= hasta,
                )
            )
            or 0
        )


# ===========================================================================
class RepositorioJobsSQL:
    def __init__(self, sesion: AsyncSession) -> None:
        self._s = sesion

    async def obtener(self, job_id: UUID) -> JobCobertura | None:
        fila = await self._s.get(JobCoberturaModel, job_id)
        return m.job_a_dominio(fila) if fila else None

    async def listar(
        self, paginacion: Paginacion, *, estado: EstadoJob | None = None
    ) -> Pagina[JobCobertura]:
        base = select(JobCoberturaModel)
        conteo = select(func.count()).select_from(JobCoberturaModel)
        if estado:
            base = base.where(JobCoberturaModel.estado == estado.value)
            conteo = conteo.where(JobCoberturaModel.estado == estado.value)

        total = await self._s.scalar(conteo) or 0
        filas = await self._s.scalars(
            base.order_by(JobCoberturaModel.creado_en.desc())
            .offset(paginacion.offset)
            .limit(paginacion.limite)
        )
        return Pagina(
            items=[m.job_a_dominio(f) for f in filas],
            total=total,
            pagina=paginacion.pagina,
            tamano=paginacion.tamano,
        )

    async def job_activo(self) -> JobCobertura | None:
        fila = await self._s.scalar(
            select(JobCoberturaModel)
            .where(
                JobCoberturaModel.estado.in_(
                    [
                        EstadoJob.PROGRAMADO.value,
                        EstadoJob.EN_CURSO.value,
                        EstadoJob.PAUSADO.value,
                    ]
                )
            )
            .order_by(JobCoberturaModel.creado_en.desc())
            .limit(1)
        )
        return m.job_a_dominio(fila) if fila else None

    async def agregar(self, job: JobCobertura) -> JobCobertura:
        self._s.add(m.job_a_modelo(job))
        await self._s.flush()
        return job

    async def actualizar(self, job: JobCobertura) -> JobCobertura:
        modelo = await self._s.get(JobCoberturaModel, job.id)
        if modelo is None:
            raise ValueError(f"Job inexistente: {job.id}")
        m.job_a_modelo(job, modelo)
        await self._s.flush()
        return job

    async def agregar_items(self, items: list[ItemJob]) -> int:
        if not items:
            return 0
        self._s.add_all([m.item_a_modelo(i) for i in items])
        await self._s.flush()
        return len(items)

    async def obtener_item(self, item_id: UUID) -> ItemJob | None:
        fila = await self._s.get(ItemJobModel, item_id)
        return m.item_a_dominio(fila) if fila else None

    async def obtener_item_por_desafio(self, desafio_id: str) -> ItemJob | None:
        fila = await self._s.scalar(
            select(ItemJobModel).where(ItemJobModel.desafio_id == desafio_id)
        )
        return m.item_a_dominio(fila) if fila else None

    async def siguiente_item(self, job_id: UUID, *, ahora: datetime) -> ItemJob | None:
        """Reclama el siguiente item listo, bloqueando su fila.

        `FOR UPDATE SKIP LOCKED` es lo que hace segura la ejecucion con varios
        trabajadores: cada uno toma una fila distinta sin bloquearse entre si, y
        ninguna persona se consulta dos veces en paralelo.
        """
        fila = await self._s.scalar(
            select(ItemJobModel)
            .where(
                ItemJobModel.job_id == job_id,
                ItemJobModel.estado == EstadoItemJob.PENDIENTE.value,
                or_(
                    ItemJobModel.programado_para.is_(None),
                    ItemJobModel.programado_para <= ahora,
                ),
            )
            .order_by(ItemJobModel.orden)
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        return m.item_a_dominio(fila) if fila else None

    async def actualizar_item(self, item: ItemJob) -> ItemJob:
        modelo = await self._s.get(ItemJobModel, item.id)
        if modelo is None:
            raise ValueError(f"Item inexistente: {item.id}")
        m.item_a_modelo(item, modelo)
        await self._s.flush()
        return item

    async def listar_items(
        self, job_id: UUID, paginacion: Paginacion, *, estado: str | None = None
    ) -> Pagina[ItemJob]:
        base = select(ItemJobModel).where(ItemJobModel.job_id == job_id)
        conteo = select(func.count()).select_from(ItemJobModel).where(ItemJobModel.job_id == job_id)
        if estado:
            base = base.where(ItemJobModel.estado == estado)
            conteo = conteo.where(ItemJobModel.estado == estado)

        total = await self._s.scalar(conteo) or 0
        filas = await self._s.scalars(
            base.order_by(ItemJobModel.orden).offset(paginacion.offset).limit(paginacion.limite)
        )
        return Pagina(
            items=[m.item_a_dominio(f) for f in filas],
            total=total,
            pagina=paginacion.pagina,
            tamano=paginacion.tamano,
        )

    async def contar_items_pendientes(self, job_id: UUID) -> int:
        return (
            await self._s.scalar(
                select(func.count())
                .select_from(ItemJobModel)
                .where(
                    ItemJobModel.job_id == job_id,
                    ItemJobModel.estado.in_(
                        [EstadoItemJob.PENDIENTE.value, EstadoItemJob.EN_PROCESO.value]
                    ),
                )
            )
            or 0
        )
