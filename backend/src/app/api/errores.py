"""Traduccion de errores de dominio a respuestas HTTP.

El dominio no conoce codigos de estado. Aqui, y solo aqui, se decide que un
`NoEncontrado` es un 404 y un `ErrorAutorizacion` un 403. Si mañana los casos de
uso se exponen tambien por MCP o por consola, cada canal hara su propia
traduccion sin tocar el negocio.

Todas las respuestas de error comparten forma, para que el frontend tenga un
unico contrato que interpretar:

    {"codigo": "no_encontrado", "mensaje": "...", "detalles": {...}, "request_id": "..."}
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.core.logging import get_logger, request_id_ctx
from app.domain.errors import (
    ConflictoDeEstado,
    DesafioRequerido,
    ErrorAutenticacion,
    ErrorAutorizacion,
    ErrorDominio,
    ErrorGeneracionReporte,
    ErrorProveedorExterno,
    ErrorValidacion,
    FueraDeAlcance,
    FueraDeVentanaOperativa,
    LimiteDeConsultasAlcanzado,
    NoEncontrado,
    ProveedorNoHabilitado,
    ReglaDeNegocioViolada,
    ReporteDemasiadoGrande,
    UsuarioBloqueado,
    UsuarioInactivo,
    YaExiste,
)

log = get_logger(__name__)

#: Correspondencia entre errores de dominio y codigos HTTP. El orden importa:
#: se busca la clase mas especifica primero.
_MAPA_ESTADOS: tuple[tuple[type[ErrorDominio], int], ...] = (
    (UsuarioBloqueado, status.HTTP_429_TOO_MANY_REQUESTS),
    (UsuarioInactivo, status.HTTP_403_FORBIDDEN),
    (ErrorAutenticacion, status.HTTP_401_UNAUTHORIZED),
    (FueraDeAlcance, status.HTTP_403_FORBIDDEN),
    (ErrorAutorizacion, status.HTTP_403_FORBIDDEN),
    (ProveedorNoHabilitado, status.HTTP_501_NOT_IMPLEMENTED),
    (NoEncontrado, status.HTTP_404_NOT_FOUND),
    (YaExiste, status.HTTP_409_CONFLICT),
    (ConflictoDeEstado, status.HTTP_409_CONFLICT),
    (ReporteDemasiadoGrande, status.HTTP_413_CONTENT_TOO_LARGE),
    (ErrorGeneracionReporte, status.HTTP_422_UNPROCESSABLE_CONTENT),
    (ErrorValidacion, status.HTTP_422_UNPROCESSABLE_CONTENT),
    (ReglaDeNegocioViolada, status.HTTP_422_UNPROCESSABLE_CONTENT),
    (LimiteDeConsultasAlcanzado, status.HTTP_429_TOO_MANY_REQUESTS),
    (FueraDeVentanaOperativa, status.HTTP_425_TOO_EARLY),
    (DesafioRequerido, status.HTTP_202_ACCEPTED),
    (ErrorProveedorExterno, status.HTTP_502_BAD_GATEWAY),
    (ErrorDominio, status.HTTP_400_BAD_REQUEST),
)


def _estado_de(error: ErrorDominio) -> int:
    for clase, estado in _MAPA_ESTADOS:
        if isinstance(error, clase):
            return estado
    return status.HTTP_400_BAD_REQUEST


def _cuerpo(codigo: str, mensaje: str, detalles: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "codigo": codigo,
        "mensaje": mensaje,
        "detalles": detalles or {},
        "request_id": request_id_ctx.get(),
    }


def registrar_manejadores(app: FastAPI) -> None:
    """Instala los manejadores de excepciones en la aplicacion."""

    @app.exception_handler(ErrorDominio)
    async def _dominio(request: Request, exc: ErrorDominio) -> JSONResponse:
        estado = _estado_de(exc)
        # Los errores de negocio son parte del funcionamiento normal: se
        # registran como aviso, no como fallo del sistema.
        log.info(
            "Error de dominio",
            extra={
                "codigo": exc.codigo,
                "estado": estado,
                "ruta": request.url.path,
            },
        )
        cabeceras: dict[str, str] = {}
        if isinstance(exc, ErrorAutenticacion):
            cabeceras["WWW-Authenticate"] = "Bearer"
        if isinstance(exc, UsuarioBloqueado):
            minutos = exc.detalles.get("minutos_restantes", 15)
            cabeceras["Retry-After"] = str(int(minutos) * 60)

        return JSONResponse(
            status_code=estado,
            content=_cuerpo(exc.codigo, exc.mensaje, exc.detalles),
            headers=cabeceras or None,
        )

    @app.exception_handler(RequestValidationError)
    async def _validacion(request: Request, exc: RequestValidationError) -> JSONResponse:
        """Normaliza los errores de Pydantic al mismo formato que el resto."""
        campos = [
            {
                "campo": ".".join(str(p) for p in error["loc"][1:]) or str(error["loc"][0]),
                "mensaje": error["msg"],
                "tipo": error["type"],
            }
            for error in exc.errors()
        ]
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content=_cuerpo(
                "validacion",
                "Los datos enviados no son validos",
                {"campos": campos},
            ),
        )

    @app.exception_handler(IntegrityError)
    async def _integridad(request: Request, exc: IntegrityError) -> JSONResponse:
        """Restriccion de la base violada.

        Ocurre cuando dos peticiones concurrentes pasan la comprobacion previa
        antes de que ninguna confirme. Se responde 409, que es lo correcto, sin
        exponer el detalle del esquema.
        """
        log.warning("Violacion de integridad", extra={"ruta": request.url.path}, exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content=_cuerpo(
                "conflicto_integridad",
                "La operacion entra en conflicto con datos existentes. "
                "Verifique que el registro no haya sido creado o modificado por otro usuario.",
            ),
        )

    @app.exception_handler(SQLAlchemyError)
    async def _base_datos(request: Request, exc: SQLAlchemyError) -> JSONResponse:
        log.exception("Error de base de datos", extra={"ruta": request.url.path})
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=_cuerpo(
                "error_base_datos",
                "El servicio de datos no esta disponible en este momento.",
            ),
        )

    @app.exception_handler(Exception)
    async def _inesperado(request: Request, exc: Exception) -> JSONResponse:
        """Ultima red de seguridad.

        Nunca se devuelve el mensaje de la excepcion: podria contener rutas,
        consultas o fragmentos de datos. Se entrega el `request_id` para que el
        usuario pueda reportarlo y el equipo lo localice en los registros.
        """
        log.exception("Error no controlado", extra={"ruta": request.url.path})
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_cuerpo(
                "error_interno",
                "Ocurrio un error inesperado. Reporte el identificador de la peticion.",
            ),
        )
