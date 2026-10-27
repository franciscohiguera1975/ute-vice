"""Entidades de la matricula estudiantil.

Alimentan el futuro Tablero Docente, que calculara la relacion
estudiantes/docente por carrera. Este modulo solo modela la carga y el
almacenamiento; ese calculo lo construye otra persona sobre
`RepositorioEstudiantes.conteo_por_carrera`.

Tres entidades:

* `Estudiante` — la persona, con lo que no cambia entre periodos: su cedula,
  su nombre y sus datos de contacto.
* `MatriculaEstudiante` — una carrera y periodo en que ese estudiante esta
  matriculado. La clave natural real es `(estudiante, periodo, carrera,
  sede)`: Banner permite doble matricula el mismo periodo cuando la carrera o
  la sede difieren.
* `BecaEstudiante` — una beca o descuento individual de una matricula. Va
  aparte porque el origen puede traer varias en una misma celda —beca
  deportiva y descuento por hermano a la vez—, separadas por coma.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from uuid import UUID, uuid4

from app.domain.value_objects import ahora_utc


@dataclass(slots=True, kw_only=True)
class BecaEstudiante:
    """Una beca o descuento individual, ya separada de la celda del origen."""

    codigo_beca: str | None = None
    financiamiento: str | None = None
    tipo_beca: str | None = None
    porcentaje: float | None = None

    id: UUID = field(default_factory=uuid4)


@dataclass(slots=True, kw_only=True)
class MatriculaEstudiante:
    """Un estudiante matriculado en una carrera durante un periodo de Banner.

    `periodo` es el codigo de seis digitos que trae Banner —`262651`—. No es
    el mismo esquema que `PeriodoAcademico`/`cat_paos` del distributivo
    docente, que usa el digito de nivel `15`/`65`/`75`: aqui no calzan, asi
    que se guarda como texto plano sin decodificarlo ni relacionarlo con
    `cat_paos`.

    `sede`, `facultad` y `carrera` son el texto crudo del Excel. `carrera_id`
    es, ademas, la resolucion contra el catalogo `cat_carreras` cuando hay una
    coincidencia exacta de nombre —ver
    `app.application.casos_uso.importar_estudiantes.ImportarEstudiantes`—;
    queda `None` cuando no la hay, sin que eso rechace la fila.
    """

    estudiante_id: UUID
    periodo: str

    sede: str | None = None
    facultad: str | None = None
    carrera: str | None = None
    carrera_id: UUID | None = None
    tipo_carrera: str | None = None
    modalidad: str | None = None
    nivel_formacion_1: str | None = None
    nivel_formacion_2: str | None = None

    tipo_estudiante: str | None = None
    sistema: str | None = None
    matriculado: str | None = None
    solicitud_retiro: str | None = None
    bloqueo_plataforma: bool = False
    estado: str | None = None

    #: Una fila por beca individual. Vacia cuando la matricula no tiene
    #: ninguna —las cuatro columnas del origen vienen vacias—.
    becas: list[BecaEstudiante] = field(default_factory=list)

    id: UUID = field(default_factory=uuid4)
    creado_en: datetime = field(default_factory=ahora_utc)
    actualizado_en: datetime = field(default_factory=ahora_utc)


@dataclass(slots=True, kw_only=True)
class Estudiante:
    """Una persona del padron de matricula.

    `cedula` **no es unica**: a diferencia de `Docente.identificacion`, Banner
    puede repetir la misma cedula en dos matriculas del mismo periodo —doble
    carrera o sede—, y el importador no impone una identidad unica que el
    origen no garantiza. `app.domain.ports.estudiantes.RepositorioEstudiantes`
    no tiene restriccion de unicidad sobre esta columna por el mismo motivo.
    """

    cedula: str
    nombre: str
    id_banner: str | None = None
    genero_id: UUID | None = None
    mail_personal: str | None = None
    mail_ute: str | None = None
    telefono_celular: str | None = None
    telefono_fijo: str | None = None
    fecha_nacimiento: date | None = None

    id: UUID = field(default_factory=uuid4)
    creado_en: datetime = field(default_factory=ahora_utc)
    actualizado_en: datetime = field(default_factory=ahora_utc)

    def actualizar(
        self,
        *,
        nombre: str | None = None,
        id_banner: str | None = None,
        genero_id: UUID | None = None,
        mail_personal: str | None = None,
        mail_ute: str | None = None,
        telefono_celular: str | None = None,
        telefono_fijo: str | None = None,
        fecha_nacimiento: date | None = None,
    ) -> None:
        """Aplica solo los campos recibidos; cada carga trae el dato mas reciente."""
        if nombre:
            self.nombre = nombre
        if id_banner:
            self.id_banner = id_banner
        if genero_id:
            self.genero_id = genero_id
        if mail_personal:
            self.mail_personal = mail_personal
        if mail_ute:
            self.mail_ute = mail_ute
        if telefono_celular:
            self.telefono_celular = telefono_celular
        if telefono_fijo:
            self.telefono_fijo = telefono_fijo
        if fecha_nacimiento:
            self.fecha_nacimiento = fecha_nacimiento
        self.actualizado_en = ahora_utc()

    def __eq__(self, otro: object) -> bool:
        return isinstance(otro, Estudiante) and otro.id == self.id

    def __hash__(self) -> int:
        return hash(self.id)
