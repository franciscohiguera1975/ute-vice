"""alcance academico por usuario

Acota lo que cada cuenta puede consultar a un conjunto de facultades y de
carreras. Dos tablas de union en lugar de columnas: un usuario coordina varias
facultades a la vez, y varias carreras de facultades distintas.

Sin filas, la cuenta no queda restringida. Por eso la migracion no necesita
poblar nada: al aplicarla, todos los usuarios existentes siguen viendo lo mismo
que antes.

ID de revision: 8081c4428f41
Revision anterior: ae3efae2f274
Fecha: 2026-09-11 12:52:41.133852+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = '8081c4428f41'
down_revision: str | None = 'ae3efae2f274'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('usuario_carreras',
    sa.Column('usuario_id', sa.UUID(), nullable=False),
    sa.Column('carrera_id', sa.UUID(), nullable=False),
    sa.ForeignKeyConstraint(['carrera_id'], ['cat_carreras.id'], name=op.f('fk_usuario_carreras_carrera_id_cat_carreras'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['usuario_id'], ['usuarios.id'], name=op.f('fk_usuario_carreras_usuario_id_usuarios'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('usuario_id', 'carrera_id', name=op.f('pk_usuario_carreras'))
    )
    op.create_table('usuario_facultades',
    sa.Column('usuario_id', sa.UUID(), nullable=False),
    sa.Column('facultad_id', sa.UUID(), nullable=False),
    sa.ForeignKeyConstraint(['facultad_id'], ['cat_facultades.id'], name=op.f('fk_usuario_facultades_facultad_id_cat_facultades'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['usuario_id'], ['usuarios.id'], name=op.f('fk_usuario_facultades_usuario_id_usuarios'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('usuario_id', 'facultad_id', name=op.f('pk_usuario_facultades'))
    )


def downgrade() -> None:
    op.drop_table('usuario_facultades')
    op.drop_table('usuario_carreras')
