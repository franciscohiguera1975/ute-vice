"""Registro de plantillas de exportacion.

Agregar un formato nuevo es escribir la clase y sumarla a `_PLANTILLAS`. Ni el
caso de uso, ni el router, ni el frontend cambian: la interfaz pregunta que
plantillas hay y pinta las que reciba.
"""

from __future__ import annotations

from app.application.plantillas.base import PlantillaDistributivo
from app.application.plantillas.consolidado import PlantillaConsolidadoOrigen
from app.application.plantillas.docencia import PlantillaDocenciaPorCarrera
from app.domain.errors import ErrorValidacion

#: Las plantillas disponibles, en el orden en que se ofrecen. La primera es la
#: que usa quien no elige ninguna.
_PLANTILLAS: tuple[PlantillaDistributivo, ...] = (
    PlantillaDocenciaPorCarrera(),
    PlantillaConsolidadoOrigen(),
)

PLANTILLA_POR_DEFECTO = _PLANTILLAS[0].codigo


class RegistroPlantillas:
    """Busca plantillas por codigo."""

    def __init__(self, plantillas: tuple[PlantillaDistributivo, ...] = _PLANTILLAS) -> None:
        self._por_codigo = {p.codigo: p for p in plantillas}
        self._orden = list(plantillas)

    def disponibles(self) -> list[PlantillaDistributivo]:
        return list(self._orden)

    def obtener(self, codigo: str | None) -> PlantillaDistributivo:
        if not codigo:
            return self._orden[0]
        plantilla = self._por_codigo.get(codigo)
        if plantilla is None:
            disponibles = ", ".join(self._por_codigo)
            raise ErrorValidacion(
                f"Plantilla de exportacion desconocida: '{codigo}'. Disponibles: {disponibles}.",
                campo="plantilla",
            )
        return plantilla


#: Registro compartido por la aplicacion.
REGISTRO_PLANTILLAS = RegistroPlantillas()
