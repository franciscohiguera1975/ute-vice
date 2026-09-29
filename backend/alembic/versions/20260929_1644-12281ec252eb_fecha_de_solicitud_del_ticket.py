"""fecha de solicitud del ticket

Agrega `tickets.fecha_solicitud`: cuando se pidio el soporte, distinto de
`creado_en` (cuando quedo registrado). El registro suele ocurrir con retraso
frente al pedido real, y esa diferencia importa para medir tiempos de
respuesta.

Se agrega nullable, se rellena con la fecha de `creado_en` de cada fila
existente —la mejor aproximacion disponible, y coincide con el valor por
defecto que ya aplica el dominio al crear un ticket nuevo— y luego se marca
NOT NULL.

ID de revision: 12281ec252eb
Revision anterior: c499e8587e18
Fecha: 2026-09-29 16:44:23.153982+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "12281ec252eb"
down_revision: str | None = "c499e8587e18"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("tickets", sa.Column("fecha_solicitud", sa.Date(), nullable=True))
    op.execute("UPDATE tickets SET fecha_solicitud = creado_en::date WHERE fecha_solicitud IS NULL")
    op.alter_column("tickets", "fecha_solicitud", nullable=False)


def downgrade() -> None:
    op.drop_column("tickets", "fecha_solicitud")
