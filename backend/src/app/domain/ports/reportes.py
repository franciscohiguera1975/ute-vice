"""Puerto de exportacion de reportes.

Un solo contrato para Excel, CSV y PDF. Los casos de uso arman una
`TablaReporte` —datos puros— y delegan el formato. Agregar un formato nuevo no
toca ningun caso de uso: es el principio abierto/cerrado en su forma mas directa.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol

from app.domain.enums import FormatoReporte
from app.domain.value_objects import ahora_utc


@dataclass(frozen=True, slots=True)
class ColumnaReporte:
    """Definicion de una columna: como se titula y como se formatea."""

    clave: str
    titulo: str
    ancho: int = 20
    tipo: str = "texto"
    """`texto`, `numero`, `fecha`, `fecha_hora`, `booleano`, `porcentaje`."""
    alineacion: str = "izquierda"

    color_cabecera: str | None = None
    """Color de fondo de la cabecera, en RRGGBB.

    Existe porque algunos reportes institucionales llegan con una plantilla que
    distingue bloques de columnas por color, y reproducirla importa: quien
    recibe el archivo lo compara contra la plantilla que envio.

    `None` deja el color por defecto del exportador.
    """


@dataclass(slots=True)
class TablaReporte:
    """Datos tabulares listos para exportar, sin formato aun."""

    titulo: str
    columnas: list[ColumnaReporte]
    filas: list[dict[str, Any]]
    subtitulo: str | None = None
    filtros_aplicados: dict[str, Any] = field(default_factory=dict)
    """Se imprime en la cabecera: un reporte sin sus filtros es inauditable."""
    generado_en: datetime = field(default_factory=ahora_utc)
    generado_por: str | None = None
    totales: dict[str, Any] = field(default_factory=dict)

    color_banda: str | None = None
    """Color de las filas pares, en RRGGBB.

    `None` deja el gris del exportador. Existe para los resumenes, que se leen
    como un cuadro y no como un listado: alli las bandas en tono pastel del
    mismo bloque de columnas ayudan a seguir la fila.
    """

    solo_datos: bool = False
    """Omite el preambulo y el pie, dejando la cabecera en la primera fila.

    Lo pide la exportacion que reproduce un archivo de origen: con titulo,
    filtros y totales alrededor, las filas no quedan donde el original las tiene
    y los dos archivos ya no se pueden contrastar sin alinearlos a mano.
    """

    @property
    def total_filas(self) -> int:
        return len(self.filas)

    def valores_de(self, fila: dict[str, Any]) -> list[Any]:
        return [fila.get(col.clave) for col in self.columnas]


@dataclass(frozen=True, slots=True)
class ArchivoReporte:
    """Reporte generado, en memoria."""

    nombre_archivo: str
    contenido: bytes
    tipo_mime: str
    formato: FormatoReporte

    @property
    def tamano_bytes(self) -> int:
        return len(self.contenido)


class ExportadorReporte(Protocol):
    """Convierte una `TablaReporte` en un archivo."""

    @property
    def formato(self) -> FormatoReporte: ...

    @property
    def tipo_mime(self) -> str: ...

    @property
    def extension(self) -> str: ...

    def exportar(self, tabla: TablaReporte) -> ArchivoReporte: ...


class RegistroExportadores(Protocol):
    """Localiza el exportador que corresponde a un formato."""

    def obtener(self, formato: FormatoReporte) -> ExportadorReporte:
        """Lanza `ErrorGeneracionReporte` si el formato no esta registrado."""
        ...

    def formatos_disponibles(self) -> list[FormatoReporte]: ...
