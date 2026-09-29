"""modulo de tickets

Solicitudes de soporte tecnico de las facultades a Vicerrectorado: la tabla
`tickets` y su tabla de seguimiento `ticket_seguimientos`, mas dos columnas en
`personas` (`facultad_id`, `carrera_id`) para que el alta rapida de un
solicitante nuevo pueda referenciar los catalogos existentes del distributivo
en lugar de texto libre.

`personas.unidad` no se toca: sigue siendo el campo libre que ya usan otras
pantallas. Las columnas nuevas son un dato adicional, no un reemplazo.

ID de revision: c499e8587e18
Revision anterior: b2e6a19c4f77
Fecha: 2026-09-29 16:08:16.417386+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c499e8587e18"
down_revision: str | None = "b2e6a19c4f77"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "tickets",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("titulo", sa.String(length=200), nullable=False),
        sa.Column("descripcion", sa.Text(), nullable=False),
        sa.Column("estado", sa.String(length=24), nullable=False),
        sa.Column("solicitante_id", sa.UUID(), nullable=False),
        sa.Column("asignado_a", sa.UUID(), nullable=True),
        sa.Column("creado_por", sa.UUID(), nullable=True),
        sa.Column(
            "creado_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "actualizado_en",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["asignado_a"],
            ["usuarios.id"],
            name=op.f("fk_tickets_asignado_a_usuarios"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["creado_por"],
            ["usuarios.id"],
            name=op.f("fk_tickets_creado_por_usuarios"),
            ondelete="SET NULL",
        ),
        # Sin `ondelete`: una persona con tickets no se puede borrar, igual que
        # con titulos (`EliminarPersona` ya exige el expediente vacio).
        sa.ForeignKeyConstraint(
            ["solicitante_id"], ["personas.id"], name=op.f("fk_tickets_solicitante_id_personas")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tickets")),
    )
    op.create_index("ix_tickets_asignado", "tickets", ["asignado_a"], unique=False)
    op.create_index("ix_tickets_estado", "tickets", ["estado"], unique=False)
    op.create_index("ix_tickets_solicitante", "tickets", ["solicitante_id"], unique=False)

    op.create_table(
        "ticket_seguimientos",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("ticket_id", sa.UUID(), nullable=False),
        sa.Column("autor_id", sa.UUID(), nullable=True),
        sa.Column("comentario", sa.Text(), nullable=False),
        sa.Column("estado_anterior", sa.String(length=24), nullable=True),
        sa.Column("estado_nuevo", sa.String(length=24), nullable=True),
        sa.Column(
            "creado_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["autor_id"],
            ["usuarios.id"],
            name=op.f("fk_ticket_seguimientos_autor_id_usuarios"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["ticket_id"],
            ["tickets.id"],
            name=op.f("fk_ticket_seguimientos_ticket_id_tickets"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ticket_seguimientos")),
    )
    op.create_index(
        "ix_ticket_seguimientos_ticket", "ticket_seguimientos", ["ticket_id", "creado_en"], unique=False
    )

    op.add_column("personas", sa.Column("facultad_id", sa.UUID(), nullable=True))
    op.add_column("personas", sa.Column("carrera_id", sa.UUID(), nullable=True))
    op.create_index("ix_personas_facultad", "personas", ["facultad_id"], unique=False)
    op.create_index("ix_personas_carrera", "personas", ["carrera_id"], unique=False)
    op.create_foreign_key(
        op.f("fk_personas_facultad_id_cat_facultades"),
        "personas",
        "cat_facultades",
        ["facultad_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        op.f("fk_personas_carrera_id_cat_carreras"),
        "personas",
        "cat_carreras",
        ["carrera_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(op.f("fk_personas_carrera_id_cat_carreras"), "personas", type_="foreignkey")
    op.drop_constraint(op.f("fk_personas_facultad_id_cat_facultades"), "personas", type_="foreignkey")
    op.drop_index("ix_personas_carrera", table_name="personas")
    op.drop_index("ix_personas_facultad", table_name="personas")
    op.drop_column("personas", "carrera_id")
    op.drop_column("personas", "facultad_id")

    op.drop_index("ix_ticket_seguimientos_ticket", table_name="ticket_seguimientos")
    op.drop_table("ticket_seguimientos")

    op.drop_index("ix_tickets_solicitante", table_name="tickets")
    op.drop_index("ix_tickets_estado", table_name="tickets")
    op.drop_index("ix_tickets_asignado", table_name="tickets")
    op.drop_table("tickets")
