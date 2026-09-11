"""Lectura del consolidado de distributivo en Excel.

El consolidado tiene 72 columnas: los datos del docente y su contrato, mas el
reparto de horas en cuatro bloques (`Da`..`Dn`, `Ga`..`Gn`, `Ia`..`Ij`,
`Va`..`Vi`).

Las columnas `D`, `G`, `I`, `V` y `TotalHoras` del archivo son **derivadas** y no
se leen: el sistema las recalcula desde el detalle. Si el archivo trae un total
que no cuadra con sus componentes, manda el detalle.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from openpyxl import load_workbook

from app.core.logging import get_logger
from app.domain.errors import ErrorValidacion
from app.domain.ports.importacion import FilaCrudaDistributivo
from app.domain.value_objects_distributivo import DistribucionHoras

log = get_logger(__name__)

#: Columnas del consolidado que se leen, con su nombre en el archivo.
_COLUMNAS = {
    "identificacion": "IDENTIFICACION",
    "pao": "PAO",
    "facultad": "FACULTAD",
    "carrera": "CARRERA",
    "sede": "SEDE",
    "nombre": "APELLIDOS.Y.NOMBRES",
    "titularidad": "TITULARIDAD",
    "dedicacion": "DEDICACION",
    "categoria": "CATEGORIA",
    "nivel": "NIVEL",
    "programa": "CARRERA/PROGRAMA",
    "titulo": "TITULO",
    "tipo_titulo": "TIPOTITULO",
    "genero": "GENERO",
    "medida": "MEDIDA",
}

#: Sin estas no se puede construir una fila.
_OBLIGATORIAS = ("IDENTIFICACION", "PAO", "FACULTAD")

_CLAVES_HORAS = (
    DistribucionHoras.CLAVES_DOCENCIA
    + DistribucionHoras.CLAVES_GESTION
    + DistribucionHoras.CLAVES_INVESTIGACION
    + DistribucionHoras.CLAVES_VINCULACION
)


def _texto(valor: Any) -> str | None:
    if valor is None:
        return None
    limpio = " ".join(str(valor).split())
    # El origen usa "NA" y "N/A" como ausencia de dato, no como valor.
    return limpio if limpio and limpio.upper() not in {"NA", "N/A"} else None


def _numero(valor: Any) -> float | None:
    if valor is None or valor == "":
        return None
    try:
        return float(valor)
    except (TypeError, ValueError):
        return None


class LectorDistributivoExcel:
    """Implementacion del puerto `LectorDistributivo` con openpyxl."""

    def leer(self, ruta: str, *, hoja: str | None = None) -> list[FilaCrudaDistributivo]:
        archivo = Path(ruta)
        if not archivo.exists():
            raise ErrorValidacion(f"El archivo no existe: {ruta}", campo="archivo")

        # `read_only` recorre el libro en flujo: un consolidado de 15.000 filas
        # cabe en memoria, pero cargarlo entero no aporta nada.
        libro = load_workbook(archivo, read_only=True, data_only=True)
        try:
            pagina = libro[hoja] if hoja else libro.worksheets[0]
            iterador = pagina.iter_rows(values_only=True)

            try:
                cabecera = [str(c).strip() if c is not None else "" for c in next(iterador)]
            except StopIteration:
                raise ErrorValidacion("El archivo esta vacio", campo="archivo") from None

            indices = {nombre: i for i, nombre in enumerate(cabecera)}
            faltantes = [c for c in _OBLIGATORIAS if c not in indices]
            if faltantes:
                raise ErrorValidacion(
                    f"Al archivo le faltan columnas obligatorias: {', '.join(faltantes)}. "
                    f"Se esperaba la estructura del consolidado de distributivo.",
                    campo="archivo",
                )

            filas: list[FilaCrudaDistributivo] = []
            for numero, fila in enumerate(iterador, start=2):
                cruda = self._construir(numero, fila, indices)
                if cruda is not None:
                    filas.append(cruda)

            log.info(
                "Consolidado leido",
                extra={"archivo": archivo.name, "filas": len(filas)},
            )
            return filas
        finally:
            libro.close()

    def _construir(
        self, numero: int, fila: tuple[Any, ...], indices: dict[str, int]
    ) -> FilaCrudaDistributivo | None:
        def leer(nombre: str) -> Any:
            i = indices.get(nombre)
            return fila[i] if i is not None and i < len(fila) else None

        identificacion = _texto(leer("IDENTIFICACION"))
        if not identificacion:
            # Fila en blanco al final del libro: se ignora en silencio.
            return None

        horas = {
            clave: valor for clave in _CLAVES_HORAS if (valor := _numero(leer(clave))) is not None
        }

        return FilaCrudaDistributivo(
            numero_fila=numero,
            identificacion=identificacion,
            pao=_texto(leer("PAO")) or "",
            facultad=_texto(leer("FACULTAD")) or "",
            carrera=_texto(leer("CARRERA")),
            sede=_texto(leer("SEDE")),
            nombre=_texto(leer("APELLIDOS.Y.NOMBRES")),
            titularidad=_texto(leer("TITULARIDAD")),
            dedicacion=_texto(leer("DEDICACION")),
            categoria=_texto(leer("CATEGORIA")),
            nivel=_texto(leer("NIVEL")),
            programa=_texto(leer("CARRERA/PROGRAMA")),
            titulo=_texto(leer("TITULO")),
            tipo_titulo=_texto(leer("TIPOTITULO")),
            genero=_texto(leer("GENERO")),
            medida=_texto(leer("MEDIDA")),
            horas=horas,
        )
