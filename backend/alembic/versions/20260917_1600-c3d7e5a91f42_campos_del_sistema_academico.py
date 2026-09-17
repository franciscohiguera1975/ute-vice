"""campos del sistema academico

El distributivo oficial trae desde 2026-2 seis datos que el consolidado no
tenia. El que motivo el cambio es el **estado de la validacion**: dice si la
carga de un docente paso los controles del sistema academico, y con que
salvedad.

    OK                      707 filas de 2026-2
    Validacion Pendiente    371
    Ok, excepcion            70
    Error                    41

Los seis quedan **nulos en todo lo anterior a 2026-2**. Es deliberado: el dato
no existia, que no es lo mismo que estar sin validar. Un valor por defecto
—«pendiente», por ejemplo— afirmaria algo falso sobre trece semestres.

`semanas` distingue el interciclo del periodo ordinario mejor que cualquier
etiqueta: cuatro semanas frente a dieciseis.

Revision ID: c3d7e5a91f42
Revises: a2f6b8e0c134
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "c3d7e5a91f42"
down_revision: str | None = "a2f6b8e0c134"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column("distributivo", sa.Column("estado_validacion", sa.String(16), nullable=True))
    op.add_column("distributivo", sa.Column("fase", sa.String(32), nullable=True))
    op.add_column("distributivo", sa.Column("semanas", sa.Integer(), nullable=True))
    op.add_column("distributivo", sa.Column("relacion_laboral", sa.String(64), nullable=True))

    # Las marcas de tutoria si llevan defecto: «no es tutor» es afirmable de
    # cualquier fila, y evita tener que distinguir nulo de falso al contarlas.
    for columna in ("tutor_posgrado", "tutor_medicina"):
        op.add_column(
            "distributivo",
            sa.Column(columna, sa.Boolean(), nullable=False, server_default=sa.false()),
        )
        op.alter_column("distributivo", columna, server_default=None)

    # Consultar «que falta por validar» es la razon de existir de la columna.
    op.create_index(
        "ix_distributivo_estado_validacion",
        "distributivo",
        ["estado_validacion"],
        postgresql_where=sa.text("estado_validacion IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_distributivo_estado_validacion", table_name="distributivo")
    for columna in (
        "tutor_medicina",
        "tutor_posgrado",
        "relacion_laboral",
        "semanas",
        "fase",
        "estado_validacion",
    ):
        op.drop_column("distributivo", columna)
