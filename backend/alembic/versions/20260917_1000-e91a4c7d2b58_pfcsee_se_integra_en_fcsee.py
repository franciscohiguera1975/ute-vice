"""pfcsee se integra en fcsee

El sistema academico nuevo ya no distingue los posgrados de ciencias de la salud
como unidad aparte: sus docentes figuran bajo *Ciencias de la Salud Eugenio
Espejo*. Se comprobo por cedula contra el distributivo oficial de 2026-1: de los
docentes de `PFCSEE` que aparecen alli, el 100% esta en esa facultad.

El cambio se aplica **solo a 2026-1 en adelante**. Las 1.775 filas historicas de
`PFCSEE` no se tocan: el distributivo es un registro, y reescribir 2020-2025 para
que se parezca a la estructura de 2026 haria irreproducibles los informes ya
emitidos.

`PFCSEE` queda **inactiva, no eliminada**. Deja de ofrecerse en los selectores y
conserva su historia.

**Sobre la reversibilidad.** La facultad anterior no se puede deducir despues del
cambio: `FCSEE` ya tiene filas con las mismas carreras —endodoncia, psiquiatria,
odontologia— cargadas por otra via. Por eso se guardan los identificadores en
`distributivo_facultad_previa`, que ademas deja constancia de que esas filas
pertenecieron a otra unidad. La vuelta atras los lee y descarta la tabla.

Revision ID: e91a4c7d2b58
Revises: d5c8e2f41a37
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "e91a4c7d2b58"
down_revision: str | None = "d5c8e2f41a37"
branch_labels: str | None = None
depends_on: str | None = None

_ORIGEN = "PFCSEE"
_DESTINO = "FCSEE"
#: Los dos digitos centrales del codigo del periodo son el anio; `26` en adelante.
_DESDE_ANIO = 26


def upgrade() -> None:
    conexion = op.get_bind()

    op.create_table(
        "distributivo_facultad_previa",
        sa.Column("fila_id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("facultad_codigo", sa.String(length=320), nullable=False),
        sa.Column("movida_en", sa.DateTime(timezone=True), server_default=sa.func.now()),
        comment=(
            "Filas cuya facultad se reasigno al integrarse una unidad en otra. "
            "Existe para poder deshacerlo: la facultad previa no es deducible del dato."
        ),
    )

    conexion.execute(
        sa.text(
            """
            INSERT INTO distributivo_facultad_previa (fila_id, facultad_codigo)
            SELECT d.id, f.codigo
            FROM distributivo d
            JOIN cat_paos p ON p.id = d.pao_id
            JOIN cat_facultades f ON f.id = d.facultad_id
            WHERE f.codigo = :origen
              AND substring(p.codigo from 1 for 2)::int >= :anio
            """
        ),
        {"origen": _ORIGEN, "anio": _DESDE_ANIO},
    )

    conexion.execute(
        sa.text(
            """
            UPDATE distributivo d
            SET facultad_id = (SELECT id FROM cat_facultades WHERE codigo = :destino)
            WHERE d.id IN (SELECT fila_id FROM distributivo_facultad_previa)
            """
        ),
        {"destino": _DESTINO},
    )

    # Se desactiva, no se borra: hay 1.775 filas historicas apuntando a ella.
    conexion.execute(
        sa.text("UPDATE cat_facultades SET activo = false WHERE codigo = :origen"),
        {"origen": _ORIGEN},
    )


def downgrade() -> None:
    conexion = op.get_bind()

    conexion.execute(
        sa.text(
            """
            UPDATE distributivo d
            SET facultad_id = (SELECT id FROM cat_facultades WHERE codigo = v.facultad_codigo)
            FROM distributivo_facultad_previa v
            WHERE v.fila_id = d.id
            """
        )
    )
    conexion.execute(
        sa.text("UPDATE cat_facultades SET activo = true WHERE codigo = :origen"),
        {"origen": _ORIGEN},
    )
    op.drop_table("distributivo_facultad_previa")
