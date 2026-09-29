"""Entidades del modulo de tickets: solicitudes de soporte tecnico de las
facultades a Vicerrectorado, con su tabla de seguimiento."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4

from app.domain.enums import EstadoTicket
from app.domain.value_objects import ahora_utc


@dataclass(slots=True)
class Ticket:
    """Un caso de soporte. El solicitante es siempre una `Persona`."""

    titulo: str
    descripcion: str
    solicitante_id: UUID
    estado: EstadoTicket = EstadoTicket.RECIBIDO
    asignado_a: UUID | None = None
    """Usuario de soporte responsable. `None` mientras nadie lo ha tomado."""

    id: UUID = field(default_factory=uuid4)
    creado_por: UUID | None = None
    creado_en: datetime = field(default_factory=ahora_utc)
    actualizado_en: datetime = field(default_factory=ahora_utc)

    def cambiar_estado(self, nuevo: EstadoTicket, *, momento: datetime | None = None) -> None:
        self.estado = nuevo
        self.actualizado_en = momento or ahora_utc()

    def asignar(self, usuario_id: UUID | None, *, momento: datetime | None = None) -> None:
        self.asignado_a = usuario_id
        self.actualizado_en = momento or ahora_utc()


@dataclass(slots=True)
class SeguimientoTicket:
    """Un paso de la tabla de seguimiento: un comentario y, opcionalmente, un
    cambio de estado registrado en el mismo movimiento."""

    ticket_id: UUID
    autor_id: UUID | None
    comentario: str
    estado_anterior: EstadoTicket | None = None
    estado_nuevo: EstadoTicket | None = None

    id: UUID = field(default_factory=uuid4)
    creado_en: datetime = field(default_factory=ahora_utc)

    @property
    def hubo_cambio_de_estado(self) -> bool:
        return self.estado_nuevo is not None and self.estado_nuevo != self.estado_anterior
