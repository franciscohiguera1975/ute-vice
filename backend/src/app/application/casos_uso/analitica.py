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
    ResumenTiempoParcial,
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
    """Los dos grupos de periodos que se comparan.

    Grupos y no periodos sueltos, por lo mismo que en los resumenes: un
    semestre son tres periodos —tecnologia, grado y posgrado— mas sus
    interciclos, y mirar solo el de grado deja fuera media institucion.
    """

    grupo_a: tuple[UUID, ...] = ()
    grupo_b: tuple[UUID, ...] = ()


class ObtenerTableroDistributivo(CasoDeUso[EntradaTableroDistributivo, TableroDistributivo]):
    """Indicadores de validacion de dos grupos de periodos, uno frente al otro.

    Lo pide `distributivo:leer` y no `dashboard:ver`: es una lectura del
    distributivo, y el rol de consulta —que no tiene tablero general— debe
    poder verlo.
    """

    nombre = "analitica.tablero_distributivo"
    descripcion = "Avance de la validacion del distributivo en dos grupos de periodos"
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

        # Misma eleccion que los resumenes: los dos ultimos semestres enteros.
        # Que las dos pantallas propongan lo mismo no es cosmetico — si una
        # dijera «2026-2 POSGRADO» y la otra «2026-2 completo», sus cifras no
        # cuadrarian y nadie sabria cual creer.
        anterior, actual = _grupos(
            periodos,
            EntradaResumenComparativo(grupo_a=entrada.grupo_a, grupo_b=entrada.grupo_b),
        )

        return TableroDistributivo(
            periodos=periodos,
            actual=await self._analitica.validacion_de_grupo(actual),
            anterior=await self._analitica.validacion_de_grupo(anterior),
            por_facultad=await self._analitica.validacion_por_facultad(
                grupo_a=actual, grupo_b=anterior
            ),
            por_sede=await self._analitica.distribucion_de_grupo(actual, campo="sede"),
            por_dedicacion=await self._analitica.distribucion_de_grupo(actual, campo="dedicacion"),
            generado_en=self._reloj.ahora().isoformat(),
        )


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
    dedicacion_ids: tuple[UUID, ...] = ()
    """Sin marcar ninguna, se incluyen todas las dedicaciones."""


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
        dedicacion_ids = entrada.dedicacion_ids

        return ResumenComparativo(
            periodos=periodos,
            grupo_a=await self._analitica.totales_de_grupo(grupo_a, dedicacion_ids=dedicacion_ids),
            grupo_b=await self._analitica.totales_de_grupo(grupo_b, dedicacion_ids=dedicacion_ids),
            avance=await self._analitica.avance_por_facultad(
                grupo_a=grupo_a, grupo_b=grupo_b, dedicacion_ids=dedicacion_ids
            ),
            estados_a=await self._analitica.estados_por_facultad(
                grupo_a, dedicacion_ids=dedicacion_ids
            ),
            estados_b=await self._analitica.estados_por_facultad(
                grupo_b, dedicacion_ids=dedicacion_ids
            ),
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

    # Con un solo semestre cargado, ese es el **actual** y no hay referencia.
    # Al reves —referencia llena y actual vacio— el avance saldria 0 % y la
    # pantalla diria que no se ha planificado nada, que es justo lo contrario.
    if len(semestres) < 2:
        return [], del_semestre(semestres[0])
    return del_semestre(semestres[1]), del_semestre(semestres[0])


# ---------------------------------------------------------------------------
# Tiempo parcial: horas de `Da` por carrera y facultad, en un PAO
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class EntradaTiempoParcial:
    """El grupo de periodos que se examina.

    Un grupo y no periodos sueltos, por lo mismo que en el resto de la
    analitica: un semestre son varios —tecnologia, grado y posgrado, mas sus
    interciclos—.
    """

    grupo: tuple[UUID, ...] = ()


class ObtenerTiempoParcial(CasoDeUso[EntradaTiempoParcial, ResumenTiempoParcial]):
    """Docentes a tiempo parcial de un PAO, con sus horas de `Da` por
    carrera y facultad."""

    nombre = "analitica.tiempo_parcial"
    descripcion = "Docentes a tiempo parcial de un PAO, con sus horas de Da por carrera y facultad"
    permiso_requerido = Permiso.DISTRIBUTIVO_LEER

    def __init__(self, analitica: RepositorioAnaliticaDistributivo, reloj: Reloj) -> None:
        self._analitica = analitica
        self._reloj = reloj

    async def _ejecutar(
        self, entrada: EntradaTiempoParcial, contexto: ContextoEjecucion
    ) -> ResumenTiempoParcial:
        periodos = await self._analitica.periodos_con_filas()
        ahora = self._reloj.ahora().isoformat()
        if not periodos:
            return ResumenTiempoParcial(generado_en=ahora)

        grupo = _grupo_unico(periodos, entrada.grupo)
        totales = await self._analitica.totales_tiempo_parcial(grupo)

        return ResumenTiempoParcial(
            periodos=periodos,
            grupo=await self._analitica.totales_de_grupo(grupo),
            docentes=totales.docentes,
            horas_da=totales.horas_da,
            por_facultad=await self._analitica.tiempo_parcial_por_facultad(grupo),
            por_carrera=await self._analitica.tiempo_parcial_por_carrera(grupo),
            generado_en=ahora,
        )


def _grupo_unico(periodos: list[PeriodoDisponible], elegidos: tuple[UUID, ...]) -> list[UUID]:
    """Un solo grupo, con el semestre mas reciente completo como propuesta.

    `periodos` viene ordenado por codigo descendente, asi que el semestre del
    primero es el mas reciente.
    """
    validos = {p.id for p in periodos}
    ids = [i for i in elegidos if i in validos]
    if ids:
        return ids

    semestre = periodos[0].semestre or periodos[0].codigo[:3]
    return [p.id for p in periodos if (p.semestre or p.codigo[:3]) == semestre]
