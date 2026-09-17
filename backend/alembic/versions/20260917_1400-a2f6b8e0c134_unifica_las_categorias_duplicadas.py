"""unifica las categorias duplicadas

La carga parcial de 2026-1 creo cuatro categorias que significan lo mismo que
las que ya existian, porque el sistema academico nuevo las escribe con el
prefijo «TITULAR»:

    TITULAR AUXILIAR    84  ->  AUXILIAR    3.586
    TITULAR PRINCIPAL   11  ->  PRINCIPAL     317
    TITULAR AGREGADO     9  ->  AGREGADO      424
    TITULAR AUXILIAR 1   1  ->  AUXILIAR

Las cuatro aparecen **solo en 2026-1**. El consolidado usa las formas cortas de
forma uniforme en los trece semestres, asi que un conteo por categoria salia
partido en dos grupos donde hay uno.

`TÉCNICO DOCENTE` tambien aparece solo en 2026-1, pero **no se toca**: es una
categoria real, presente tambien en el distributivo oficial.

## La tabla de valores previos

La fase anterior creo `distributivo_facultad_previa` para poder deshacer la
integracion de una facultad en otra. Esta migracion necesita lo mismo para las
categorias, asi que la tabla se generaliza a `distributivo_valor_previo`, con
una columna `campo` que dice de cual se trata. Evita una tabla por columna.

Los parametros van con `CAST(... AS varchar)`: reutilizar el mismo en dos
columnas hace que asyncpg no pueda deducir un tipo unico y falle con
`AmbiguousParameterError`. Ya paso en la migracion de los tres periodos.

Revision ID: a2f6b8e0c134
Revises: e91a4c7d2b58
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "a2f6b8e0c134"
down_revision: str | None = "e91a4c7d2b58"
branch_labels: str | None = None
depends_on: str | None = None

#: `duplicada -> equivalente`.
_EQUIVALENCIAS = {
    "TITULAR AUXILIAR": "AUXILIAR",
    "TITULAR AUXILIAR 1": "AUXILIAR",
    "TITULAR PRINCIPAL": "PRINCIPAL",
    "TITULAR AGREGADO": "AGREGADO",
}


def upgrade() -> None:
    conexion = op.get_bind()

    op.rename_table("distributivo_facultad_previa", "distributivo_valor_previo")
    op.alter_column("distributivo_valor_previo", "facultad_codigo", new_column_name="codigo_previo")
    op.add_column(
        "distributivo_valor_previo",
        sa.Column("campo", sa.String(length=32), nullable=False, server_default="facultad_id"),
    )
    op.alter_column("distributivo_valor_previo", "campo", server_default=None)
    # La clave deja de ser la fila: una misma fila puede tener guardados el
    # valor previo de la facultad y el de la categoria.
    op.drop_constraint("pk_distributivo_facultad_previa", "distributivo_valor_previo")
    op.create_primary_key(
        "pk_distributivo_valor_previo", "distributivo_valor_previo", ["fila_id", "campo"]
    )

    for duplicada, equivalente in _EQUIVALENCIAS.items():
        conexion.execute(
            sa.text(
                """
                INSERT INTO distributivo_valor_previo (fila_id, campo, codigo_previo)
                SELECT d.id, 'categoria_id', CAST(:duplicada AS varchar)
                FROM distributivo d
                JOIN cat_categorias c ON c.id = d.categoria_id
                WHERE c.codigo = CAST(:duplicada AS varchar)
                ON CONFLICT DO NOTHING
                """
            ),
            {"duplicada": duplicada},
        )
        conexion.execute(
            sa.text(
                """
                UPDATE distributivo d
                SET categoria_id = (
                    SELECT id FROM cat_categorias WHERE codigo = CAST(:equivalente AS varchar)
                )
                WHERE d.categoria_id = (
                    SELECT id FROM cat_categorias WHERE codigo = CAST(:duplicada AS varchar)
                )
                """
            ),
            {"duplicada": duplicada, "equivalente": equivalente},
        )

    # Ya sin filas apuntando a ellas, se pueden retirar del catalogo.
    conexion.execute(
        sa.text("DELETE FROM cat_categorias WHERE codigo = ANY(:codigos)"),
        {"codigos": list(_EQUIVALENCIAS)},
    )


def downgrade() -> None:
    conexion = op.get_bind()

    for duplicada in _EQUIVALENCIAS:
        conexion.execute(
            sa.text(
                """
                INSERT INTO cat_categorias (id, codigo, nombre, descripcion, clave_busqueda,
                                            activo, orden, atributos, codigo_erp)
                VALUES (gen_random_uuid(), CAST(:codigo AS varchar), CAST(:codigo AS varchar),
                        '', lower(CAST(:codigo AS varchar)), true, 0, '{}'::jsonb, '')
                ON CONFLICT (codigo) DO NOTHING
                """
            ),
            {"codigo": duplicada},
        )

    conexion.execute(
        sa.text(
            """
            UPDATE distributivo d
            SET categoria_id = (SELECT id FROM cat_categorias WHERE codigo = v.codigo_previo)
            FROM distributivo_valor_previo v
            WHERE v.fila_id = d.id AND v.campo = 'categoria_id'
            """
        )
    )
    conexion.execute(sa.text("DELETE FROM distributivo_valor_previo WHERE campo = 'categoria_id'"))

    op.drop_constraint("pk_distributivo_valor_previo", "distributivo_valor_previo")
    op.drop_column("distributivo_valor_previo", "campo")
    op.alter_column("distributivo_valor_previo", "codigo_previo", new_column_name="facultad_codigo")
    op.create_primary_key(
        "pk_distributivo_facultad_previa", "distributivo_valor_previo", ["fila_id"]
    )
    op.rename_table("distributivo_valor_previo", "distributivo_facultad_previa")
