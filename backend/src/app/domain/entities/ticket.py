"""Entidades del modulo de tickets: solicitudes de soporte tecnico de las
facultades a Vicerrectorado, con su tabla de seguimiento."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from uuid import UUID, uuid4

from app.domain.enums import EstadoTicket, PrioridadTicket
from app.domain.errors import ErrorValidacion
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

    fecha_solicitud: date = field(default_factory=lambda: ahora_utc().date())
    """Cuando se pidio el soporte, no cuando se registro el ticket.

    Nace igual a la fecha de creacion, pero es editable: el registro suele
    ocurrir con retraso frente al pedido real, y esa diferencia importa para
    medir tiempos de respuesta.
    """

    prioridad: PrioridadTicket | None = None
    """Urgencia del caso. Nula hasta que soporte la determina al triar."""

    categoria_id: UUID | None = None
    """Tipo de incidente, del catalogo administrable de categorias de ticket."""

    fecha_limite: date | None = None
    """Vencimiento declarado a mano, sin calculo automatico de SLA."""

    id: UUID = field(default_factory=uuid4)
    creado_por: UUID | None = None
    creado_en: datetime = field(default_factory=ahora_utc)
    actualizado_en: datetime = field(default_factory=ahora_utc)

    def __post_init__(self) -> None:
        self._validar_fecha_solicitud(self.fecha_solicitud)

    @staticmethod
    def _validar_fecha_solicitud(fecha: date) -> None:
        if fecha > ahora_utc().date():
            raise ErrorValidacion(
                "La fecha de solicitud no puede ser futura", campo="fecha_solicitud"
            )

    def cambiar_estado(self, nuevo: EstadoTicket, *, momento: datetime | None = None) -> None:
        self.estado = nuevo
        self.actualizado_en = momento or ahora_utc()

    def asignar(self, usuario_id: UUID | None, *, momento: datetime | None = None) -> None:
        self.asignado_a = usuario_id
        self.actualizado_en = momento or ahora_utc()

    def cambiar_fecha_solicitud(self, fecha: date, *, momento: datetime | None = None) -> None:
        self._validar_fecha_solicitud(fecha)
        self.fecha_solicitud = fecha
        self.actualizado_en = momento or ahora_utc()

    def actualizar_detalles(
        self,
        *,
        prioridad: PrioridadTicket | None = None,
        categoria_id: UUID | None = None,
        fecha_limite: date | None = None,
        momento: datetime | None = None,
    ) -> None:
        """Triage: prioridad, categoria y fecha limite, los tres opcionales.

        Se editan juntos porque en la practica se deciden en el mismo momento,
        al revisar el caso; no hay razon para exigir tres llamadas separadas.
        """
        self.prioridad = prioridad
        self.categoria_id = categoria_id
        self.fecha_limite = fecha_limite
        self.actualizado_en = momento or ahora_utc()

    @property
    def vencido(self) -> bool:
        """Paso la fecha limite y el caso sigue abierto.

        No hay motor de SLA con horas habiles ni escalamiento: es solo una
        comparacion de fechas para marcar visualmente lo que ya deberia estar
        resuelto.
        """
        if self.fecha_limite is None or self.estado.es_terminal:
            return False
        return self.fecha_limite < ahora_utc().date()


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
