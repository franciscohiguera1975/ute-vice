"""varias asignaturas por fila

Un docente dicta mas de una materia en la misma carrera y periodo. El
consolidado no las distingue —reparte horas por tipo de actividad, no por
materia— asi que la fila sigue siendo una sola y las asignaturas pasan a ser
varias: la columna se convierte en tabla de union, con `orden` para conservar
como se escribieron.

Ese orden es el que despues sale en la celda «Asignatura que imparte» del
reporte, donde las materias van separadas por comas.

La migracion **conserva lo enlazado** en las dos direcciones. La vuelta atras
tiene un limite inevitable: la columna admite una sola asignatura, asi que de
las filas con varias se queda con la primera. Se avisa aqui porque no hay forma
de que no pase.

ID de revision: e0bca8427c85
Revision anterior: 172e2acc6b3f
Fecha: 2026-09-12 00:09:46.728239+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "e0bca8427c85"
down_revision: str | None = "172e2acc6b3f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "distributivo_asignaturas",
        sa.Column("fila_id", sa.UUID(), nullable=False),
        sa.Column("asignatura_id", sa.UUID(), nullable=False),
        sa.Column("orden", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["asignatura_id"],
            ["cat_asignaturas.id"],
            name=op.f("fk_distributivo_asignaturas_asignatura_id_cat_asignaturas"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["fila_id"],
            ["distributivo.id"],
            name=op.f("fk_distributivo_asignaturas_fila_id_distributivo"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "fila_id", "asignatura_id", name=op.f("pk_distributivo_asignaturas")
        ),
    )
    # Lo ya enlazado pasa a la tabla nueva antes de soltar la columna.
    op.execute(
        """
        INSERT INTO distributivo_asignaturas (fila_id, asignatura_id, orden)
        SELECT id, asignatura_id, 0
          FROM distributivo
         WHERE asignatura_id IS NOT NULL
        """
    )

    op.drop_constraint(
        op.f("fk_distributivo_asignatura_id_cat_asignaturas"), "distributivo", type_="foreignkey"
    )
    op.drop_column("distributivo", "asignatura_id")


def downgrade() -> None:
    op.add_column(
        "distributivo", sa.Column("asignatura_id", sa.UUID(), autoincrement=False, nullable=True)
    )
    op.create_foreign_key(
        op.f("fk_distributivo_asignatura_id_cat_asignaturas"),
        "distributivo",
        "cat_asignaturas",
        ["asignatura_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # La columna admite una sola: de las filas con varias se conserva la
    # primera. Es la perdida que se anuncia en la cabecera del archivo.
    op.execute(
        """
        UPDATE distributivo AS d
           SET asignatura_id = primera.asignatura_id
          FROM (
                SELECT DISTINCT ON (fila_id) fila_id, asignatura_id
                  FROM distributivo_asignaturas
                 ORDER BY fila_id, orden
               ) AS primera
         WHERE d.id = primera.fila_id
        """
    )

    op.drop_table("distributivo_asignaturas")
