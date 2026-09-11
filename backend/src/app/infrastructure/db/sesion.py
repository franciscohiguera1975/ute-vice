"""Motor y fabrica de sesiones asincronas."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import DatabaseSettings


def crear_motor(config: DatabaseSettings) -> AsyncEngine:
    """Crea el motor asincrono con el pool configurado.

    `pool_pre_ping` verifica la conexion antes de entregarla: sin el, una
    conexion cerrada por el servidor tras un periodo de inactividad —muy comun
    en un job que corre durante dias— falla la primera consulta que la use.
    """
    return create_async_engine(
        config.async_dsn,
        echo=config.echo_sql,
        pool_size=config.pool_size,
        max_overflow=config.max_overflow,
        pool_pre_ping=config.pool_pre_ping,
        pool_recycle=config.pool_recycle_seconds,
        future=True,
    )


def crear_fabrica_sesiones(motor: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(
        bind=motor,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )


@asynccontextmanager
async def sesion_transaccional(
    fabrica: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    """Sesion con confirmacion automatica al salir sin error."""
    async with fabrica() as sesion:
        try:
            yield sesion
            await sesion.commit()
        except Exception:
            await sesion.rollback()
            raise
