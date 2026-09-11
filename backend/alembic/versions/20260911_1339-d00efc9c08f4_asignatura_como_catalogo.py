"""asignatura como catalogo

La asignatura que imparte cada docente pasa de texto libre en `distributivo` a
un catalogo propio con clave foranea, como los otros doce.

El motivo es el de cualquier catalogo: escrita a mano en cientos de filas, la
misma materia acaba con tres grafias distintas, y corregirlas obliga a tocar
cada fila. Con el catalogo se corrige una vez y cambia en todas.

La migracion **conserva lo capturado**: crea un elemento por cada texto
distinto —comparando en mayusculas, para que «Calculo I» y «CALCULO I» no
queden como dos— y enlaza las filas antes de retirar la columna vieja. El
camino de vuelta rehace el texto desde el catalogo, asi que no se pierde nada
en ninguna direccion.

ID de revision: d00efc9c08f4
Revision anterior: 8081c4428f41
Fecha: 2026-09-11 13:39:22.795585+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "d00efc9c08f4"
down_revision: str | None = "8081c4428f41"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "cat_asignaturas",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("codigo", sa.String(length=320), nullable=False),
        sa.Column("nombre", sa.String(length=320), nullable=False),
        sa.Column("descripcion", sa.Text(), nullable=False),
        sa.Column("clave_busqueda", sa.Text(), nullable=False),
        sa.Column("activo", sa.Boolean(), nullable=False),
        sa.Column("orden", sa.Integer(), nullable=False),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_cat_asignaturas")),
        sa.UniqueConstraint("codigo", name="uq_cat_asignaturas_codigo"),
    )
    op.create_index(
        "ix_cat_asignaturas_activo_orden", "cat_asignaturas", ["activo", "orden"], unique=False
    )
    op.create_index(
        "ix_cat_asignaturas_busqueda",
        "cat_asignaturas",
        ["clave_busqueda"],
        unique=False,
        postgresql_using="gin",
        postgresql_ops={"clave_busqueda": "gin_trgm_ops"},
    )
    op.add_column("distributivo", sa.Column("asignatura_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        op.f("fk_distributivo_asignatura_id_cat_asignaturas"),
        "distributivo",
        "cat_asignaturas",
        ["asignatura_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # --- Se conserva lo que ya estaba capturado --------------------------
    # `normalizada` reproduce en SQL lo que hace la aplicacion con el texto:
    # recorta los extremos y colapsa los espacios interiores. Sin lo segundo,
    # «CALCULO  I» y «CALCULO I» quedarian como dos elementos distintos, que es
    # justo lo que el catalogo viene a evitar.
    op.execute(
        r"""
        INSERT INTO cat_asignaturas
               (codigo, nombre, descripcion, clave_busqueda, activo, orden, atributos)
        SELECT DISTINCT ON (upper(normalizada))
               upper(normalizada),
               normalizada,
               '',
               lower(unaccent(normalizada)),
               true, 0, '{}'::jsonb
          FROM (
                SELECT regexp_replace(btrim(asignatura), '\s+', ' ', 'g') AS normalizada
                  FROM distributivo
                 WHERE asignatura IS NOT NULL
               ) AS textos
         WHERE normalizada <> ''
         ORDER BY upper(normalizada)
        """
    )
    op.execute(
        r"""
        UPDATE distributivo AS d
           SET asignatura_id = c.id
          FROM cat_asignaturas AS c
         WHERE d.asignatura IS NOT NULL
           AND upper(regexp_replace(btrim(d.asignatura), '\s+', ' ', 'g')) = c.codigo
        """
    )

    op.drop_column("distributivo", "asignatura")


def downgrade() -> None:
    op.add_column(
        "distributivo",
        sa.Column("asignatura", sa.VARCHAR(length=400), autoincrement=False, nullable=True),
    )

    # Se rehace el texto desde el catalogo antes de soltar la clave foranea:
    # de otro modo la vuelta atras perderia todo lo capturado.
    op.execute(
        """
        UPDATE distributivo AS d
           SET asignatura = c.nombre
          FROM cat_asignaturas AS c
         WHERE d.asignatura_id = c.id
        """
    )

    op.drop_constraint(
        op.f("fk_distributivo_asignatura_id_cat_asignaturas"), "distributivo", type_="foreignkey"
    )
    op.drop_column("distributivo", "asignatura_id")
    op.drop_index(
        "ix_cat_asignaturas_busqueda",
        table_name="cat_asignaturas",
        postgresql_using="gin",
        postgresql_ops={"clave_busqueda": "gin_trgm_ops"},
    )
    op.drop_index("ix_cat_asignaturas_activo_orden", table_name="cat_asignaturas")
    op.drop_table("cat_asignaturas")
