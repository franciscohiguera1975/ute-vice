"""Modelos ORM del modulo de tickets de soporte tecnico."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, text
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base, MixinAuditoria


def _uuid_pk() -> Mapped[UUID]:
    return mapped_column(
        PgUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=text("gen_random_uuid()"),
    )


class TicketModel(Base, MixinAuditoria):
    __tablename__ = "tickets"
    __table_args__ = (
        Index("ix_tickets_estado", "estado"),
        Index("ix_tickets_solicitante", "solicitante_id"),
        Index("ix_tickets_asignado", "asignado_a"),
    )

    id: Mapped[UUID] = _uuid_pk()
    titulo: Mapped[str] = mapped_column(String(200), nullable=False)
    descripcion: Mapped[str] = mapped_column(Text, nullable=False)
    estado: Mapped[str] = mapped_column(String(24), default="RECIBIDO", nullable=False)

    # Sin `ondelete`: una persona con tickets no se puede borrar, igual que con
    # titulos (`EliminarPersona` ya exige el expediente vacio).
    solicitante_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("personas.id"), nullable=False
    )
    asignado_a: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("usuarios.id", ondelete="SET NULL")
    )
    creado_por: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("usuarios.id", ondelete="SET NULL")
    )


class SeguimientoTicketModel(Base):
    """Un paso de la tabla de seguimiento. Solo se inserta; nunca se edita."""

    __tablename__ = "ticket_seguimientos"
    __table_args__ = (Index("ix_ticket_seguimientos_ticket", "ticket_id", "creado_en"),)

    id: Mapped[UUID] = _uuid_pk()
    ticket_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False
    )
    autor_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("usuarios.id", ondelete="SET NULL")
    )
    comentario: Mapped[str] = mapped_column(Text, nullable=False)
    estado_anterior: Mapped[str | None] = mapped_column(String(24))
    estado_nuevo: Mapped[str | None] = mapped_column(String(24))
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
