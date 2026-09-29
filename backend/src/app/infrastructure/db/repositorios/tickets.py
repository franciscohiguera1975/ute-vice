"""Repositorio de tickets sobre PostgreSQL."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import Row, Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.ticket import SeguimientoTicket, Ticket
from app.domain.ports.repositorios import Pagina, Paginacion
from app.domain.ports.tickets import FiltroTickets, VistaTicket
from app.infrastructure.db import mapeadores as m
from app.infrastructure.db.modelos import PersonaModel, UsuarioModel
from app.infrastructure.db.modelos_tickets import SeguimientoTicketModel, TicketModel

_ORDEN_TICKETS = {
    "titulo": TicketModel.titulo,
    "estado": TicketModel.estado,
    "creado_en": TicketModel.creado_en,
    "actualizado_en": TicketModel.actualizado_en,
}


def _aplicar_orden(consulta: Select[Any], paginacion: Paginacion) -> Select[Any]:
    columna = _ORDEN_TICKETS.get(paginacion.ordenar_por or "", TicketModel.creado_en)
    # Por defecto, los mas recientes primero: es el orden util para una cola de
    # soporte, y evita que un ticket viejo se pierda al fondo de la lista.
    descendente = paginacion.descendente if paginacion.ordenar_por else True
    return consulta.order_by(columna.desc() if descendente else columna.asc())


class RepositorioTicketsSQL:
    def __init__(self, sesion: AsyncSession) -> None:
        self._s = sesion

    def _consulta_base(self) -> Select[Any]:
        return (
            select(TicketModel, PersonaModel, UsuarioModel.nombre_completo)
            .join(PersonaModel, TicketModel.solicitante_id == PersonaModel.id)
            .outerjoin(UsuarioModel, TicketModel.asignado_a == UsuarioModel.id)
        )

    def _fila_a_vista(self, fila: Row[Any]) -> VistaTicket:
        ticket_modelo, persona_modelo, asignado_a_nombre = fila
        return VistaTicket(
            ticket=m.ticket_a_dominio(ticket_modelo),
            solicitante_nombre=f"{persona_modelo.nombres} {persona_modelo.apellidos}".strip(),
            solicitante_unidad=persona_modelo.unidad,
            asignado_a_nombre=asignado_a_nombre,
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
