"""Formateo de valores compartido por todos los exportadores.

Centralizado para que una fecha se vea igual en Excel, en CSV y en PDF. Si cada
exportador formateara por su cuenta, el mismo reporte en dos formatos daria
cifras aparentemente distintas.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

ZONA_LOCAL = ZoneInfo("America/Guayaquil")

FORMATO_FECHA = "%d/%m/%Y"
FORMATO_FECHA_HORA = "%d/%m/%Y %H:%M"


def a_local(momento: datetime) -> datetime:
    """Convierte a hora de Ecuador.

    El dominio trabaja en UTC; un reporte que muestre UTC a un funcionario de
    Quito le hara leer las consultas de la tarde como si fueran de la noche.
    """
    if momento.tzinfo is None:
        return momento
    return momento.astimezone(ZONA_LOCAL)


def formatear(valor: Any, tipo: str) -> str:
    """Representacion textual de un valor segun el tipo de columna."""
    if valor is None or valor == "":
        return ""

    match tipo:
        case "fecha":
            if isinstance(valor, datetime):
                return a_local(valor).strftime(FORMATO_FECHA)
            if isinstance(valor, date):
                return valor.strftime(FORMATO_FECHA)
            return str(valor)

        case "fecha_hora":
            if isinstance(valor, datetime):
                return a_local(valor).strftime(FORMATO_FECHA_HORA)
            if isinstance(valor, date):
                return valor.strftime(FORMATO_FECHA)
            return str(valor)

        case "booleano":
            return "Si" if valor else "No"

        case "numero":
            if isinstance(valor, int | float):
                return f"{valor:,}".replace(",", ".")
            return str(valor)

        case "porcentaje":
            if isinstance(valor, int | float):
                return f"{valor:.2f}%"
            return str(valor)

        case _:
            return str(valor)


def valor_nativo(valor: Any, tipo: str) -> Any:
    """Valor conservando su tipo, para formatos que lo soportan (Excel).

    Un numero escrito como texto en una hoja de calculo no se puede sumar ni
    ordenar, y eso arruina el trabajo posterior de quien recibe el archivo.
    """
    if valor is None:
        return None
    if tipo in {"numero", "porcentaje"} and isinstance(valor, int | float):
        return valor
    if tipo == "booleano":
        return "Si" if valor else "No"
    if tipo in {"fecha", "fecha_hora"}:
        if isinstance(valor, datetime):
            # Excel no maneja zonas horarias: se convierte y se quita el tzinfo.
            return a_local(valor).replace(tzinfo=None)
        if isinstance(valor, date):
            return valor
    return str(valor) if not isinstance(valor, str) else valor


def nombre_archivo(titulo: str, extension: str, momento: datetime) -> str:
    """Nombre de archivo seguro y fechado."""
    import re
    import unicodedata

    base = unicodedata.normalize("NFKD", titulo)
    base = "".join(c for c in base if not unicodedata.combining(c))
    base = re.sub(r"[^A-Za-z0-9]+", "_", base).strip("_").lower()[:60]
    marca = a_local(momento).strftime("%Y%m%d_%H%M")
    return f"{base or 'reporte'}_{marca}.{extension}"
