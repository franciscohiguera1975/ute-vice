"""Casos de uso del tablero."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from uuid import UUID

from app.application.base import CasoDeUso, ContextoEjecucion
from app.domain.enums import Permiso
from app.domain.ports.analitica import (
    PeriodoDisponible,
    RepositorioAnalitica,
    RepositorioAnaliticaDistributivo,
    ResumenComparativo,
    TableroCompleto,
    TableroDistributivo,
)
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


# ---------------------------------------------------------------------------
# Tablero del distributivo docente
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class EntradaTableroDistributivo:
    """Los dos periodos que se comparan. Ambos opcionales: ver `_elegir`."""

    pao_id: UUID | None = None
    pao_anterior_id: UUID | None = None


class ObtenerTableroDistributivo(CasoDeUso[EntradaTableroDistributivo, TableroDistributivo]):
    """Indicadores de validacion de dos periodos, uno frente al otro.

    Lo pide `distributivo:leer` y no `dashboard:ver`: es una lectura del
    distributivo, y el rol de consulta —que no tiene tablero general— debe
    poder verlo.
    """

    nombre = "analitica.tablero_distributivo"
    descripcion = "Avance de la validacion del distributivo en dos periodos"
    permiso_requerido = Permiso.DISTRIBUTIVO_LEER

    def __init__(self, analitica: RepositorioAnaliticaDistributivo, reloj: Reloj) -> None:
        self._analitica = analitica
        self._reloj = reloj

    async def _ejecutar(
        self, entrada: EntradaTableroDistributivo, contexto: ContextoEjecucion
    ) -> TableroDistributivo:
        periodos = await self._analitica.periodos_con_filas()
        if not periodos:
            return TableroDistributivo(generado_en=self._reloj.ahora().isoformat())

        actual, anterior = _elegir(periodos, entrada)

        return TableroDistributivo(
            periodos=periodos,
            actual=await self._analitica.validacion_de_periodo(actual.id),
            anterior=(
                await self._analitica.validacion_de_periodo(anterior.id) if anterior else None
            ),
            por_facultad=await self._analitica.validacion_por_facultad(
                actual=actual.id, anterior=anterior.id if anterior else None
            ),
            por_sede=await self._analitica.distribucion_de_periodo(actual.id, campo="sede"),
            por_dedicacion=await self._analitica.distribucion_de_periodo(
                actual.id, campo="dedicacion"
            ),
            generado_en=self._reloj.ahora().isoformat(),
        )


def _elegir(
    periodos: list[PeriodoDisponible], entrada: EntradaTableroDistributivo
) -> tuple[PeriodoDisponible, PeriodoDisponible | None]:
    """Decide que dos periodos se comparan.

    `periodos` llega ordenado de mas nuevo a mas viejo por codigo.

    El anterior por defecto **no es el periodo inmediatamente anterior de la
    lista**, sino el anterior *del mismo tipo*: el codigo institucional es
    `AA P NN D`, donde `NN` distingue tecnologia, grado y posgrado y `D`
    distingue ordinario de interciclo. La familia es `NN D` —los tres ultimos
    digitos—, porque lo unico que cambia entre un periodo y su anterior son el
    anio y el semestre. Comparar `2026-2 GRADO` con `2026-2 POSGRADO` —que es
    lo que saldria de tomar el siguiente de la lista— no dice nada;
    compararlo con `2026-1 GRADO` si.
    """
    por_id = {p.id: p for p in periodos}
    actual = por_id.get(entrada.pao_id) if entrada.pao_id else periodos[0]
    if actual is None:
        actual = periodos[0]

    if entrada.pao_anterior_id:
        return actual, por_id.get(entrada.pao_anterior_id)

    familia = actual.codigo[3:] if len(actual.codigo) == 6 else None
    candidatos = [
        p
        for p in periodos
        if p.id != actual.id
        and p.codigo < actual.codigo
        and (familia is None or p.codigo[3:] == familia)
    ]
    if not candidatos:
        candidatos = [p for p in periodos if p.id != actual.id and p.codigo < actual.codigo]
    return actual, candidatos[0] if candidatos else None


# ---------------------------------------------------------------------------
# Resumenes: dos grupos de periodos, uno frente al otro
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class EntradaResumenComparativo:
    """Los dos grupos que se comparan.

    Son grupos y no periodos sueltos porque un semestre son varios periodos:
    `2026-1` es `261151` + `261651` + `261751`, mas sus interciclos. Comparar
    solo el de grado dejaria fuera media institucion.
    """

    grupo_a: tuple[UUID, ...] = ()
    grupo_b: tuple[UUID, ...] = ()


class ObtenerResumenComparativo(CasoDeUso[EntradaResumenComparativo, ResumenComparativo]):
    """Avance de docentes y desglose de estados entre dos grupos de periodos."""

    nombre = "analitica.resumen_comparativo"
    descripcion = "Compara dos grupos de periodos del distributivo"
    permiso_requerido = Permiso.DISTRIBUTIVO_LEER

    def __init__(self, analitica: RepositorioAnaliticaDistributivo, reloj: Reloj) -> None:
        self._analitica = analitica
        self._reloj = reloj

    async def _ejecutar(
        self, entrada: EntradaResumenComparativo, contexto: ContextoEjecucion
    ) -> ResumenComparativo:
        periodos = await self._analitica.periodos_con_filas()
        ahora = self._reloj.ahora().isoformat()
        if not periodos:
            return ResumenComparativo(generado_en=ahora)

        grupo_a, grupo_b = _grupos(periodos, entrada)

        return ResumenComparativo(
            periodos=periodos,
            grupo_a=await self._analitica.totales_de_grupo(grupo_a),
            grupo_b=await self._analitica.totales_de_grupo(grupo_b),
            avance=await self._analitica.avance_por_facultad(grupo_a=grupo_a, grupo_b=grupo_b),
            estados_a=await self._analitica.estados_por_facultad(grupo_a),
            estados_b=await self._analitica.estados_por_facultad(grupo_b),
            generado_en=ahora,
        )


def _grupos(
    periodos: list[PeriodoDisponible], entrada: EntradaResumenComparativo
) -> tuple[list[UUID], list[UUID]]:
    """Los dos grupos, con el semestre entero como propuesta por defecto.

    Sin eleccion, se toman los dos ultimos semestres completos: todos los
    periodos del mas reciente frente a todos los del anterior. Es la
    comparacion que se pide siempre —«26-1 contra 26-2»— y no obliga a marcar
    tres o seis casillas para verla.
    """
    validos = {p.id for p in periodos}
    a = [i for i in entrada.grupo_a if i in validos]
    b = [i for i in entrada.grupo_b if i in validos]
    if a or b:
        return a, b

    # `periodos` viene ordenado por codigo descendente, asi que el semestre del
    # primero es el mas reciente.
    semestres: list[str] = []
    for p in periodos:
        clave = p.semestre or p.codigo[:3]
        if clave not in semestres:
            semestres.append(clave)

    def del_semestre(clave: str) -> list[UUID]:
        return [p.id for p in periodos if (p.semestre or p.codigo[:3]) == clave]

    if len(semestres) < 2:
        return del_semestre(semestres[0]), []
    return del_semestre(semestres[1]), del_semestre(semestres[0])
