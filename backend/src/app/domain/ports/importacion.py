"""Puerto de importacion del consolidado de distributivo."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True, slots=True)
class FilaCrudaDistributivo:
    """Una fila del consolidado, tal como viene del archivo.

    Es deliberadamente plana y de texto: representa el origen sin interpretarlo.
    La normalizacion —sedes con varios nombres, titulos concatenados, generos en
    distinta capitalizacion— ocurre en el caso de uso de importacion, donde se
    puede probar sin abrir un Excel.
    """

    numero_fila: int
    identificacion: str
    pao: str
    facultad: str
    carrera: str | None = None
    sede: str | None = None
    nombre: str | None = None
    titularidad: str | None = None
    dedicacion: str | None = None
    categoria: str | None = None
    nivel: str | None = None
    titulo: str | None = None
    tipo_titulo: str | None = None
    genero: str | None = None
    medida: str | None = None
    horas: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ErrorImportacionDistributivo:
    numero_fila: int
    identificacion: str
    motivo: str


@dataclass(frozen=True, slots=True)
class AvisoConsolidacion:
    """Dos filas del origen que comparten la clave natural y se fusionaron.

    Se informa una a una en lugar de consolidar en silencio: cuando el origen
    trae la misma carga dos veces con horas distintas, alguien tiene que poder
    revisar cual era la correcta.
    """

    identificacion: str
    pao: str
    carrera: str
    sede: str | None
    filas_origen: tuple[int, ...]
    total_horas_resultante: float


@dataclass(slots=True)
class ResultadoImportacionDistributivo:
    """Informe de la carga. Nunca falla entera por una fila mala."""

    total_filas_leidas: int = 0
    docentes_creados: int = 0
    docentes_existentes: int = 0
    filas_creadas: int = 0
    filas_consolidadas: int = 0
    elementos_catalogo_creados: dict[str, int] = field(default_factory=dict)
    titulos_creados: int = 0
    rechazadas: list[ErrorImportacionDistributivo] = field(default_factory=list)
    consolidaciones: list[AvisoConsolidacion] = field(default_factory=list)

    @property
    def exitosa(self) -> bool:
        return not self.rechazadas

    def resumen(self) -> str:
        return (
            f"{self.filas_creadas} filas de {self.total_filas_leidas} leidas · "
            f"{self.docentes_creados} docentes nuevos · "
            f"{self.filas_consolidadas} consolidadas · "
            f"{len(self.rechazadas)} rechazadas"
        )


class LectorDistributivo(Protocol):
    """Lee un consolidado y devuelve sus filas sin interpretarlas."""

    def leer(self, ruta: str, *, hoja: str | None = None) -> list[FilaCrudaDistributivo]:
        """Lanza `ErrorValidacion` si el archivo no tiene la estructura esperada."""
        ...


# ---------------------------------------------------------------------------
# Materias que imparte cada docente
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class FilaCrudaMateria:
    """Una materia dictada por un docente en un periodo, tal como viene.

    El origen es el reporte del SICAF agregado por docente: no trae carrera ni
    sede, solo el semestre. Por eso `semestre` es el grano de union con el
    distributivo, y la ambiguedad —un docente con filas en varias carreras el
    mismo semestre— se resuelve en el caso de uso.
    """

    numero_fila: int
    semestre: str
    codigo_periodo: str
    identificacion: str
    nombre_docente: str
    materia: str


@dataclass(frozen=True, slots=True)
class MateriaSinDestino:
    """Una materia que no encontro fila del distributivo a la que enlazarse.

    Se informa en lugar de descartarse en silencio: que un docente aparezca
    dictando y no conste en el distributivo del periodo es justamente lo que
    interesa detectar.
    """

    identificacion: str
    nombre_docente: str
    semestre: str
    materias: int


@dataclass(slots=True)
class ResultadoImportacionMaterias:
    """Informe de la carga de materias."""

    total_filas_leidas: int = 0
    asignaturas_creadas: int = 0
    asignaturas_existentes: int = 0
    filas_enlazadas: int = 0
    enlaces_creados: int = 0
    semestres_sin_periodo: dict[str, int] = field(default_factory=dict)
    sin_destino: list[MateriaSinDestino] = field(default_factory=list)

    @property
    def materias_sin_destino(self) -> int:
        return sum(m.materias for m in self.sin_destino)
