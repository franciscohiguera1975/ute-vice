"""Puerto de persistencia de tickets."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Protocol
from uuid import UUID

from app.domain.entities.ticket import SeguimientoTicket, Ticket
from app.domain.enums import EstadoTicket, PrioridadTicket
from app.domain.ports.analitica import ConteoEtiquetado, PuntoSerie
from app.domain.ports.repositorios import Pagina, Paginacion


@dataclass(frozen=True, slots=True)
class FiltroTickets:
    texto: str | None = None
    """Busqueda sobre el titulo y la descripcion del ticket."""
    estado: EstadoTicket | None = None
    solicitante_id: UUID | None = None
    asignado_a: UUID | None = None
    prioridad: PrioridadTicket | None = None
    categoria_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class VistaTicket:
    """Ticket con los nombres ya resueltos, para no golpear personas y
    usuarios fila por fila al listar o al abrir el detalle."""

    ticket: Ticket
    solicitante_nombre: str
    solicitante_unidad: str | None
    asignado_a_nombre: str | None
    creado_por_nombre: str | None
    categoria_nombre: str | None


@dataclass(frozen=True, slots=True)
class EstadisticasTickets:
    """Agregados del dashboard de soporte, acotados o no a un responsable.

    `asignado_a` en la consulta decide el alcance ("mis soportes" vs "todos");
    esta clase solo lleva el resultado ya filtrado.
    """

    total: int
    total_abiertos: int
    total_vencidos: int
    tiempo_promedio_resolucion_horas: float | None
    por_estado: list[ConteoEtiquetado] = field(default_factory=list)
    por_prioridad: list[ConteoEtiquetado] = field(default_factory=list)
    creados_por_dia: list[PuntoSerie] = field(default_factory=list)


class RepositorioTickets(Protocol):
    async def obtener(self, ticket_id: UUID) -> VistaTicket | None: ...

    async def listar(
        self, filtro: FiltroTickets, paginacion: Paginacion
    ) -> Pagina[VistaTicket]: ...

    async def agregar(self, ticket: Ticket) -> Ticket: ...

    async def actualizar(self, ticket: Ticket) -> Ticket: ...

    async def listar_seguimientos(self, ticket_id: UUID) -> list[SeguimientoTicket]: ...

    async def agregar_seguimiento(self, seguimiento: SeguimientoTicket) -> SeguimientoTicket: ...

    async def estadisticas(
        self, *, asignado_a: UUID | None, desde: date, hasta: date
    ) -> EstadisticasTickets: ...
