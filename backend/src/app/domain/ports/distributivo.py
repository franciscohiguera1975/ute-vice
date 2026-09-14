"""Puertos del distributivo docente."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol
from uuid import UUID

from app.domain.alcance import AlcanceAcademico
from app.domain.entities.catalogo import ElementoCatalogo, TipoCatalogo
from app.domain.entities.distributivo import Docente, FilaDistributivo
from app.domain.ports.repositorios import Pagina, Paginacion

# ---------------------------------------------------------------------------
# Filtros
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class FiltroCatalogo:
    texto: str | None = None
    activo: bool | None = None


@dataclass(frozen=True, slots=True)
class FiltroDocentes:
    texto: str | None = None
    """Busqueda difusa sobre nombre e identificacion."""
    identificacion: str | None = None
    genero_id: UUID | None = None
    activo: bool | None = None
    solo_con_pasaporte: bool | None = None
    """Aisla a los docentes cuyo documento no es contrastable con el registro."""
    vinculado_a_persona: bool | None = None


@dataclass(frozen=True, slots=True)
class FiltroDistributivo:
    texto: str | None = None
    """Busqueda difusa sobre el docente: nombre o identificacion."""
    docente_id: UUID | None = None
    pao_id: UUID | None = None
    pao_ids: tuple[UUID, ...] = ()
    facultad_id: UUID | None = None
    facultad_ids: tuple[UUID, ...] = ()
    """Varias facultades a la vez, igual que las carreras y los periodos."""
    carrera_id: UUID | None = None
    carrera_ids: tuple[UUID, ...] = ()
    """Varias carreras a la vez: es como se emite el reporte institucional."""
    sede_id: UUID | None = None
    nivel_id: UUID | None = None
    titularidad_id: UUID | None = None
    dedicacion_id: UUID | None = None
    categoria_id: UUID | None = None
    tipo_titulo_id: UUID | None = None
    sin_asignatura: bool | None = None
    """`True` aisla las filas con docencia pero sin asignatura registrada."""
    con_carga: bool | None = None

    alcance: AlcanceAcademico | None = None
    """Recorte por lo que el usuario puede consultar.

    Lo pone el caso de uso a partir del actor, **nunca la peticion**: si
    viniera de fuera, cualquiera podria ampliarlo pidiendo mas de la cuenta.
    """


# ---------------------------------------------------------------------------
# Vistas de lectura
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class FilaDistributivoResuelta:
    """Una fila con los catalogos ya resueltos a texto.

    Existe para no disparar una consulta por cada catalogo al pintar un listado
    de cien filas. La resuelve el repositorio en una sola pasada.
    """

    fila: FilaDistributivo
    docente_identificacion: str
    docente_nombre: str
    pao: str
    """Nombre legible del periodo: `2026-1 GRADO`."""
    pao_semestre: str
    """El semestre calendario sin el nivel: `2026-1`.

    Es lo que traia el consolidado en su columna `PAO`, y lo que vuelve a salir
    al exportarlo en su formato de origen.
    """
    facultad: str
    carrera: str
    sede: str | None = None
    nivel: str | None = None
    titularidad: str | None = None
    dedicacion: str | None = None
    categoria: str | None = None
    tipo_titulo: str | None = None
    genero: str | None = None

    #: Nombres de las asignaturas de la fila, en el orden en que se escribieron.
    asignaturas: tuple[str, ...] = ()

    #: Titulos profesionales del docente, en el orden del origen. Van en la fila
    #: y no en el docente porque quien exporta el consolidado necesita la fila
    #: completa sin volver a consultar por cada profesor.
    titulos: tuple[str, ...] = ()

    #: Texto con que el consolidado nombraba cada catalogo, antes de que la
    #: importacion lo capitalizara. Solo lo trae la exportacion que reproduce el
    #: archivo de origen; los listados usan los nombres, que se leen mejor.
    codigo_carrera: str | None = None
    codigo_sede: str | None = None
    codigo_nivel: str | None = None
    codigo_titularidad: str | None = None
    codigo_dedicacion: str | None = None
    codigo_categoria: str | None = None
    codigo_tipo_titulo: str | None = None
    codigo_genero: str | None = None


@dataclass(frozen=True, slots=True)
class FilaReporteDocencia:
    """Fila del reporte institucional de docentes por carrera.

    Corresponde una a una con las columnas de la plantilla. Se arma en el
    repositorio porque exige un dato derivado —el periodo mas antiguo en que el
    docente aparece en esa carrera— que se calcula mejor en la base que
    recorriendo el historico en memoria.
    """

    numero: int
    nombre: str
    titulo_profesional: str
    grado_academico: str
    asignatura: str
    anio_inicio_carrera: int | None
    jerarquia_docente: str
    dedicacion_horaria: str
    tipo_contrato: str
    unidad: str
    comuna: str
    anio_actual: int

    #: Datos de apoyo que no salen en la plantilla pero sirven para auditar.
    identificacion: str = ""
    carrera: str = ""
    total_horas: float = 0.0

    #: Horas de docencia de la fila. No se exporta: decide si la fila necesita
    #: una asignatura, que es la regla `requiere_asignatura` del dominio.
    total_docencia: float = 0.0

    @property
    def requiere_asignatura(self) -> bool:
        """`True` si dicta clase y nadie registro que materia."""
        return self.total_docencia > 0 and not self.asignatura


@dataclass(frozen=True, slots=True)
class ResumenDistributivo:
    """Contadores de un conjunto de filas, para el tablero y la cabecera."""

    total_filas: int = 0
    total_docentes: int = 0
    total_horas: float = 0.0
    filas_sin_asignatura: int = 0
    por_categoria: list[tuple[str, int]] = field(default_factory=list)
    por_dedicacion: list[tuple[str, int]] = field(default_factory=list)
    por_facultad: list[tuple[str, int]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Repositorios
# ---------------------------------------------------------------------------


class RepositorioCatalogos(Protocol):
    """Un solo repositorio para los doce catalogos.

    El `tipo` selecciona la tabla. Asi los doce CRUD comparten implementacion sin
    renunciar a tener una tabla —y una clave foranea real— por catalogo.
    """

    async def obtener(self, tipo: TipoCatalogo, elemento_id: UUID) -> ElementoCatalogo | None: ...

    async def obtener_por_codigo(
        self, tipo: TipoCatalogo, codigo: str
    ) -> ElementoCatalogo | None: ...

    async def listar(
        self, tipo: TipoCatalogo, filtro: FiltroCatalogo, paginacion: Paginacion
    ) -> Pagina[ElementoCatalogo]: ...

    async def listar_todos(
        self, tipo: TipoCatalogo, *, solo_activos: bool = True
    ) -> list[ElementoCatalogo]:
        """Catalogo completo, para poblar un selector."""
        ...

    async def agregar(self, elemento: ElementoCatalogo) -> ElementoCatalogo: ...

    async def agregar_muchos(self, elementos: list[ElementoCatalogo]) -> int: ...

    async def actualizar(self, elemento: ElementoCatalogo) -> ElementoCatalogo: ...

    async def eliminar(self, tipo: TipoCatalogo, elemento_id: UUID) -> None: ...

    async def existe_codigo(
        self, tipo: TipoCatalogo, codigo: str, *, excluyendo: UUID | None = None
    ) -> bool: ...

    async def contar_referencias(self, tipo: TipoCatalogo, elemento_id: UUID) -> int:
        """Filas del distributivo que apuntan a este elemento.

        Se consulta antes de eliminar: un catalogo referenciado no se borra, se
        desactiva, para no dejar el historico sin el dato.
        """
        ...


class RepositorioDocentes(Protocol):
    async def obtener(self, docente_id: UUID) -> Docente | None: ...

    async def obtener_por_identificacion(self, identificacion: str) -> Docente | None: ...

    async def listar(self, filtro: FiltroDocentes, paginacion: Paginacion) -> Pagina[Docente]: ...

    async def agregar(self, docente: Docente) -> Docente: ...

    async def agregar_muchos(self, docentes: list[Docente]) -> int: ...

    async def actualizar(self, docente: Docente) -> Docente: ...

    async def eliminar(self, docente_id: UUID) -> None: ...

    async def existe_identificacion(
        self, identificacion: str, *, excluyendo: UUID | None = None
    ) -> bool: ...

    async def contar_filas(self, docente_id: UUID) -> int: ...

    async def titulos_de(self, docente_id: UUID) -> list[ElementoCatalogo]: ...


class RepositorioDistributivo(Protocol):
    async def obtener(self, fila_id: UUID) -> FilaDistributivo | None: ...

    async def obtener_resuelta(self, fila_id: UUID) -> FilaDistributivoResuelta | None: ...

    async def listar(
        self, filtro: FiltroDistributivo, paginacion: Paginacion
    ) -> Pagina[FilaDistributivoResuelta]: ...

    async def agregar(self, fila: FilaDistributivo) -> FilaDistributivo: ...

    async def agregar_muchas(self, filas: list[FilaDistributivo]) -> int: ...

    async def actualizar(self, fila: FilaDistributivo) -> FilaDistributivo: ...

    async def eliminar(self, fila_id: UUID) -> None: ...

    async def existe_combinacion(
        self,
        *,
        docente_id: UUID,
        pao_id: UUID,
        carrera_id: UUID,
        sede_id: UUID | None = None,
        excluyendo: UUID | None = None,
    ) -> bool:
        """`(docente, periodo, carrera, sede)` es la clave natural de una fila.

        La sede entra en la clave porque un docente si dicta la misma carrera en
        dos campus el mismo periodo.
        """
        ...

    async def resumen(self, filtro: FiltroDistributivo) -> ResumenDistributivo: ...

    async def filas_para_reporte(self, filtro: FiltroDistributivo) -> list[FilaReporteDocencia]:
        """Arma el reporte institucional, con el anio de inicio ya derivado."""
        ...

    async def unidades_por_docente(self) -> dict[UUID, str]:
        """Facultad de cada docente en su periodo mas reciente.

        Sirve para poblar la `unidad` de las personas: un docente puede haber
        cambiado de facultad a lo largo del historico, y la que corresponde es
        la ultima, no una cualquiera.
        """
        ...

    async def carreras_presentes(self, filtro: FiltroDistributivo) -> list[ElementoCatalogo]:
        """Carreras que **de hecho** aparecen en las filas del filtro.

        Es la relacion entre facultades y carreras, derivada de los datos en
        lugar de guardada en una columna. Tiene que ser asi: doce carreras se
        dictan en dos facultades a la vez —la facultad y la unidad en linea—, y
        una columna `facultad_id` en el catalogo obligaria a elegir una de las
        dos y a equivocarse en la otra.
        """
        ...

    async def filas_resueltas(self, filtro: FiltroDistributivo) -> list[FilaDistributivoResuelta]:
        """Todas las filas del filtro, sin paginar.

        La usa la exportacion, que necesita el conjunto entero y no una pagina.
        El filtro siempre acota a un periodo, asi que el conjunto es del orden
        de unos miles de filas, no del historico completo.
        """
        ...
