"""Plantillas de exportacion del distributivo."""

from app.application.plantillas.base import ContenidoPlantilla, PlantillaDistributivo
from app.application.plantillas.consolidado import (
    COLUMNAS_CONSOLIDADO,
    PlantillaConsolidadoOrigen,
)
from app.application.plantillas.docencia import COLUMNAS_DOCENCIA, PlantillaDocenciaPorCarrera
from app.application.plantillas.indicadores_docentes import (
    COLUMNAS_INDICADORES_DOCENTES,
    PlantillaIndicadoresDocentes,
)
from app.application.plantillas.pao import COLUMNAS_PAO, PlantillaPaoOrigen
from app.application.plantillas.registro import (
    PLANTILLA_POR_DEFECTO,
    REGISTRO_PLANTILLAS,
    RegistroPlantillas,
)

__all__ = [
    "COLUMNAS_CONSOLIDADO",
    "COLUMNAS_DOCENCIA",
    "COLUMNAS_INDICADORES_DOCENTES",
    "COLUMNAS_PAO",
    "PLANTILLA_POR_DEFECTO",
    "REGISTRO_PLANTILLAS",
    "ContenidoPlantilla",
    "PlantillaConsolidadoOrigen",
    "PlantillaDistributivo",
    "PlantillaDocenciaPorCarrera",
    "PlantillaIndicadoresDocentes",
    "PlantillaPaoOrigen",
    "RegistroPlantillas",
]
