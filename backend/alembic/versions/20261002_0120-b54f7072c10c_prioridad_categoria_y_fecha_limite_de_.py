"""prioridad, categoria y fecha limite de ticket

Acerca el modulo de tickets a un ServiceDesk: prioridad (enum libre, sin
columna de catalogo), categoria (catalogo administrable nuevo, como Facultad o
Carrera) y fecha limite (vencimiento declarado a mano, sin motor de SLA). Los
tres son opcionales: no se exige completarlos al crear el ticket.

ID de revision: b54f7072c10c
Revision anterior: 12281ec252eb
Fecha: 2026-10-02 01:20:08.807185+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b54f7072c10c"
down_revision: str | None = "12281ec252eb"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
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

    op.add_column("tickets", sa.Column("prioridad", sa.String(length=16), nullable=True))
    op.add_column("tickets", sa.Column("fecha_limite", sa.Date(), nullable=True))
    op.add_column("tickets", sa.Column("categoria_id", sa.UUID(), nullable=True))
    op.create_index("ix_tickets_categoria", "tickets", ["categoria_id"], unique=False)
    op.create_foreign_key(
        op.f("fk_tickets_categoria_id_cat_categorias_ticket"),
        "tickets",
        "cat_categorias_ticket",
        ["categoria_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("fk_tickets_categoria_id_cat_categorias_ticket"), "tickets", type_="foreignkey"
    )
    op.drop_index("ix_tickets_categoria", table_name="tickets")
    op.drop_column("tickets", "categoria_id")
    op.drop_column("tickets", "fecha_limite")
    op.drop_column("tickets", "prioridad")

    op.drop_index(
        "ix_cat_categorias_ticket_busqueda",
        table_name="cat_categorias_ticket",
        postgresql_using="gin",
        postgresql_ops={"clave_busqueda": "gin_trgm_ops"},
    )
    op.drop_index("ix_cat_categorias_ticket_activo_orden", table_name="cat_categorias_ticket")
    op.drop_table("cat_categorias_ticket")
