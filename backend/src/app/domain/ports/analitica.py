"""Puerto de consultas agregadas para el tablero.

Se separa de los repositorios de escritura a proposito. Las agregaciones del
tablero son consultas de solo lectura, optimizadas y sin entidades de por medio:
mezclarlas con los repositorios obligaria a cargar miles de objetos en memoria
para contar cuatro cosas. Es una separacion CQRS ligera — el lado de lectura
tiene su propio contrato.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Protocol


@dataclass(frozen=True, slots=True)
class ConteoEtiquetado:
    """Par etiqueta/valor. Alimenta graficos de barras y anillos."""

    etiqueta: str
    valor: int
    porcentaje: float = 0.0


@dataclass(frozen=True, slots=True)
class PuntoSerie:
    """Punto de una serie temporal."""

    fecha: date
    valor: int
    etiqueta: str | None = None


@dataclass(frozen=True, slots=True)
class ResumenCobertura:
    """Estado de la validacion del padron. Es el numero que importa."""

    total_personas: int
    personas_activas: int
    con_titulos: int
    sin_titulos: int
    nunca_consultadas: int
    consultadas_en_periodo: int
    con_error_ultima_consulta: int

    @property
    def porcentaje_cobertura(self) -> float:
        if self.personas_activas == 0:
            return 0.0
        return round(self.consultadas_en_periodo / self.personas_activas * 100, 2)

    @property
    def porcentaje_con_titulos(self) -> float:
        if self.personas_activas == 0:
            return 0.0
        return round(self.con_titulos / self.personas_activas * 100, 2)


@dataclass(frozen=True, slots=True)
class ResumenTitulos:
    total: int
    vigentes: int
    retirados: int
    por_verificar: int
    verificados: int
    posgrados: int
    por_nivel: list[ConteoEtiquetado] = field(default_factory=list)
    por_institucion: list[ConteoEtiquetado] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class ResumenConsultas:
    total_periodo: int
    exitosas: int
    sin_datos: int
    con_error: int
    esperando_desafio: int
    con_cambios: int
    duracion_promedio_ms: int
    por_estado: list[ConteoEtiquetado] = field(default_factory=list)
    tendencia_diaria: list[PuntoSerie] = field(default_factory=list)

    @property
    def tasa_exito(self) -> float:
        if self.total_periodo == 0:
            return 0.0
        return round((self.exitosas + self.sin_datos) / self.total_periodo * 100, 2)


@dataclass(frozen=True, slots=True)
class TableroCompleto:
    """Todo lo que pinta el tablero, en una sola respuesta.

    Se devuelve junto para que la pantalla haga una peticion y no seis: con seis
    llamadas concurrentes, los numeros pueden no ser coherentes entre si.
    """

    cobertura: ResumenCobertura
    titulos: ResumenTitulos
    consultas: ResumenConsultas
    personas_por_unidad: list[ConteoEtiquetado] = field(default_factory=list)
    personas_por_vinculacion: list[ConteoEtiquetado] = field(default_factory=list)
    generado_en: str = ""


class RepositorioAnalitica(Protocol):
    """Consultas agregadas. Solo lectura."""

    async def resumen_cobertura(self, *, desde: date, hasta: date) -> ResumenCobertura: ...

    async def resumen_titulos(self) -> ResumenTitulos: ...

    async def resumen_consultas(self, *, desde: date, hasta: date) -> ResumenConsultas: ...

    async def personas_por_unidad(self, *, limite: int = 15) -> list[ConteoEtiquetado]: ...

    async def personas_por_vinculacion(self) -> list[ConteoEtiquetado]: ...
