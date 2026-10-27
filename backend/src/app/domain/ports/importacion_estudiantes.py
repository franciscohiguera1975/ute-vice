"""Puerto de importacion de la matricula estudiantil."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Protocol


@dataclass(frozen=True, slots=True)
class BecaCruda:
    """Una beca individual, ya separada de la celda que las concatena.

    `porcentaje` llega como texto: el origen lo declara como columna de texto
    y no numerica -ver `app.domain.entities.estudiantes.BecaEstudiante`, que
    es donde se convierte a `float`-.
    """

    codigo_beca: str | None = None
    financiamiento: str | None = None
    tipo_beca: str | None = None
    porcentaje: str | None = None


@dataclass(frozen=True, slots=True)
class FilaCrudaEstudiante:
    """Una fila del reporte de matricula de Banner, tal como viene del archivo.

    Deliberadamente plana y de texto, igual que `FilaCrudaDistributivo`: la
    normalizacion ocurre en el caso de uso de importacion, donde se puede
    probar sin abrir un Excel.
    """

    numero_fila: int
    periodo: str
    cedula: str

    sede: str | None = None
    facultad: str | None = None
    carrera: str | None = None
    tipo_carrera: str | None = None
    modalidad: str | None = None
    nivel_formacion_1: str | None = None
    nivel_formacion_2: str | None = None

    id_banner: str | None = None
    nombre: str | None = None
    genero: str | None = None
    mail_personal: str | None = None
    mail_ute: str | None = None
    telefono_celular: str | None = None
    telefono_fijo: str | None = None
    #: Ya convertida: el origen la trae como texto `DD/MM/AAAA`, no como fecha
    #: nativa de Excel. El lector la parsea; un formato invalido o vacio
    #: llega aqui como `None`.
    fecha_nacimiento: date | None = None

    #: Ya separadas y emparejadas por posicion -ver
    #: `app.infrastructure.importadores.estudiantes_excel`-.
    becas: tuple[BecaCruda, ...] = ()

    tipo_estudiante: str | None = None
    sistema: str | None = None
    matriculado: str | None = None
    solicitud_retiro: str | None = None
    bloqueo_plataforma: bool = False
    estado: str | None = None


@dataclass(frozen=True, slots=True)
class ErrorImportacionEstudiante:
    numero_fila: int
    cedula: str
    motivo: str


@dataclass(slots=True)
class ResultadoImportacionEstudiantes:
    """Informe de la carga. Nunca falla entera por una fila mala."""

    total_filas_leidas: int = 0
    estudiantes_creados: int = 0
    estudiantes_existentes: int = 0
    matriculas_creadas: int = 0
    matriculas_actualizadas: int = 0
    becas_creadas: int = 0
    generos_creados: int = 0
    #: Filas cuya `CARRERA` no coincidio por igualdad exacta con ningun
    #: `cat_carreras.nombre`. No se rechazan ni crean una carrera nueva: solo
    #: quedan con `carrera_id = None` y se cuentan aqui para que alguien las
    #: revise.
    sin_carrera_reconocida: int = 0
    rechazadas: list[ErrorImportacionEstudiante] = field(default_factory=list)

    @property
    def exitosa(self) -> bool:
        return not self.rechazadas

    def resumen(self) -> str:
        return (
            f"{self.matriculas_creadas + self.matriculas_actualizadas} matriculas de "
            f"{self.total_filas_leidas} leidas · {self.estudiantes_creados} estudiantes nuevos · "
            f"{self.sin_carrera_reconocida} sin carrera reconocida · "
            f"{len(self.rechazadas)} rechazadas"
        )


class LectorEstudiantes(Protocol):
    """Lee un reporte de matricula y devuelve sus filas sin interpretarlas."""

    def leer(self, origen: str | bytes, *, hoja: str | None = None) -> list[FilaCrudaEstudiante]:
        """Lanza `ErrorValidacion` si el archivo no tiene la estructura esperada."""
        ...
