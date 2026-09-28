"""estado de lote y de contrato

Dos columnas del sistema academico que no se leian: `Estado de Lote/Proceso`
—el avance de la contratacion administrativa, distinto de la validacion
academica que ya tenia `estado_validacion`— y `Estado de Contrato` —el estado
de la firma, casi siempre vacio hoy—.

No son un conjunto fijo de valores: se guardan como texto, igual que `fase`.

Revision ID: a7c15f3e9d84
Revises: f4a1c9d76e23
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "a7c15f3e9d84"
down_revision: str | None = "f4a1c9d76e23"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column("distributivo", sa.Column("estado_lote", sa.String(64), nullable=True))
    op.add_column("distributivo", sa.Column("estado_contrato", sa.String(64), nullable=True))
    op.create_index("ix_distributivo_estado_lote", "distributivo", ["estado_lote"])


def downgrade() -> None:
    op.drop_index("ix_distributivo_estado_lote", table_name="distributivo")
    op.drop_column("distributivo", "estado_contrato")
    op.drop_column("distributivo", "estado_lote")
