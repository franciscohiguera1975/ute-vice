"""Registro de exportadores disponibles."""

from __future__ import annotations

from app.domain.enums import FormatoReporte
from app.domain.errors import ErrorGeneracionReporte
from app.domain.ports.reportes import ExportadorReporte
from app.infrastructure.reportes.csv import ExportadorCSV
from app.infrastructure.reportes.excel import ExportadorExcel
from app.infrastructure.reportes.pdf import ExportadorPDF


class RegistroExportadoresEnMemoria:
    """Implementacion del puerto `RegistroExportadores`.

    Agregar un formato nuevo es registrar una implementacion mas aqui: ni los
    casos de uso ni la API se enteran. Ese es el punto de haber definido el
    puerto en el dominio.
    """

    def __init__(self, exportadores: list[ExportadorReporte] | None = None) -> None:
        self._exportadores: dict[FormatoReporte, ExportadorReporte] = {}
        for exportador in exportadores or _por_defecto():
            self.registrar(exportador)

    def registrar(self, exportador: ExportadorReporte) -> None:
        self._exportadores[exportador.formato] = exportador

    def obtener(self, formato: FormatoReporte) -> ExportadorReporte:
        exportador = self._exportadores.get(formato)
        if exportador is None:
            disponibles = ", ".join(f.value for f in self.formatos_disponibles())
            raise ErrorGeneracionReporte(
                f"El formato {formato.value} no esta disponible. "
                f"Formatos habilitados: {disponibles}"
            )
        return exportador

    def formatos_disponibles(self) -> list[FormatoReporte]:
        return sorted(self._exportadores, key=lambda f: f.value)


def _por_defecto() -> list[ExportadorReporte]:
    return [ExportadorExcel(), ExportadorCSV(), ExportadorPDF()]
