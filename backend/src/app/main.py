"""Punto de entrada de la aplicacion FastAPI."""

from __future__ import annotations

import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from app.api.errores import registrar_manejadores
from app.api.esquemas.comunes import EstadoSalud
from app.api.v1 import router_v1
from app.core.config import Environment, Settings, get_settings
from app.core.logging import configurar_logging, get_logger, request_id_ctx, user_id_ctx
from app.infrastructure.contenedor import Contenedor
from app.infrastructure.planificador.ejecutor import EjecutorPlanificador

VERSION = "0.8.0"

log = get_logger(__name__)


@asynccontextmanager
async def ciclo_de_vida(app: FastAPI) -> AsyncIterator[None]:
    """Arranque y apagado ordenados.

    Construye el contenedor una sola vez y lo deja en el estado de la app; las
    dependencias lo leen de ahi. Al apagar, cierra el planificador antes que el
    motor de base de datos, para que ninguna consulta en curso se quede sin
    conexion a mitad de una transaccion.
    """
    settings: Settings = app.state.settings
    contenedor = Contenedor(settings)
    app.state.contenedor = contenedor

    log.info(
        "Iniciando %s v%s",
        settings.app_name,
        VERSION,
        extra=contenedor.resumen_configuracion(),
    )

    if settings.senescyt.provider.value == "mock" and settings.environment.is_production:
        log.warning(
            "SENESCYT_PROVIDER=mock en produccion: las consultas devuelven datos "
            "simulados. Configure un proveedor real."
        )

    planificador = EjecutorPlanificador(
        fabrica_avanzar=lambda: _fabricar_avanzar(contenedor),
        uow=contenedor.unidad_de_trabajo(),
        habilitado=settings.scheduler.enabled,
    )
    app.state.planificador = planificador
    await planificador.iniciar()

    try:
        yield
    finally:
        log.info("Apagando la aplicacion")
        await planificador.detener()
        await contenedor.cerrar()


def _fabricar_avanzar(contenedor: Contenedor):  # type: ignore[no-untyped-def]
    """Construye un `AvanzarJob` con una unidad de trabajo nueva.

    Cada paso del planificador usa su propia transaccion: si uno falla, no
    arrastra al siguiente.
    """
    from app.application.casos_uso.consultas import AvanzarJob

    return AvanzarJob(
        contenedor.unidad_de_trabajo(),
        contenedor.proveedor_titulos,
        contenedor.reconciliador,
        contenedor.politica_planificacion,
        contenedor.reloj,
    )


def crear_app(settings: Settings | None = None) -> FastAPI:
    """Fabrica de la aplicacion.

    Se expone como funcion —y no como un objeto global— para que las pruebas
    puedan construir una instancia con otra configuracion.
    """
    settings = settings or get_settings()
    configurar_logging(
        nivel=settings.log_level,
        json_output=settings.environment is not Environment.DEVELOPMENT,
    )

    app = FastAPI(
        title=settings.app_name,
        version=VERSION,
        description=(
            "API de gestion y validacion de titulos universitarios del personal "
            "de la Universidad Tecnologica Equinoccial.\n\n"
            "**Autenticacion:** token JWT en la cabecera `Authorization: Bearer <token>`.\n\n"
            "**Autorizacion:** por permisos individuales, no por rol. Cada endpoint "
            "declara el permiso que exige."
        ),
        lifespan=ciclo_de_vida,
        docs_url="/docs" if not settings.environment.is_production else None,
        redoc_url="/redoc" if not settings.environment.is_production else None,
        openapi_url="/openapi.json" if not settings.environment.is_production else None,
    )
    app.state.settings = settings

    _configurar_middleware(app, settings)
    registrar_manejadores(app)

    app.include_router(router_v1, prefix=settings.api_v1_prefix)
    _registrar_salud(app, settings)

    return app


def _configurar_middleware(app: FastAPI, settings: Settings) -> None:
    app.add_middleware(GZipMiddleware, minimum_size=1024)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Accept", "X-Request-ID"],
        expose_headers=["Content-Disposition", "Content-Length", "X-Request-ID"],
        max_age=600,
    )

    @app.middleware("http")
    async def correlacion(request: Request, siguiente):  # type: ignore[no-untyped-def]
        """Asigna un identificador a cada peticion y mide su duracion.

        El identificador viaja por `ContextVar`, de modo que cualquier log
        emitido durante la peticion queda correlacionado sin pasarlo por
        parametro, y se devuelve en la cabecera para que el usuario pueda
        citarlo al reportar un problema.
        """
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
        token_rid = request_id_ctx.set(request_id)
        token_uid = user_id_ctx.set(None)
        request.state.request_id = request_id

        inicio = time.perf_counter()
        try:
            respuesta: Response = await siguiente(request)
        finally:
            duracion_ms = (time.perf_counter() - inicio) * 1000
            request_id_ctx.reset(token_rid)
            user_id_ctx.reset(token_uid)

        respuesta.headers["X-Request-ID"] = request_id
        respuesta.headers["X-Response-Time-ms"] = f"{duracion_ms:.1f}"

        # Se registran solo las peticiones lentas o fallidas: registrar todas
        # ahoga los logs y esconde justamente lo que interesa.
        if duracion_ms > 1000 or respuesta.status_code >= 500:
            log.warning(
                "Peticion atendida",
                extra={
                    "metodo": request.method,
                    "ruta": request.url.path,
                    "estado": respuesta.status_code,
                    "duracion_ms": round(duracion_ms, 1),
                },
            )
        return respuesta

    @app.middleware("http")
    async def cabeceras_seguridad(request: Request, siguiente):  # type: ignore[no-untyped-def]
        """Cabeceras de proteccion del navegador.

        La API devuelve JSON y archivos, nunca HTML interpretable, asi que la
        politica de contenido puede ser maximamente restrictiva.
        """
        respuesta: Response = await siguiente(request)
        respuesta.headers.setdefault("X-Content-Type-Options", "nosniff")
        respuesta.headers.setdefault("X-Frame-Options", "DENY")
        respuesta.headers.setdefault("Referrer-Policy", "no-referrer")
        respuesta.headers.setdefault(
            "Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'"
        )
        if settings.environment.is_production:
            respuesta.headers.setdefault(
                "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
            )
        return respuesta


def _registrar_salud(app: FastAPI, settings: Settings) -> None:
    @app.get("/health", response_model=EstadoSalud, tags=["Sistema"], summary="Estado del servicio")
    async def salud(request: Request) -> EstadoSalud:
        """Comprobacion de salud. La usa Docker y cualquier balanceador."""
        from sqlalchemy import text

        contenedor: Contenedor = request.app.state.contenedor
        estado_bd = "desconocido"
        try:
            async with contenedor.motor.connect() as conexion:
                await conexion.execute(text("SELECT 1"))
            estado_bd = "conectada"
        except Exception:
            estado_bd = "sin conexion"
            log.warning("La comprobacion de salud no alcanzo la base de datos")

        planificador: EjecutorPlanificador = request.app.state.planificador
        return EstadoSalud(
            estado="ok" if estado_bd == "conectada" else "degradado",
            version=VERSION,
            entorno=settings.environment.value,
            base_datos=estado_bd,
            proveedor_senescyt=contenedor.proveedor_titulos.nombre,
            planificador_activo=planificador.esta_activo,
        )

    @app.get("/", include_in_schema=False)
    async def raiz() -> dict[str, str]:
        return {
            "servicio": settings.app_name,
            "version": VERSION,
            "documentacion": "/docs" if not settings.environment.is_production else "no disponible",
            "salud": "/health",
        }


app = crear_app()
