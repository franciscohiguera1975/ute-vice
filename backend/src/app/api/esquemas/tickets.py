"""Esquemas del modulo de tickets."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import Field

from app.api.esquemas.comunes import EsquemaBase
from app.application.casos_uso.tickets import Responsable, TicketConSeguimiento
from app.domain.entities.ticket import SeguimientoTicket
from app.domain.enums import EstadoTicket
from app.domain.ports.tickets import VistaTicket


class TicketCrear(EsquemaBase):
    titulo: Annotated[str, Field(min_length=3, max_length=200)]
    descripcion: Annotated[str, Field(min_length=1)]
    solicitante_id: UUID


class SeguimientoCrear(EsquemaBase):
    comentario: Annotated[str, Field(min_length=1)]
    estado_nuevo: EstadoTicket | None = None


class AsignarTicketEntrada(EsquemaBase):
    usuario_id: UUID | None = None


class SeguimientoSalida(EsquemaBase):
    id: UUID
    autor_id: UUID | None
    comentario: str
    estado_anterior: EstadoTicket | None
    estado_nuevo: EstadoTicket | None
    creado_en: datetime

    @classmethod
    def desde(cls, s: SeguimientoTicket) -> SeguimientoSalida:
        return cls(
            id=s.id,
            autor_id=s.autor_id,
            comentario=s.comentario,
            estado_anterior=s.estado_anterior,
            estado_nuevo=s.estado_nuevo,
            creado_en=s.creado_en,
        )


class TicketSalida(EsquemaBase):
    id: UUID
    titulo: str
    descripcion: str
    estado: EstadoTicket
    solicitante_id: UUID
    solicitante_nombre: str
    solicitante_unidad: str | None
    asignado_a: UUID | None
    asignado_a_nombre: str | None
    creado_por: UUID | None
    creado_en: datetime
    actualizado_en: datetime

    @classmethod
    def desde(cls, v: VistaTicket) -> TicketSalida:
        return cls(
            id=v.ticket.id,
            titulo=v.ticket.titulo,
            descripcion=v.ticket.descripcion,
            estado=v.ticket.estado,
            solicitante_id=v.ticket.solicitante_id,
            solicitante_nombre=v.solicitante_nombre,
            solicitante_unidad=v.solicitante_unidad,
            asignado_a=v.ticket.asignado_a,
            asignado_a_nombre=v.asignado_a_nombre,
            creado_por=v.ticket.creado_por,
            creado_en=v.ticket.creado_en,
            actualizado_en=v.ticket.actualizado_en,
        )


class TicketDetalleSalida(EsquemaBase):
    ticket: TicketSalida
    seguimientos: list[SeguimientoSalida]

    @classmethod
    def desde(cls, detalle: TicketConSeguimiento) -> TicketDetalleSalida:
        return cls(
            ticket=TicketSalida.desde(detalle.vista),
            seguimientos=[SeguimientoSalida.desde(s) for s in detalle.seguimientos],
        )


class ResponsableSalida(EsquemaBase):
    id: UUID
    nombre_completo: str

    @classmethod
    def desde(cls, r: Responsable) -> ResponsableSalida:
        return cls(id=r.id, nombre_completo=r.nombre_completo)
