"""Verifica que las migraciones describen el esquema real de la aplicacion.

Una migracion que se desincroniza de los modelos es una bomba de relojeria: todo
funciona en desarrollo —donde el esquema se creo con `create_all`— y falla al
desplegar. Esta prueba lo detecta antes.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


async def test_las_migraciones_reproducen_el_esquema_de_los_modelos(
    base_disponible: bool,
) -> None:
    """Aplica las migraciones y compara el resultado contra los modelos.

    Si esta prueba falla, falta generar una migracion:

        make migration m="descripcion del cambio"
    """
    if not base_disponible:
        pytest.skip("no hay PostgreSQL disponible")

    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext

    from app.core.config import get_settings

    # Puebla `Base.metadata`: sin este import la comparacion se haria contra un
    # metadata vacio y la prueba pasaria sin verificar nada.
    from app.infrastructure.db import (
        modelos,  # noqa: F401
        modelos_distributivo,  # noqa: F401
    )
    from app.infrastructure.db.base import Base
    from app.infrastructure.db.sesion import crear_motor

    assert Base.metadata.tables, "el metadata quedo vacio: falta importar los modelos"

    motor = crear_motor(get_settings().db)

    # Se parte de un esquema limpio construido desde los modelos y se comprueba
    # que no queden diferencias pendientes de migrar.
    async with motor.begin() as conexion:
        await conexion.run_sync(Base.metadata.drop_all)
        await conexion.run_sync(Base.metadata.create_all)

    def _diferencias(conexion) -> list:  # type: ignore[no-untyped-def]
        contexto = MigrationContext.configure(
            conexion,
            opts={"compare_type": True, "target_metadata": Base.metadata},
        )
        return compare_metadata(contexto, Base.metadata)

    async with motor.connect() as conexion:
        diferencias = await conexion.run_sync(_diferencias)

    async with motor.begin() as conexion:
        await conexion.run_sync(Base.metadata.drop_all)
    await motor.dispose()

    assert not diferencias, "Los modelos y el esquema no coinciden:\n  - " + "\n  - ".join(
        str(d) for d in diferencias
    )
