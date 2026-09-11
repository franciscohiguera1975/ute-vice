"""Puerto Reloj.

Las reglas de planificacion dependen de la hora: franjas horarias, vencimiento
de periodos, retrocesos exponenciales. Si el dominio llamara a `datetime.now()`
directamente, esas reglas serian imposibles de probar sin esperar horas reales.
Con este puerto, una prueba inyecta un reloj congelado y verifica el
comportamiento a las 03:00 sin levantarse de madrugada.
"""

from __future__ import annotations

import random
from datetime import UTC, datetime, tzinfo
from typing import Protocol
from zoneinfo import ZoneInfo


class Reloj(Protocol):
    def ahora(self) -> datetime:
        """Instante actual en UTC, siempre con zona horaria."""
        ...

    def ahora_local(self, zona: tzinfo | None = None) -> datetime:
        """Instante actual en la zona indicada (por defecto, la institucional)."""
        ...


class RelojDelSistema:
    """Implementacion real. Unica de todo el sistema que consulta el reloj."""

    def __init__(self, zona_local: str = "America/Guayaquil") -> None:
        self._zona = ZoneInfo(zona_local)

    def ahora(self) -> datetime:
        return datetime.now(UTC)

    def ahora_local(self, zona: tzinfo | None = None) -> datetime:
        return datetime.now(zona or self._zona)


class RelojCongelado:
    """Reloj controlado, para pruebas y simulaciones del planificador."""

    def __init__(self, momento: datetime, zona_local: str = "America/Guayaquil") -> None:
        if momento.tzinfo is None:
            raise ValueError("El reloj congelado exige un instante con zona horaria")
        self._momento = momento.astimezone(UTC)
        self._zona = ZoneInfo(zona_local)

    def ahora(self) -> datetime:
        return self._momento

    def ahora_local(self, zona: tzinfo | None = None) -> datetime:
        return self._momento.astimezone(zona or self._zona)

    def avanzar(self, segundos: float) -> None:
        from datetime import timedelta

        self._momento += timedelta(seconds=segundos)

    def fijar(self, momento: datetime) -> None:
        self._momento = momento.astimezone(UTC)


class FuenteAleatoria(Protocol):
    """Puerto para la aleatoriedad del planificador.

    Se abstrae por la misma razon que el reloj: el desorden de la cola y el
    jitter entre peticiones son reglas de negocio, y una prueba necesita
    fijarlos para poder afirmar algo sobre el resultado.
    """

    def uniforme(self, minimo: float, maximo: float) -> float: ...
    def barajar(self, elementos: list[object]) -> None: ...


class AleatorioDelSistema:
    def __init__(self, semilla: int | None = None) -> None:
        self._rng = random.Random(semilla)

    def uniforme(self, minimo: float, maximo: float) -> float:
        return self._rng.uniform(minimo, maximo)

    def barajar(self, elementos: list[object]) -> None:
        self._rng.shuffle(elementos)
