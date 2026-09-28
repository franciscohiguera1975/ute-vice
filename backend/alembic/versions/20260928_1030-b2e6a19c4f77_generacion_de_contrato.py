"""generacion de contrato

Tercera columna del sistema academico sobre el avance de la contratacion:
`Generación de contrato`, `SI` cuando la fila genera un contrato nuevo. Es lo
que distingue el flujo de contratacion -pasa ademas por Canciller y
Rector- de los otros dos flujos de aprobacion.

Revision ID: b2e6a19c4f77
Revises: a7c15f3e9d84
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "b2e6a19c4f77"
down_revision: str | None = "a7c15f3e9d84"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column("distributivo", sa.Column("generacion_contrato", sa.String(8), nullable=True))


def downgrade() -> None:
    op.drop_column("distributivo", "generacion_contrato")
