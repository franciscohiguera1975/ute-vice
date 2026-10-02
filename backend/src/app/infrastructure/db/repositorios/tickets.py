"""Repositorio de tickets sobre PostgreSQL."""

from __future__ import annotations

from datetime import date
from typing import Any
from uuid import UUID

from sqlalchemy import Row, Select, case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.domain.entities.ticket import SeguimientoTicket, Ticket
from app.domain.enums import EstadoTicket, PrioridadTicket
from app.domain.ports.analitica import ConteoEtiquetado, PuntoSerie
from app.domain.ports.repositorios import Pagina, Paginacion
from app.domain.ports.tickets import EstadisticasTickets, FiltroTickets, VistaTicket
from app.infrastructure.db import mapeadores as m
from app.infrastructure.db.modelos import PersonaModel, UsuarioModel
from app.infrastructure.db.modelos_distributivo import CategoriaTicketModel
from app.infrastructure.db.modelos_tickets import SeguimientoTicketModel, TicketModel

_ORDEN_TICKETS = {
    "titulo": TicketModel.titulo,
    "estado": TicketModel.estado,
    "fecha_solicitud": TicketModel.fecha_solicitud,
    "creado_en": TicketModel.creado_en,
    "actualizado_en": TicketModel.actualizado_en,
}


def _aplicar_orden(consulta: Select[Any], paginacion: Paginacion) -> Select[Any]:
    columna = _ORDEN_TICKETS.get(paginacion.ordenar_por or "", TicketModel.creado_en)
    # Por defecto, los mas recientes primero: es el orden util para una cola de
    # soporte, y evita que un ticket viejo se pierda al fondo de la lista.
    descendente = paginacion.descendente if paginacion.ordenar_por else True
    return consulta.order_by(columna.desc() if descendente else columna.asc())


_CreadoPorModel = aliased(UsuarioModel, name="creado_por_usuario")


class RepositorioTicketsSQL:
    def __init__(self, sesion: AsyncSession) -> None:
        self._s = sesion

    def _consulta_base(self) -> Select[Any]:
        return (
            select(
                TicketModel,
                PersonaModel,
                UsuarioModel.nombre_completo,
                _CreadoPorModel.nombre_completo,
                CategoriaTicketModel.nombre,
            )
            .join(PersonaModel, TicketModel.solicitante_id == PersonaModel.id)
            .outerjoin(UsuarioModel, TicketModel.asignado_a == UsuarioModel.id)
            .outerjoin(_CreadoPorModel, TicketModel.creado_por == _CreadoPorModel.id)
            .outerjoin(CategoriaTicketModel, TicketModel.categoria_id == CategoriaTicketModel.id)
        )

    def _fila_a_vista(self, fila: Row[Any]) -> VistaTicket:
        (
            ticket_modelo,
            persona_modelo,
            asignado_a_nombre,
            creado_por_nombre,
            categoria_nombre,
        ) = fila
        return VistaTicket(
            ticket=m.ticket_a_dominio(ticket_modelo),
            solicitante_nombre=f"{persona_modelo.nombres} {persona_modelo.apellidos}".strip(),
            solicitante_unidad=persona_modelo.unidad,
            asignado_a_nombre=asignado_a_nombre,
            creado_por_nombre=creado_por_nombre,
            categoria_nombre=categoria_nombre,
        )

    def _filtrar(self, consulta: Select[Any], filtro: FiltroTickets) -> Select[Any]:
        if filtro.texto:
            patron = f"%{filtro.texto.strip()}%"
            consulta = consulta.where(
                or_(TicketModel.titulo.ilike(patron), TicketModel.descripcion.ilike(patron))
            )
        if filtro.estado:
            consulta = consulta.where(TicketModel.estado == filtro.estado.value)
        if filtro.solicitante_id:
            consulta = consulta.where(TicketModel.solicitante_id == filtro.solicitante_id)
        if filtro.asignado_a:
            consulta = consulta.where(TicketModel.asignado_a == filtro.asignado_a)
        if filtro.prioridad:
            consulta = consulta.where(TicketModel.prioridad == filtro.prioridad.value)
        if filtro.categoria_id:
            consulta = consulta.where(TicketModel.categoria_id == filtro.categoria_id)
        return consulta

    async def obtener(self, ticket_id: UUID) -> VistaTicket | None:
        fila = (
            await self._s.execute(self._consulta_base().where(TicketModel.id == ticket_id))
        ).first()
        return self._fila_a_vista(fila) if fila else None

    async def listar(self, filtro: FiltroTickets, paginacion: Paginacion) -> Pagina[VistaTicket]:
        base = self._filtrar(self._consulta_base(), filtro)
        total = (
            await self._s.scalar(
                self._filtrar(
                    select(func.count())
                    .select_from(TicketModel)
                    .join(PersonaModel, TicketModel.solicitante_id == PersonaModel.id),
                    filtro,
                )
            )
            or 0
        )
        consulta = _aplicar_orden(base, paginacion)
        filas = (
            await self._s.execute(consulta.offset(paginacion.offset).limit(paginacion.limite))
        ).all()
        return Pagina(
            items=[self._fila_a_vista(f) for f in filas],
            total=total,
            pagina=paginacion.pagina,
            tamano=paginacion.tamano,
        )

    async def agregar(self, ticket: Ticket) -> Ticket:
        self._s.add(m.ticket_a_modelo(ticket))
        await self._s.flush()
        return ticket

    async def actualizar(self, ticket: Ticket) -> Ticket:
        modelo = await self._s.get(TicketModel, ticket.id)
        if modelo is None:
            raise ValueError(f"Ticket inexistente: {ticket.id}")
        m.ticket_a_modelo(ticket, modelo)
        await self._s.flush()
        return ticket

    async def listar_seguimientos(self, ticket_id: UUID) -> list[SeguimientoTicket]:
        filas = await self._s.scalars(
            select(SeguimientoTicketModel)
            .where(SeguimientoTicketModel.ticket_id == ticket_id)
            .order_by(SeguimientoTicketModel.creado_en.asc())
        )
        return [m.seguimiento_a_dominio(f) for f in filas]

    async def agregar_seguimiento(self, seguimiento: SeguimientoTicket) -> SeguimientoTicket:
        self._s.add(m.seguimiento_a_modelo(seguimiento))
        await self._s.flush()
        return seguimiento

    async def estadisticas(
        self, *, asignado_a: UUID | None, desde: date, hasta: date
    ) -> EstadisticasTickets:
        condiciones: list[Any] = []
        if asignado_a is not None:
            condiciones.append(TicketModel.asignado_a == asignado_a)
        estados_terminales = [e.value for e in EstadoTicket if e.es_terminal]

        totales = (
            await self._s.execute(
                select(
                    func.count().label("total"),
                    func.sum(
                        case((TicketModel.estado.not_in(estados_terminales), 1), else_=0)
                    ).label("abiertos"),
                    func.sum(
                        case(
                            (
                                (TicketModel.fecha_limite.is_not(None))
                                & (TicketModel.fecha_limite < func.current_date())
                                & (TicketModel.estado.not_in(estados_terminales)),
                                1,
                            ),
                            else_=0,
                        )
                    ).label("vencidos"),
                    func.avg(
                        case(
                            (
                                TicketModel.estado == EstadoTicket.EJECUTADO.value,
                                func.extract(
                                    "epoch", TicketModel.actualizado_en - TicketModel.creado_en
                                )
                                / 3600.0,
                            )
                        )
                    ).label("horas_promedio"),
                ).where(*condiciones)
            )
        ).one()

        por_estado = (
            await self._s.execute(
                select(TicketModel.estado, func.count())
                .where(*condiciones)
                .group_by(TicketModel.estado)
            )
        ).all()
        por_prioridad = (
            await self._s.execute(
                select(TicketModel.prioridad, func.count())
                .where(*condiciones)
                .group_by(TicketModel.prioridad)
            )
        ).all()
        tendencia = (
            await self._s.execute(
                select(func.date(TicketModel.creado_en), func.count())
                .where(
                    *condiciones,
                    func.date(TicketModel.creado_en) >= desde,
                    func.date(TicketModel.creado_en) <= hasta,
                )
                .group_by(func.date(TicketModel.creado_en))
                .order_by(func.date(TicketModel.creado_en))
            )
        ).all()

        return EstadisticasTickets(
            total=totales.total or 0,
            total_abiertos=int(totales.abiertos or 0),
            total_vencidos=int(totales.vencidos or 0),
            tiempo_promedio_resolucion_horas=(
                round(float(totales.horas_promedio), 1)
                if totales.horas_promedio is not None
                else None
            ),
            por_estado=_conteos_etiquetados(
                [(EstadoTicket(e).etiqueta if e else "(sin estado)", c) for e, c in por_estado]
            ),
            por_prioridad=_conteos_etiquetados(
                [
                    (PrioridadTicket(p).etiqueta if p else "Sin prioridad", c)
                    for p, c in por_prioridad
                ]
            ),
            creados_por_dia=[PuntoSerie(fecha=dia, valor=cantidad) for dia, cantidad in tendencia],
        )


def _conteos_etiquetados(conteos: list[tuple[str, int]]) -> list[ConteoEtiquetado]:
    total = sum(v for _, v in conteos) or 1
    return [
        ConteoEtiquetado(etiqueta=etiqueta, valor=valor, porcentaje=round(valor / total * 100, 2))
        for etiqueta, valor in conteos
    ]
