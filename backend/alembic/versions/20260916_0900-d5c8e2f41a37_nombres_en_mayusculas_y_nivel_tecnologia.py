"""nombres en mayusculas y nivel tecnologia

Tres correcciones sobre datos ya cargados.

**1. Los nombres van en mayusculas.** Convivian los que escribio alguien a mano
con los que generaba el importador en formato titulo, y la lista de un catalogo
mostraba «Posgrado» junto a «GRADO». La entidad lo impone ahora al construirse;
esta migracion alinea lo que ya estaba.

**2. La sede `MON` se llama `RICARDO HIDALGO OTTOLENGHI`.** Se llamaba «Monjas
(Ricardo Hidalgo Ottolenghi)», que no sale de ningun dato: el consolidado solo
escribe `MON`, `RHO` y `RICARDO HIDALGO OTTOLENGHI`. El «Monjas» era una
suposicion de quien escribio la tabla de nombres.

**3. Existe el nivel `TECNOLOGIA`.** El consolidado no lo conoce —sus filas de
`ETECH` y `UAEFTT` vienen etiquetadas como grado—, asi que el catalogo solo
tenia grado y posgrado. Las filas que estan en un periodo de tecnologia pasan a
declararlo tambien: decir «GRADO» dentro de «2026-1 TECNOLOGIA» es una
contradiccion que se veia en pantalla.

La vuelta atras deshace el nivel y el nombre de la sede. **Las mayusculas no se
revierten**: no se guarda como estaba escrito cada nombre antes, y reconstruirlo
con un formato titulo daria un texto distinto del original. Se deja constancia
aqui en lugar de fingir que es reversible.

Revision ID: d5c8e2f41a37
Revises: b8d3f1a29e64
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "d5c8e2f41a37"
down_revision: str | None = "b8d3f1a29e64"
branch_labels: str | None = None
depends_on: str | None = None

_TABLAS = (
    "cat_paos",
    "cat_facultades",
    "cat_carreras",
    "cat_sedes",
    "cat_titularidades",
    "cat_dedicaciones",
    "cat_categorias",
    "cat_niveles",
    "cat_titulos_profesionales",
    "cat_tipos_titulo",
    "cat_generos",
    "cat_asignaturas",
)


def upgrade() -> None:
    conexion = op.get_bind()

    for tabla in _TABLAS:
        conexion.execute(
            sa.text(f"UPDATE {tabla} SET nombre = upper(nombre) WHERE nombre <> upper(nombre)")
        )

    conexion.execute(
        sa.text("UPDATE cat_sedes SET nombre = 'RICARDO HIDALGO OTTOLENGHI' WHERE codigo = 'MON'")
    )

    conexion.execute(
        sa.text(
            """
            INSERT INTO cat_niveles (id, codigo, nombre, descripcion, clave_busqueda,
                                     activo, orden, atributos, codigo_erp)
            VALUES (gen_random_uuid(), 'TECNOLOGIA', 'TECNOLOGIA', '', 'tecnologia',
                    true, 2, '{}'::jsonb, '')
            ON CONFLICT (codigo) DO NOTHING
            """
        )
    )

    # Los tres digitos centrales del codigo del periodo nombran el nivel: `15`
    # es tecnologia. Se usa el periodo y no la facultad porque el periodo ya
    # incorpora la regla completa, decidida al importar.
    conexion.execute(
        sa.text(
            """
            UPDATE distributivo d
            SET nivel_id = (SELECT id FROM cat_niveles WHERE codigo = 'TECNOLOGIA')
            FROM cat_paos p
            WHERE p.id = d.pao_id AND substring(p.codigo from 4 for 2) = '15'
            """
        )
    )


def downgrade() -> None:
    conexion = op.get_bind()

    # Las filas de tecnologia vuelven a grado, que es como las etiquetaba el
    # consolidado antes de que existiera el nivel.
    conexion.execute(
        sa.text(
            """
            UPDATE distributivo d
            SET nivel_id = (SELECT id FROM cat_niveles WHERE codigo = 'GRADO')
            WHERE d.nivel_id = (SELECT id FROM cat_niveles WHERE codigo = 'TECNOLOGIA')
            """
        )
    )
    conexion.execute(sa.text("DELETE FROM cat_niveles WHERE codigo = 'TECNOLOGIA'"))
    conexion.execute(
        sa.text(
            "UPDATE cat_sedes SET nombre = 'Monjas (Ricardo Hidalgo Ottolenghi)' "
            "WHERE codigo = 'MON'"
        )
    )
