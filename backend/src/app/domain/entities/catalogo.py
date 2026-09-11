"""Catalogos del distributivo docente.

Los doce catalogos —PAO, facultad, carrera, sede, titularidad, dedicacion,
categoria, nivel, programa, titulo profesional, tipo de titulo y genero— comparten
forma: un codigo unico, un nombre, y las marcas de activo y orden.

Se modelan como **tablas separadas** y no como una sola tabla con un
discriminador. La diferencia importa: con tablas separadas, la columna
`distributivo.sede_id` solo puede apuntar a una sede, y la base lo garantiza. Con
una tabla unica, nada impedia que apuntara a una facultad y el error se
descubriria al leer un reporte.

El comportamiento, en cambio, si se comparte: esta entidad base y los genericos
de la capa de aplicacion hacen que los doce CRUD sean el mismo codigo.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from app.domain.errors import ErrorValidacion
from app.domain.value_objects import ahora_utc, normalizar_texto
from app.domain.value_objects_distributivo import PeriodoAcademico


class TipoCatalogo(StrEnum):
    """Los doce catalogos. El valor es el segmento de URL de su API.

    No hay catalogo de «programa»: el consolidado traia `CARRERA` y
    `CARRERA/PROGRAMA` con la misma informacion —el segundo era el primero
    capitalizado— y mantener los dos obligaba a elegir entre ellos en cada
    formulario sin que la eleccion significara nada. Quedo `carrera`, que es
    ademas parte de la clave natural de una fila.
    """

    PAO = "paos"
    FACULTAD = "facultades"
    CARRERA = "carreras"
    SEDE = "sedes"
    TITULARIDAD = "titularidades"
    DEDICACION = "dedicaciones"
    CATEGORIA = "categorias"
    NIVEL = "niveles"
    TITULO_PROFESIONAL = "titulos-profesionales"
    TIPO_TITULO = "tipos-titulo"
    GENERO = "generos"
    ASIGNATURA = "asignaturas"

    @property
    def etiqueta(self) -> str:
        return _ETIQUETAS[self]

    @property
    def singular(self) -> str:
        return _SINGULARES[self]


_ETIQUETAS: dict[TipoCatalogo, str] = {
    TipoCatalogo.PAO: "Periodos academicos",
    TipoCatalogo.FACULTAD: "Facultades",
    TipoCatalogo.CARRERA: "Carreras",
    TipoCatalogo.SEDE: "Sedes",
    TipoCatalogo.TITULARIDAD: "Titularidades",
    TipoCatalogo.DEDICACION: "Dedicaciones",
    TipoCatalogo.CATEGORIA: "Categorias",
    TipoCatalogo.NIVEL: "Niveles",
    TipoCatalogo.TITULO_PROFESIONAL: "Titulos profesionales",
    TipoCatalogo.TIPO_TITULO: "Tipos de titulo",
    TipoCatalogo.GENERO: "Generos",
    TipoCatalogo.ASIGNATURA: "Asignaturas",
}

_SINGULARES: dict[TipoCatalogo, str] = {
    TipoCatalogo.PAO: "periodo academico",
    TipoCatalogo.FACULTAD: "facultad",
    TipoCatalogo.CARRERA: "carrera",
    TipoCatalogo.SEDE: "sede",
    TipoCatalogo.TITULARIDAD: "titularidad",
    TipoCatalogo.DEDICACION: "dedicacion",
    TipoCatalogo.CATEGORIA: "categoria",
    TipoCatalogo.NIVEL: "nivel",
    TipoCatalogo.TITULO_PROFESIONAL: "titulo profesional",
    TipoCatalogo.TIPO_TITULO: "tipo de titulo",
    TipoCatalogo.GENERO: "genero",
    TipoCatalogo.ASIGNATURA: "asignatura",
}


@dataclass(slots=True, kw_only=True)
class ElementoCatalogo:
    """Un elemento de cualquiera de los doce catalogos."""

    tipo: TipoCatalogo
    codigo: str
    nombre: str
    descripcion: str = ""
    activo: bool = True
    orden: int = 0

    #: Datos propios del catalogo: `anio`/`periodo` en PAO, `modalidad` en
    #: carrera, `alias` en sede. Se guardan aqui en lugar de multiplicar
    #: columnas que estarian vacias en once de los doce catalogos.
    atributos: dict[str, object] = field(default_factory=dict)

    id: UUID = field(default_factory=uuid4)
    creado_en: datetime = field(default_factory=ahora_utc)
    actualizado_en: datetime = field(default_factory=ahora_utc)

    def __post_init__(self) -> None:
        self.codigo = " ".join((self.codigo or "").split()).upper()
        self.nombre = " ".join((self.nombre or "").split())

        if not self.codigo:
            raise ErrorValidacion("El codigo es obligatorio", campo="codigo")
        if len(self.codigo) > 320:
            raise ErrorValidacion("El codigo excede los 320 caracteres", campo="codigo")
        if not self.nombre:
            raise ErrorValidacion("El nombre es obligatorio", campo="nombre")
        if len(self.nombre) > 320:
            raise ErrorValidacion("El nombre excede los 320 caracteres", campo="nombre")

        if self.tipo is TipoCatalogo.PAO:
            # Valida el formato y deja `anio`, `periodo` y `orden` coherentes con
            # el codigo, para que ordenar por periodo no dependa de la cadena.
            periodo = PeriodoAcademico.desde_codigo(self.codigo)
            self.codigo = periodo.codigo
            self.atributos = {
                **self.atributos,
                "anio": periodo.anio,
                "periodo": periodo.periodo,
            }
            self.orden = periodo.orden

    # ----------------------------------------------------------- propiedades
    @property
    def clave_busqueda(self) -> str:
        """Texto normalizado sin acentos, para la busqueda difusa."""
        return normalizar_texto(f"{self.codigo} {self.nombre} {self.descripcion}")

    @property
    def periodo(self) -> PeriodoAcademico | None:
        """El periodo, cuando el elemento es un PAO."""
        if self.tipo is not TipoCatalogo.PAO:
            return None
        return PeriodoAcademico.desde_codigo(self.codigo)

    # ------------------------------------------------------------ mutaciones
    def actualizar(
        self,
        *,
        nombre: str | None = None,
        descripcion: str | None = None,
        activo: bool | None = None,
        orden: int | None = None,
        atributos: dict[str, object] | None = None,
    ) -> None:
        """Aplica solo los campos recibidos; `None` significa «sin cambio».

        El codigo no se modifica: es la identidad del elemento dentro de su
        catalogo y hay filas del distributivo apuntando a el.
        """
        if nombre is not None:
            self.nombre = " ".join(nombre.split())
        if descripcion is not None:
            self.descripcion = descripcion.strip()
        if activo is not None:
            self.activo = activo
        if orden is not None:
            self.orden = orden
        if atributos is not None:
            self.atributos = {**self.atributos, **atributos}

        self.actualizado_en = ahora_utc()
        self.__post_init__()

    def desactivar(self) -> None:
        """Retira el elemento de los selectores sin borrarlo.

        Es la operacion preferida: un elemento con filas del distributivo
        apuntando a el no puede eliminarse sin dejar el historico inconsistente.
        """
        self.activo = False
        self.actualizado_en = ahora_utc()

    def activar(self) -> None:
        self.activo = True
        self.actualizado_en = ahora_utc()

    def __eq__(self, otro: object) -> bool:
        return isinstance(otro, ElementoCatalogo) and otro.id == self.id

    def __hash__(self) -> int:
        return hash(self.id)
