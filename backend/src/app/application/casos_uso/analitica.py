"""Casos de uso del tablero."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from app.application.base import CasoDeUso, ContextoEjecucion
from app.domain.enums import Permiso
from app.domain.ports.analitica import RepositorioAnalitica, TableroCompleto
from app.domain.ports.reloj import Reloj


@dataclass(frozen=True, slots=True)
class EntradaTablero:
    dias: int = 30
    """Ventana de analisis para las series y las tasas."""


class ObtenerTablero(CasoDeUso[EntradaTablero, TableroCompleto]):
    """Construye el tablero completo en una sola operacion."""

    nombre = "analitica.tablero"
    descripcion = "Indicadores de cobertura, titulos y consultas para el tablero"
    permiso_requerido = Permiso.DASHBOARD_VER

    def __init__(self, analitica: RepositorioAnalitica, reloj: Reloj) -> None:
        self._analitica = analitica
        self._reloj = reloj

    async def _ejecutar(
        self, entrada: EntradaTablero, contexto: ContextoEjecucion
    ) -> TableroCompleto:
        hasta = self._reloj.ahora().date()
        desde = hasta - timedelta(days=max(1, entrada.dias))

        return TableroCompleto(
            cobertura=await self._analitica.resumen_cobertura(desde=desde, hasta=hasta),
            titulos=await self._analitica.resumen_titulos(),
            consultas=await self._analitica.resumen_consultas(desde=desde, hasta=hasta),
            personas_por_unidad=await self._analitica.personas_por_unidad(),
            personas_por_vinculacion=await self._analitica.personas_por_vinculacion(),
            generado_en=self._reloj.ahora().isoformat(),
        )


@dataclass(frozen=True, slots=True)
class EntradaRangoFechas:
    desde: date
    hasta: date
