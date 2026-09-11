"""Registro estructurado en JSON con identificador de correlacion.

Cada peticion HTTP recibe un `request_id` que viaja por un `ContextVar`, de modo
que cualquier log emitido durante esa peticion — incluso desde el fondo de un
caso de uso que no sabe nada de HTTP — queda correlacionado sin tener que pasar
el identificador por parametro.
"""

from __future__ import annotations

import json
import logging
import sys
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any, ClassVar

request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)
user_id_ctx: ContextVar[str | None] = ContextVar("user_id", default=None)

# Atributos propios de LogRecord: todo lo demas que traiga el record se
# considera contexto adicional y se vuelca al JSON.
_RESERVADOS = frozenset(
    {
        "args",
        "asctime",
        "created",
        "exc_info",
        "exc_text",
        "filename",
        "funcName",
        "levelname",
        "levelno",
        "lineno",
        "module",
        "msecs",
        "message",
        "msg",
        "name",
        "pathname",
        "process",
        "processName",
        "relativeCreated",
        "stack_info",
        "thread",
        "threadName",
        "taskName",
    }
)


class JsonFormatter(logging.Formatter):
    """Formatea cada registro como una linea JSON apta para agregadores."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        if (rid := request_id_ctx.get()) is not None:
            payload["request_id"] = rid
        if (uid := user_id_ctx.get()) is not None:
            payload["user_id"] = uid

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        if record.stack_info:
            payload["stack"] = self.formatStack(record.stack_info)

        for key, value in record.__dict__.items():
            if key not in _RESERVADOS and not key.startswith("_"):
                payload[key] = _serializable(value)

        return json.dumps(payload, ensure_ascii=False, default=str)


class ConsoleFormatter(logging.Formatter):
    """Formato legible para desarrollo local."""

    _COLORES: ClassVar[dict[str, str]] = {
        "DEBUG": "\033[36m",
        "INFO": "\033[32m",
        "WARNING": "\033[33m",
        "ERROR": "\033[31m",
        "CRITICAL": "\033[35m",
    }
    _RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        color = self._COLORES.get(record.levelname, "")
        hora = datetime.fromtimestamp(record.created, tz=UTC).strftime("%H:%M:%S")
        rid = request_id_ctx.get()
        marca = f" [{rid[:8]}]" if rid else ""
        base = (
            f"{hora} {color}{record.levelname:<8}{self._RESET}"
            f"{marca} {record.name} — {record.getMessage()}"
        )
        if record.exc_info:
            base += "\n" + self.formatException(record.exc_info)
        return base


def _serializable(value: Any) -> Any:
    if isinstance(value, str | int | float | bool | type(None)):
        return value
    if isinstance(value, list | tuple):
        return [_serializable(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _serializable(v) for k, v in value.items()}
    return str(value)


def configurar_logging(*, nivel: str = "INFO", json_output: bool = True) -> None:
    """Instala el formateador elegido en el logger raiz.

    En produccion se emite JSON; en desarrollo, texto coloreado.
    """
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter() if json_output else ConsoleFormatter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(nivel)

    # Uvicorn duplica registros con su propio handler; se delega al raiz.
    for nombre in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        log = logging.getLogger(nombre)
        log.handlers.clear()
        log.propagate = True

    # SQLAlchemy es ruidoso en INFO; solo interesan sus avisos.
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)


def get_logger(nombre: str) -> logging.Logger:
    return logging.getLogger(nombre)
