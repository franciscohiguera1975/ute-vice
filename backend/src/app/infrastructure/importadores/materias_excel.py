"""Lectura del reporte de materias por docente en Excel.

Seis columnas: el semestre (`2026-1`), el codigo institucional del periodo
(`261651`), la cedula y el nombre del docente, y el nombre de la materia. Una
fila por materia: un docente con cuatro asignaturas ocupa cuatro filas.

El archivo **no trae carrera ni sede**, que son parte de la clave natural de una
fila del distributivo. La union se hace por docente y semestre, y el reparto
cuando hay varias filas candidatas lo decide el caso de uso, donde se puede
probar sin abrir un Excel.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from openpyxl import load_workbook

from app.core.logging import get_logger
from app.domain.errors import ErrorValidacion
from app.domain.ports.importacion import FilaCrudaMateria

log = get_logger(__name__)

#: Columnas que se leen, con su nombre en el archivo.
_COLUMNAS = {
    "semestre": "periodo",
    "codigo_periodo": "codigo_periodo",
    "identificacion": "cedula_docente",
    "nombre_docente": "nombre_docente",
    "materia": "nombre_materia",
}

#: Sin estas no se puede construir una fila.
_OBLIGATORIAS = ("periodo", "cedula_docente", "nombre_materia")


def _texto(valor: Any) -> str:
    if valor is None:
        return ""
    # Las cedulas vienen a veces como numero y pierden el cero inicial.
    if isinstance(valor, float) and valor.is_integer():
        return str(int(valor))
    return " ".join(str(valor).split())


class LectorMateriasExcel:
    """Convierte el reporte de materias en filas planas."""

    def leer(self, ruta: str | Path, *, hoja: str | None = None) -> list[FilaCrudaMateria]:
        camino = Path(ruta)
        if not camino.exists():
            raise ErrorValidacion(f"El archivo no existe: {camino}", campo="archivo")

        libro = load_workbook(camino, read_only=True, data_only=True)
        try:
            pagina = libro[hoja] if hoja else libro[libro.sheetnames[0]]
            iterador = pagina.iter_rows(values_only=True)

            try:
                cabecera = next(iterador)
            except StopIteration:
                raise ErrorValidacion("El archivo esta vacio", campo="archivo") from None

            indices = {_texto(c).lower(): i for i, c in enumerate(cabecera) if c is not None}
            faltantes = [c for c in _OBLIGATORIAS if c not in indices]
            if faltantes:
                raise ErrorValidacion(
                    f"Al archivo le faltan columnas: {', '.join(faltantes)}",
                    campo="archivo",
                )

            filas: list[FilaCrudaMateria] = []
            for numero, cruda in enumerate(iterador, start=2):
                if all(v is None for v in cruda):
                    continue

                def valor(clave: str, _fila: tuple[Any, ...] = cruda) -> str:
                    posicion = indices.get(_COLUMNAS[clave])
                    if posicion is None or posicion >= len(_fila):
                        return ""
                    return _texto(_fila[posicion])

                materia = valor("materia")
                identificacion = valor("identificacion")
                if not materia or not identificacion:
                    continue

                filas.append(
                    FilaCrudaMateria(
                        numero_fila=numero,
                        semestre=valor("semestre"),
                        codigo_periodo=valor("codigo_periodo"),
                        identificacion=identificacion,
                        nombre_docente=valor("nombre_docente"),
                        materia=materia,
                    )
                )
        finally:
            libro.close()

        log.info("Reporte de materias leido", extra={"filas": len(filas), "archivo": str(camino)})
        return filas
