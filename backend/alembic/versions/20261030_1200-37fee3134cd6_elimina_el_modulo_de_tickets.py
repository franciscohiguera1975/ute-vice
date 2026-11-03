"""elimina el modulo de tickets

El modulo de tickets (mesa de soporte tecnico) se extrajo a un proyecto
independiente, `ute-tickets`, con su propio backend/frontend y su propia
identidad de usuarios. El historico (8 tickets, 15 seguimientos en
produccion al momento de este cambio) ya fue migrado ahi.

Se eliminan, en orden de dependencia: `ticket_seguimientos`, `tickets`,
`cat_categorias_ticket` (vacia en produccion: el catalogo nunca se uso).
Tambien se limpian los permisos `tickets:leer/escribir/administrar` y el rol
`SOPORTE_TECNICO` (sin usuarios asignados en produccion al momento de este
cambio) para que no queden huerfanos en las tablas de autorizacion.

No se toca `personas.facultad_id`/`carrera_id`: aunque se agregaron en la
migracion original del modulo de tickets, hoy las usan el distributivo, la
matricula estudiantil y el tablero docente. Son de esas tablas, no de esta.

ID de revision: 37fee3134cd6
Revision anterior: c4659df6db4c
Fecha: 2026-10-30 12:00:00.000000+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "37fee3134cd6"
down_revision: str | None = "c4659df6db4c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PERMISOS_TICKET = ("tickets:leer", "tickets:escribir", "tickets:administrar")


def upgrade() -> None:
    # --- Autorizacion: limpiar lo que ya no tiene codigo que lo respalde ---
    # Las FK de rol_permisos/usuario_roles tienen ON DELETE CASCADE, asi que
    # esto tambien retira el vinculo de ADMIN con los permisos de tickets.
    op.execute(
        sa.text("delete from roles where codigo = 'SOPORTE_TECNICO'")
    )
    op.execute(
        sa.text("delete from permisos where codigo = any(:codigos)").bindparams(
            codigos=list(_PERMISOS_TICKET)
        )
    )

    # --- Tablas del modulo, en orden de dependencia ---
    op.drop_index("ix_ticket_seguimientos_ticket", table_name="ticket_seguimientos")
    op.drop_table("ticket_seguimientos")

    op.drop_index("ix_tickets_categoria", table_name="tickets")
    op.drop_index("ix_tickets_solicitante", table_name="tickets")
    op.drop_index("ix_tickets_estado", table_name="tickets")
    op.drop_index("ix_tickets_asignado", table_name="tickets")
    op.drop_table("tickets")

    op.drop_index(
        "ix_cat_categorias_ticket_busqueda",
        table_name="cat_categorias_ticket",
        postgresql_using="gin",
        postgresql_ops={"clave_busqueda": "gin_trgm_ops"},
    )
    op.drop_index("ix_cat_categorias_ticket_activo_orden", table_name="cat_categorias_ticket")
    op.drop_table("cat_categorias_ticket")


def downgrade() -> None:
    op.create_table(
        "cat_categorias_ticket",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("codigo", sa.String(length=320), nullable=False),
        sa.Column("nombre", sa.String(length=320), nullable=False),
        sa.Column("descripcion", sa.Text(), nullable=False),
        sa.Column("clave_busqueda", sa.Text(), nullable=False),
        sa.Column("activo", sa.Boolean(), nullable=False),
        sa.Column("orden", sa.Integer(), nullable=False),
        sa.Column("codigo_erp", sa.String(length=64), nullable=False),
        sa.Column("atributos", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "creado_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "actualizado_en",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_cat_categorias_ticket")),
        sa.UniqueConstraint("codigo", name="uq_cat_categorias_ticket_codigo"),
    )
    op.create_index(
        "ix_cat_categorias_ticket_activo_orden",
        "cat_categorias_ticket",
        ["activo", "orden"],
        unique=False,
    )
    op.create_index(
        "ix_cat_categorias_ticket_busqueda",
        "cat_categorias_ticket",
        ["clave_busqueda"],
        unique=False,
        postgresql_using="gin",
        postgresql_ops={"clave_busqueda": "gin_trgm_ops"},
    )

    op.create_table(
        "tickets",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("titulo", sa.String(length=200), nullable=False),
        sa.Column("descripcion", sa.Text(), nullable=False),
        sa.Column("estado", sa.String(length=24), nullable=False),
        sa.Column("solicitante_id", sa.UUID(), nullable=False),
        sa.Column("asignado_a", sa.UUID(), nullable=True),
        sa.Column("creado_por", sa.UUID(), nullable=True),
        sa.Column("fecha_solicitud", sa.Date(), nullable=False),
        sa.Column("prioridad", sa.String(length=16), nullable=True),
        sa.Column("fecha_limite", sa.Date(), nullable=True),
        sa.Column("categoria_id", sa.UUID(), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["solicitante_id"], ["personas.id"], name=op.f("fk_tickets_solicitante_id_personas")
        ),
        sa.ForeignKeyConstraint(
            ["categoria_id"],
            ["cat_categorias_ticket.id"],
            name=op.f("fk_tickets_categoria_id_cat_categorias_ticket"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tickets")),
    )
    op.create_index("ix_tickets_asignado", "tickets", ["asignado_a"], unique=False)
    op.create_index("ix_tickets_estado", "tickets", ["estado"], unique=False)
    op.create_index("ix_tickets_solicitante", "tickets", ["solicitante_id"], unique=False)
    op.create_index("ix_tickets_categoria", "tickets", ["categoria_id"], unique=False)

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

    # Los permisos y el rol SOPORTE_TECNICO no se re-crean aqui: si tambien se
    # revierte el codigo, el siguiente `python -m app.cli seed` los repone
    # (agrega los permisos que falten y re-sincroniza los roles del sistema).
