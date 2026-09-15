"""rol de consulta del distributivo

Un rol de solo lectura mas estrecho que `CONSULTA`: ve el distributivo y sus
catalogos, y emite los reportes, pero no llega a personas, titulos ni consultas
al SENESCYT. Es para quien revisa la carga docente sin necesitar el expediente
de cada persona.

No lleva `DISTRIBUTIVO_ESCRIBIR` ni `CATALOGOS_ESCRIBIR`. Sin ellos la interfaz
oculta los botones de alta, edicion y borrado —el menu y las acciones se
gobiernan por permiso— y el backend rechaza la operacion aunque alguien llame
al endpoint directamente.

`seed` ya crea el rol en una base nueva; esta migracion lo agrega a las que ya
existen. Es idempotente: si el rol ya esta, solo completa sus permisos.

Revision ID: b8d3f1a29e64
Revises: c47a1e3b8d52
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "b8d3f1a29e64"
down_revision: str | None = "c47a1e3b8d52"
branch_labels: str | None = None
depends_on: str | None = None

_CODIGO = "CONSULTA_DISTRIBUTIVO"
_NOMBRE = "Consulta del distributivo"
_DESCRIPCION = "Consulta del distributivo y sus catalogos, con emision de reportes"
_PERMISOS = ("distributivo:leer", "catalogos:leer", "reportes:generar")


def upgrade() -> None:
    conexion = op.get_bind()

    conexion.execute(
        sa.text(
            """
            INSERT INTO roles (id, codigo, nombre, descripcion, es_sistema)
            VALUES (gen_random_uuid(), :codigo, :nombre, :descripcion, true)
            ON CONFLICT (codigo) DO NOTHING
            """
        ),
        {"codigo": _CODIGO, "nombre": _NOMBRE, "descripcion": _DESCRIPCION},
    )

    # Los permisos ya existen: los siembra `seed` con el resto del catalogo. Si
    # alguno faltara, el INSERT no encontraria su id y el rol quedaria corto, asi
    # que se comprueba en vez de suponerlo.
    for permiso in _PERMISOS:
        encontrado = conexion.execute(
            sa.text("SELECT 1 FROM permisos WHERE codigo = :codigo"), {"codigo": permiso}
        ).scalar()
        if not encontrado:
            raise RuntimeError(
                f"Falta el permiso {permiso!r}. Ejecute `python -m app.cli seed` antes de migrar."
            )

    conexion.execute(
        sa.text(
            """
            INSERT INTO rol_permisos (rol_id, permiso_id)
            SELECT r.id, p.id
            FROM roles r, permisos p
            WHERE r.codigo = :rol AND p.codigo = ANY(:permisos)
            ON CONFLICT DO NOTHING
            """
        ),
        {"rol": _CODIGO, "permisos": list(_PERMISOS)},
    )


def downgrade() -> None:
    conexion = op.get_bind()
    # Primero los vinculos de usuario: dejar un usuario sin ningun rol es
    # preferible a dejar una fila apuntando a un rol que ya no existe.
    conexion.execute(
        sa.text(
            "DELETE FROM usuario_roles WHERE rol_id IN (SELECT id FROM roles WHERE codigo = :c)"
        ),
        {"c": _CODIGO},
    )
    conexion.execute(
        sa.text(
            "DELETE FROM rol_permisos WHERE rol_id IN (SELECT id FROM roles WHERE codigo = :c)"
        ),
        {"c": _CODIGO},
    )
    conexion.execute(sa.text("DELETE FROM roles WHERE codigo = :c"), {"c": _CODIGO})
