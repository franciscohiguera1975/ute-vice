"""carrera y programa eran el mismo dato

El consolidado traia `CARRERA` y `CARRERA/PROGRAMA` como columnas distintas, y
la importacion creaba un catalogo para cada una. Comprobado sobre las 15.219
filas del historico, no eran dos datos: `programa` era `carrera` capitalizada.
Cada carrera apuntaba a exactamente un programa, y los tres programas que
apuntaban a varias carreras lo hacian por erratas del origen —«ARQUITECTURA» y
«ARQUITECTURA (R) - PRESENCIAL»—, no por decir cosas distintas.

Tener las dos obligaba a elegir entre ellas en cada formulario sin que la
eleccion significara nada. Queda `carrera`, que ademas es parte de la clave
natural de una fila y aquello a lo que apunta el alcance de los usuarios.

**Esta migracion pierde informacion a proposito**: la vuelta atras recrea la
tabla y la columna, pero vacias. Recuperar el contenido exige reimportar el
consolidado, que es de donde salia.

ID de revision: 172e2acc6b3f
Revision anterior: d00efc9c08f4
Fecha: 2026-09-11 16:21:37.082510+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "172e2acc6b3f"
down_revision: str | None = "d00efc9c08f4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Primero la referencia y despues la tabla: al reves, PostgreSQL se niega a
    # soltar `cat_programas` porque `distributivo` todavia apunta a ella.
    op.drop_constraint(
        op.f("fk_distributivo_programa_id_cat_programas"), "distributivo", type_="foreignkey"
    )
    op.drop_column("distributivo", "programa_id")

    op.drop_index(op.f("ix_cat_programas_activo_orden"), table_name="cat_programas")
    op.drop_index(
        op.f("ix_cat_programas_busqueda"),
        table_name="cat_programas",
        postgresql_ops={"clave_busqueda": "gin_trgm_ops"},
        postgresql_using="gin",
    )
    op.drop_table("cat_programas")


def downgrade() -> None:
    # La vuelta atras recrea la estructura, no el contenido: el dato vivia en
    # el consolidado y de alli hay que reimportarlo.
    # La tabla primero: la clave foranea no se puede crear apuntando a algo
    # que todavia no existe.
    op.create_table(
        "cat_programas",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column("codigo", sa.VARCHAR(length=320), autoincrement=False, nullable=False),
        sa.Column("nombre", sa.VARCHAR(length=320), autoincrement=False, nullable=False),
        sa.Column("descripcion", sa.TEXT(), autoincrement=False, nullable=False),
        sa.Column("clave_busqueda", sa.TEXT(), autoincrement=False, nullable=False),
        sa.Column("activo", sa.BOOLEAN(), autoincrement=False, nullable=False),
        sa.Column("orden", sa.INTEGER(), autoincrement=False, nullable=False),
        sa.Column(
            "atributos",
            postgresql.JSONB(astext_type=sa.Text()),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column(
            "creado_en",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column(
            "actualizado_en",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            autoincrement=False,
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_cat_programas")),
        sa.UniqueConstraint(
            "codigo",
            name=op.f("uq_cat_programas_codigo"),
            postgresql_include=[],
            postgresql_nulls_not_distinct=False,
        ),
    )
    op.create_index(
        op.f("ix_cat_programas_busqueda"),
        "cat_programas",
        ["clave_busqueda"],
        unique=False,
        postgresql_ops={"clave_busqueda": "gin_trgm_ops"},
        postgresql_using="gin",
    )
    op.create_index(
        op.f("ix_cat_programas_activo_orden"), "cat_programas", ["activo", "orden"], unique=False
    )

    op.add_column(
        "distributivo", sa.Column("programa_id", sa.UUID(), autoincrement=False, nullable=True)
    )
    op.create_foreign_key(
        op.f("fk_distributivo_programa_id_cat_programas"),
        "distributivo",
        "cat_programas",
        ["programa_id"],
        ["id"],
        ondelete="SET NULL",
    )
