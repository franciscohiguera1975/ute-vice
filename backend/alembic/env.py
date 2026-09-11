"""Entorno de migraciones de Alembic.

Corre en modo asincrono sobre el mismo driver que la aplicacion (asyncpg), en
lugar de exigir un driver sincrono adicional solo para migrar.

La URL sale de la configuracion tipada de la aplicacion, no del `alembic.ini`:
asi las credenciales viven en un unico lugar y no acaban versionadas.
"""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.core.config import get_settings

# Importar los modelos puebla `Base.metadata`, que es lo que compara el
# autogenerador. Si un modelo no se importa aqui, sus tablas no se detectan.
from app.infrastructure.db.base import Base
from app.infrastructure.db import modelos  # noqa: F401
from app.infrastructure.db import modelos_distributivo  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.db.async_dsn)


def incluir_objeto(objeto, nombre, tipo, reflejado, comparar_con):  # type: ignore[no-untyped-def]
    """Excluye del autogenerado lo que no gestionamos nosotros.

    Las extensiones de PostgreSQL las instala el script de inicializacion del
    contenedor; sus objetos no deben aparecer en las migraciones.
    """
    if tipo == "table" and nombre in {"spatial_ref_sys"}:
        return False
    return True


def ejecutar_migraciones(conexion: Connection) -> None:
    context.configure(
        connection=conexion,
        target_metadata=target_metadata,
        include_object=incluir_objeto,
        compare_type=True,
        compare_server_default=True,
        render_as_batch=False,
        transaction_per_migration=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def migrar_sin_conexion() -> None:
    """Modo offline: emite el SQL sin conectarse.

    Util para revisar los cambios antes de aplicarlos en produccion:
    `alembic upgrade head --sql > cambios.sql`
    """
    context.configure(
        url=settings.db.async_dsn.replace("+asyncpg", ""),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=incluir_objeto,
    )
    with context.begin_transaction():
        context.run_migrations()


async def migrar_con_conexion() -> None:
    motor = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with motor.connect() as conexion:
        await conexion.run_sync(ejecutar_migraciones)
    await motor.dispose()


if context.is_offline_mode():
    migrar_sin_conexion()
else:
    asyncio.run(migrar_con_conexion())
