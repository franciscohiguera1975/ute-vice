"""grupo combinado en el distributivo

El sistema academico junta con comas cuando un docente dicta en varias
carreras, sedes o periodos a la vez, con un total de horas unico que no se
puede repartir entre ellas. Antes esas filas se rechazaban enteras; ahora se
explotan en una fila por combinacion, todas con la misma carga, y comparten
`grupo_combinado_id` para poder sumarla una sola vez al totalizar horas por
docente en lugar de por carrera o periodo.

Nulo en toda fila que no viene de una combinacion, que es casi todo el
historico.

Revision ID: f4a1c9d76e23
Revises: c3d7e5a91f42
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "f4a1c9d76e23"
down_revision: str | None = "c3d7e5a91f42"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "distributivo",
        sa.Column(
            "grupo_combinado_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True
        ),
    )
    op.create_index(
        "ix_distributivo_grupo_combinado_id",
        "distributivo",
        ["grupo_combinado_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_distributivo_grupo_combinado_id", table_name="distributivo")
    op.drop_column("distributivo", "grupo_combinado_id")
