"""Soporte para las pruebas de integracion.

Estas pruebas necesitan un PostgreSQL real: verifican justamente lo que los
dobles en memoria no pueden —SQL generado, restricciones, indices y
transacciones—. Si no hay base disponible se omiten en lugar de fallar, para
que `pytest` siga siendo util en una maquina sin Docker.

Para levantar una:

    docker run -d --name ute_pg_test -e POSTGRES_USER=ute \\
      -e POSTGRES_PASSWORD=ute -e POSTGRES_DB=ute_vice_test \\
      -p 55432:5432 postgres:18-alpine

**Estas pruebas borran y recrean el esquema entero.** Por eso solo corren contra
una base cuyo nombre termine en `_test`: con un `.env` de desarrollo cargado en
el entorno, `POSTGRES_DB` apunta a la base de trabajo y la bateria se la llevaria
por delante. Para forzarlo —en un contenedor efimero de CI, por ejemplo— se
define `PERMITIR_BASE_NO_TEST=1`.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio

pytestmark = pytest.mark.integration


def _configurar_entorno() -> None:
    """Fija las variables antes de que se construya la configuracion."""
    os.environ.setdefault("POSTGRES_HOST", "localhost")
    os.environ.setdefault("POSTGRES_PORT", "55432")
    os.environ.setdefault("POSTGRES_USER", "ute")
    os.environ.setdefault("POSTGRES_PASSWORD", "ute")
    os.environ.setdefault("POSTGRES_DB", "ute_vice_test")
    os.environ.setdefault("SECRET_KEY", "clave-de-pruebas-" + "x" * 50)
    os.environ.setdefault("ENVIRONMENT", "development")
    os.environ.setdefault("SENESCYT_PROVIDER", "mock")
    os.environ.setdefault("SCHEDULER_ENABLED", "false")

    # La politica de ritmo se niega a consultar fuera del horario configurado,
    # que es exactamente lo que debe hacer. Pero una prueba que solo pasa en
    # horario de oficina no es una prueba: se abre la ventana a las 24 horas
    # para que el resultado no dependa de cuando se ejecute la bateria.
    # El comportamiento horario se verifica aparte, con un reloj congelado,
    # en tests/unit/test_planificacion.py.
    os.environ.setdefault("SCHEDULER_PEAK_START_HOUR", "0")
    os.environ.setdefault("SCHEDULER_PEAK_END_HOUR", "23")
    os.environ.setdefault("SCHEDULER_OFFPEAK_END_HOUR", "23")
    os.environ.setdefault("SCHEDULER_MIN_DELAY_SECONDS", "1")
    os.environ.setdefault("SCHEDULER_MAX_DELAY_SECONDS", "2")


#: Se exige este sufijo para no destruir una base de desarrollo por accidente.
_SUFIJO_BASE_DE_PRUEBAS = "_test"


def _base_es_desechable() -> bool:
    """`True` si se puede borrar el esquema de la base configurada.

    Las pruebas hacen `drop_all` antes de cada modulo. Si `POSTGRES_DB` viene
    del entorno de desarrollo, eso destruye datos reales: ya paso.
    """
    if os.environ.get("PERMITIR_BASE_NO_TEST") == "1":
        return True
    return os.environ.get("POSTGRES_DB", "").endswith(_SUFIJO_BASE_DE_PRUEBAS)


async def _hay_base_de_datos() -> bool:
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    from app.core.config import get_settings

    try:
        motor = create_async_engine(get_settings().db.async_dsn)
        async with motor.connect() as conexion:
            await conexion.execute(text("SELECT 1"))
        await motor.dispose()
    except Exception:
        return False
    return True


@pytest_asyncio.fixture
async def base_disponible() -> bool:
    _configurar_entorno()
    from app.core.config import get_settings

    get_settings.cache_clear()
    if not _base_es_desechable():
        pytest.skip(
            f"POSTGRES_DB={os.environ.get('POSTGRES_DB')!r} no termina en "
            f"'{_SUFIJO_BASE_DE_PRUEBAS}'. Estas pruebas recrean el esquema "
            "entero: apunte a una base de pruebas o defina PERMITIR_BASE_NO_TEST=1."
        )
    return await _hay_base_de_datos()


@pytest_asyncio.fixture
async def esquema(base_disponible: bool) -> AsyncIterator[None]:
    """Recrea el esquema desde cero antes de cada prueba.

    Se usa `metadata.create_all` y no Alembic: la prueba verifica el
    comportamiento de la aplicacion, y la correccion de las migraciones se
    comprueba aparte en `test_migraciones.py`.
    """
    if not base_disponible:
        pytest.skip("no hay PostgreSQL disponible en localhost:55432")

    from app.core.config import get_settings

    # Importar los modelos es lo que puebla `Base.metadata`. Sin esta linea el
    # metadata esta vacio, `create_all` no crea nada, y la prueba solo funciona
    # si alguna anterior importo los modelos por su cuenta — es decir, depende
    # del orden de ejecucion. Es el mismo import explicito que hace alembic/env.py.
    from app.infrastructure.db import (
        modelos,  # noqa: F401
        modelos_distributivo,  # noqa: F401
    )
    from app.infrastructure.db.base import Base
    from app.infrastructure.db.sesion import crear_motor

    assert Base.metadata.tables, "el metadata quedo vacio: falta importar los modelos"

    motor = crear_motor(get_settings().db)
    async with motor.begin() as conexion:
        await conexion.run_sync(Base.metadata.drop_all)
        await conexion.run_sync(Base.metadata.create_all)
    await motor.dispose()

    yield

    motor = crear_motor(get_settings().db)
    async with motor.begin() as conexion:
        await conexion.run_sync(Base.metadata.drop_all)
    await motor.dispose()


@pytest_asyncio.fixture
async def app_y_cliente(esquema: None):  # type: ignore[no-untyped-def]
    """Aplicacion completa con un cliente HTTP en proceso."""
    import httpx

    from app.core.config import get_settings
    from app.main import crear_app

    aplicacion = crear_app(get_settings())
    transporte = httpx.ASGITransport(app=aplicacion)

    async with (
        aplicacion.router.lifespan_context(aplicacion),
        httpx.AsyncClient(transport=transporte, base_url="http://pruebas") as cliente,
    ):
        yield aplicacion, cliente


@pytest_asyncio.fixture
async def sembrado(app_y_cliente):  # type: ignore[no-untyped-def]
    """Permisos, roles y superusuario, listos para autenticar."""
    from sqlalchemy import select

    from app.core.config import get_settings
    from app.domain.entities.auth import Usuario
    from app.domain.enums import PERMISOS_POR_ROL, Permiso, RolCodigo
    from app.domain.value_objects import Email
    from app.infrastructure.contenedor import Contenedor
    from app.infrastructure.db.modelos import PermisoModel, RolModel

    aplicacion, cliente = app_y_cliente
    contenedor: Contenedor = aplicacion.state.contenedor

    async with contenedor.fabrica_sesiones() as sesion:
        for permiso in Permiso:
            modulo, accion = permiso.value.split(":", 1)
            sesion.add(
                PermisoModel(
                    codigo=permiso.value,
                    nombre=f"{accion} {modulo}",
                    modulo=modulo,
                )
            )
        await sesion.flush()

        catalogo = {
            fila.codigo: fila for fila in (await sesion.scalars(select(PermisoModel))).all()
        }
        for codigo, permisos in PERMISOS_POR_ROL.items():
            sesion.add(
                RolModel(
                    codigo=codigo.value,
                    nombre=codigo.value.capitalize(),
                    es_sistema=True,
                    permisos=[catalogo[p.value] for p in permisos],
                )
            )
        await sesion.commit()

    settings = get_settings()
    uow = contenedor.unidad_de_trabajo()
    async with uow:
        rol_admin = await uow.roles.obtener_por_codigo(RolCodigo.ADMIN.value)
        assert rol_admin is not None
        await uow.usuarios.agregar(
            Usuario(
                email=Email(settings.first_superuser_email),
                nombre_completo="Administrador",
                hash_contrasena=contenedor.hasher.hashear(settings.first_superuser_password),
                roles={rol_admin},
                es_superusuario=True,
            )
        )
        await uow.commit()

    return aplicacion, cliente


@pytest_asyncio.fixture
async def cabeceras_admin(sembrado):  # type: ignore[no-untyped-def]
    """Cabecera `Authorization` de una sesion de administrador."""
    from app.core.config import get_settings

    _, cliente = sembrado
    settings = get_settings()
    respuesta = await cliente.post(
        "/api/v1/auth/login",
        json={
            "email": settings.first_superuser_email,
            "contrasena": settings.first_superuser_password,
        },
    )
    assert respuesta.status_code == 200, respuesta.text
    return {"Authorization": f"Bearer {respuesta.json()['tokens']['acceso']}"}
