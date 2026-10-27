"""cargo directivo del docente

Agrega el catorceavo catalogo del distributivo: `cat_cargos_directivos`
(Decano, Director de Carrera, Vicerrector, ...). Es administrable como los
otros trece —la institucion define sus propios cargos desde la pantalla de
catalogos, sin tocar codigo—, y existe para que el Tablero Docente pueda
excluir a los directivos de la pestana "Mas horas": un docente con cargo
directivo no compite por horas de la misma forma que el resto.

La asignacion es deliberadamente simple: una clave foranea nullable mas en
`distributivo`, igual que `titularidad_id` o `categoria_id`, y no una tabla de
relacion aparte. El unico uso de hoy es un filtro booleano —tiene cargo
directivo o no—, no una lista de cargos simultaneos; si eso cambia, se amplia
entonces.

ID de revision: c4659df6db4c
Revision anterior: de8cdc0be23e
Fecha: 2026-10-27 15:00:00+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c4659df6db4c"
down_revision: str | None = "de8cdc0be23e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "cat_cargos_directivos",
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_cat_cargos_directivos")),
        sa.UniqueConstraint("codigo", name="uq_cat_cargos_directivos_codigo"),
    )
    op.create_index(
        "ix_cat_cargos_directivos_activo_orden",
        "cat_cargos_directivos",
        ["activo", "orden"],
        unique=False,
    )
    op.create_index(
        "ix_cat_cargos_directivos_busqueda",
        "cat_cargos_directivos",
        ["clave_busqueda"],
        unique=False,
        postgresql_using="gin",
        postgresql_ops={"clave_busqueda": "gin_trgm_ops"},
    )

    op.add_column("distributivo", sa.Column("cargo_directivo_id", sa.UUID(), nullable=True))
    op.create_index(
        "ix_distributivo_cargo_directivo_id", "distributivo", ["cargo_directivo_id"], unique=False
    )
    op.create_foreign_key(
        op.f("fk_distributivo_cargo_directivo_id_cat_cargos_directivos"),
        "distributivo",
        "cat_cargos_directivos",
        ["cargo_directivo_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("fk_distributivo_cargo_directivo_id_cat_cargos_directivos"),
        "distributivo",
        type_="foreignkey",
    )
    op.drop_index("ix_distributivo_cargo_directivo_id", table_name="distributivo")
    op.drop_column("distributivo", "cargo_directivo_id")

    op.drop_index(
        "ix_cat_cargos_directivos_busqueda",
        table_name="cat_cargos_directivos",
        postgresql_using="gin",
        postgresql_ops={"clave_busqueda": "gin_trgm_ops"},
    )
    op.drop_index("ix_cat_cargos_directivos_activo_orden", table_name="cat_cargos_directivos")
    op.drop_table("cat_cargos_directivos")
