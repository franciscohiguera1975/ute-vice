"""Puerto de consultas agregadas para el tablero.

Se separa de los repositorios de escritura a proposito. Las agregaciones del
tablero son consultas de solo lectura, optimizadas y sin entidades de por medio:
mezclarlas con los repositorios obligaria a cargar miles de objetos en memoria
para contar cuatro cosas. Es una separacion CQRS ligera — el lado de lectura
tiene su propio contrato.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date
from typing import Protocol
from uuid import UUID


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


# ---------------------------------------------------------------------------
# Tablero del distributivo docente
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PeriodoDisponible:
    """Un PAO que tiene filas cargadas, para elegirlo en el tablero."""

    id: UUID
    codigo: str
    nombre: str
    semestre: str
    """`2026-2`. Sale de los atributos del catalogo; vacio si no lo trae."""
    filas: int


@dataclass(frozen=True, slots=True)
class ValidacionDeGrupo:
    """Como quedo la validacion de un grupo de periodos.

    Es un grupo y no un periodo suelto porque un semestre son varios: `2026-1`
    es tecnologia, grado y posgrado, mas sus interciclos. Mirar solo el de
    grado deja fuera media institucion.

    `aprobadas` suma `OK` y `OK_EXCEPCION`: las dos dicen que la carga es
    valida, y la segunda solo anade que lo es por una excepcion concedida.

    `sin_estado` esta aparte y **no cuenta como reprobada**: los periodos
    anteriores a 2026-2 no traian el dato. Mezclarlo con `ERROR` haria que
    todo el historico apareciera como rechazado.
    """

    codigos: tuple[str, ...]
    nombres: tuple[str, ...]
    total: int
    aprobadas: int
    pendientes: int
    con_error: int
    sin_estado: int
    docentes: int
    horas: float
    por_estado: list[ConteoEtiquetado] = field(default_factory=list)

    @property
    def evaluadas(self) -> int:
        """Filas que si traen estado. Es el denominador del porcentaje."""
        return self.total - self.sin_estado

    @property
    def porcentaje_aprobado(self) -> float:
        if self.evaluadas == 0:
            return 0.0
        return round(self.aprobadas / self.evaluadas * 100, 2)


@dataclass(frozen=True, slots=True)
class FilaComparativa:
    """Una facultad con sus cifras en los dos grupos que se comparan."""

    etiqueta: str
    total_actual: int
    aprobadas_actual: int
    evaluadas_actual: int
    total_anterior: int
    aprobadas_anterior: int
    evaluadas_anterior: int

    @staticmethod
    def _porcentaje(aprobadas: int, evaluadas: int) -> float:
        return round(aprobadas / evaluadas * 100, 2) if evaluadas else 0.0

    @property
    def porcentaje_actual(self) -> float:
        return self._porcentaje(self.aprobadas_actual, self.evaluadas_actual)

    @property
    def porcentaje_anterior(self) -> float:
        return self._porcentaje(self.aprobadas_anterior, self.evaluadas_anterior)

    @property
    def variacion(self) -> float:
        """Puntos porcentuales ganados o perdidos entre los dos periodos."""
        return round(self.porcentaje_actual - self.porcentaje_anterior, 2)


@dataclass(frozen=True, slots=True)
class TableroDistributivo:
    """Todo lo que pinta el tablero del distributivo, en una sola respuesta."""

    periodos: list[PeriodoDisponible] = field(default_factory=list)
    actual: ValidacionDeGrupo | None = None
    anterior: ValidacionDeGrupo | None = None
    por_facultad: list[FilaComparativa] = field(default_factory=list)
    por_sede: list[ConteoEtiquetado] = field(default_factory=list)
    por_dedicacion: list[ConteoEtiquetado] = field(default_factory=list)
    generado_en: str = ""


class RepositorioAnaliticaDistributivo(Protocol):
    """Agregaciones del distributivo docente. Solo lectura."""

    async def periodos_con_filas(self) -> list[PeriodoDisponible]: ...

    async def validacion_de_grupo(self, paos: Sequence[UUID]) -> ValidacionDeGrupo | None: ...

    async def validacion_por_facultad(
        self, *, grupo_a: Sequence[UUID], grupo_b: Sequence[UUID]
    ) -> list[FilaComparativa]: ...

    async def distribucion_de_grupo(
        self, paos: Sequence[UUID], *, campo: str, limite: int = 12
    ) -> list[ConteoEtiquetado]: ...

    async def totales_de_grupo(self, paos: Sequence[UUID]) -> GrupoDePeriodos: ...

    async def avance_por_facultad(
        self, *, grupo_a: Sequence[UUID], grupo_b: Sequence[UUID]
    ) -> list[AvanceDeFacultad]: ...

    async def estados_por_facultad(self, paos: Sequence[UUID]) -> list[EstadosDeFacultad]: ...


# ---------------------------------------------------------------------------
# Resumenes: dos grupos de periodos, uno frente al otro
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class GrupoDePeriodos:
    """Lo que un grupo de periodos suma en conjunto.

    `docentes` **no es la suma de los docentes de cada facultad**: un docente
    que dicta en dos facultades cuenta una vez aqui y dos alli. Por eso se
    calcula aparte y no sumando la columna.
    """

    codigos: tuple[str, ...]
    filas: int
    docentes: int


@dataclass(frozen=True, slots=True)
class AvanceDeFacultad:
    """Una facultad en los dos grupos de periodos que se comparan.

    El avance es cuantos de los docentes que tenia el primer grupo vuelven a
    tener carga en el segundo. Puede pasar del 100 %: significa que la facultad
    planifico mas docentes de los que tenia.
    """

    codigo: str
    nombre: str
    docentes_a: int
    docentes_b: int
    filas_a: int
    filas_b: int
    docentes_aprobados_b: int
    filas_aprobadas_b: int
    filas_evaluadas_b: int

    @property
    def porcentaje_avance(self) -> float:
        if self.docentes_a == 0:
            return 0.0
        return round(self.docentes_b / self.docentes_a * 100, 1)

    @property
    def porcentaje_aprobado_b(self) -> float:
        if self.filas_evaluadas_b == 0:
            return 0.0
        return round(self.filas_aprobadas_b / self.filas_evaluadas_b * 100, 1)


@dataclass(frozen=True, slots=True)
class EstadosDeFacultad:
    """Las filas de una facultad repartidas por estado de validacion."""

    codigo: str
    nombre: str
    ok: int
    ok_excepcion: int
    pendiente: int
    con_error: int
    sin_estado: int

    @property
    def total(self) -> int:
        return self.ok + self.ok_excepcion + self.pendiente + self.con_error + self.sin_estado

    @property
    def evaluadas(self) -> int:
        return self.total - self.sin_estado

    @property
    def porcentaje_aprobado(self) -> float:
        if self.evaluadas == 0:
            return 0.0
        return round((self.ok + self.ok_excepcion) / self.evaluadas * 100, 1)


@dataclass(frozen=True, slots=True)
class ResumenComparativo:
    """Los dos resumenes de la pantalla, en una sola respuesta."""

    periodos: list[PeriodoDisponible] = field(default_factory=list)
    grupo_a: GrupoDePeriodos | None = None
    grupo_b: GrupoDePeriodos | None = None
    avance: list[AvanceDeFacultad] = field(default_factory=list)
    estados_a: list[EstadosDeFacultad] = field(default_factory=list)
    estados_b: list[EstadosDeFacultad] = field(default_factory=list)
    generado_en: str = ""
