"""Imagenes insertadas desde el editor enriquecido de un ticket.

No es un sistema de adjuntos: es solo lo que sube el boton de imagen del
editor, para no incrustar base64 en la columna de descripcion o de un
comentario de seguimiento.
"""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

from app.core.config import TicketsSettings
from app.domain.errors import ErrorValidacion

#: Tipos aceptados y su extension en disco. El nombre de archivo nunca viene
#: del cliente: se genera aqui, asi que no hace falta sanear el original.
_TIPOS_PERMITIDOS = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
    "image/gif": ".gif",
}


async def guardar_imagen(archivo: UploadFile, settings: TicketsSettings) -> str:
    """Valida y guarda la imagen. Devuelve el nombre generado para servirla despues."""
    extension = _TIPOS_PERMITIDOS.get(archivo.content_type or "")
    if extension is None:
        raise ErrorValidacion(
            "Solo se admiten imagenes PNG, JPEG, WEBP o GIF", campo="archivo"
        )

    contenido = await archivo.read()
    limite_bytes = settings.max_imagen_mb * 1024 * 1024
    if len(contenido) > limite_bytes:
        raise ErrorValidacion(
            f"La imagen supera el tamano maximo de {settings.max_imagen_mb} MB",
            campo="archivo",
        )

    settings.imagenes_dir.mkdir(parents=True, exist_ok=True)
    nombre = f"{uuid4()}{extension}"
    (settings.imagenes_dir / nombre).write_bytes(contenido)
    return nombre


def resolver_imagen(nombre: str, settings: TicketsSettings) -> Path | None:
    """Ruta en disco de una imagen ya guardada.

    `None` si el archivo no existe o si el nombre pedido intenta salir del
    directorio de imagenes (p. ej. con `..`).
    """
    base = settings.imagenes_dir.resolve()
    candidato = (base / nombre).resolve()
    if not candidato.is_relative_to(base) or not candidato.is_file():
        return None
    return candidato
