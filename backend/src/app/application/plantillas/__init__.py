"""Plantillas de exportacion del distributivo."""

from app.application.plantillas.base import ContenidoPlantilla, PlantillaDistributivo
from app.application.plantillas.consolidado import (
    COLUMNAS_CONSOLIDADO,
    PlantillaConsolidadoOrigen,
)
from app.application.plantillas.docencia import COLUMNAS_DOCENCIA, PlantillaDocenciaPorCarrera
from app.application.plantillas.registro import (
    PLANTILLA_POR_DEFECTO,
    REGISTRO_PLANTILLAS,
    RegistroPlantillas,
)

__all__ = [
    "COLUMNAS_CONSOLIDADO",
    "COLUMNAS_DOCENCIA",
    "PLANTILLA_POR_DEFECTO",
    "REGISTRO_PLANTILLAS",
    "ContenidoPlantilla",
    "PlantillaConsolidadoOrigen",
    "PlantillaDistributivo",
    "PlantillaDocenciaPorCarrera",
    "RegistroPlantillas",
]
