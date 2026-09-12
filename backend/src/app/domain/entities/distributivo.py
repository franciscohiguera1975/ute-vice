"""Entidades del distributivo docente.

El distributivo es el reparto de carga horaria del profesorado por periodo
academico. Una fila responde: *este docente, en este periodo, dicto en esta
carrera de esta facultad, con este contrato y esta distribucion de horas*.

Dos entidades:

* `Docente` — la persona, con lo que no cambia entre periodos: su documento, su
  nombre y su genero, mas el conjunto de titulos profesionales que se le conocen.
* `FilaDistributivo` — la fotografia de un periodo. Titularidad, dedicacion,
  categoria, sede y facultad viven aqui y no en el docente, porque cambian: en el
  padron real, el 27% de los docentes cambia de categoria y el 19% de sede a lo
  largo del historico.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4

from app.domain.errors import ErrorValidacion
from app.domain.value_objects import ahora_utc, normalizar_texto
from app.domain.value_objects_distributivo import DistribucionHoras, Identificacion

#: Separadores con los que el consolidado concatena varios titulos en una celda.
#:
#: El principal es `&`. El origen tambien usa la coma, con espaciado
#: inconsistente: ` , `, ` ,` y `, `. Se exige espacio en al menos un lado para
#: no partir una coma interna de un titulo.
#:
#: Se verifico sobre el consolidado completo: ningun titulo tiene una coma
#: pegada por ambos lados (`\w,\w`), asi que este criterio no rompe ninguno.
_SEPARADOR_TITULOS = re.compile(r"\s*&\s*|\s+,\s*|\s*,\s+")


@dataclass(slots=True, kw_only=True)
class Docente:
    """Profesor del padron.

    `persona_id` enlaza —cuando se puede— con el expediente academico del modulo
    de personas. Es opcional a proposito: el distributivo incluye docentes con
    pasaporte, que no tienen cedula contra la cual consultar al registro
    nacional. Exigir el enlace dejaria fuera a esos docentes.
    """

    identificacion: Identificacion
    nombre_completo: str
    genero_id: UUID | None = None
    persona_id: UUID | None = None

    #: Titulos profesionales conocidos del docente, en el orden del origen.
    #: Es la union de lo reportado en todos sus periodos: el consolidado los
    #: acumula a medida que la persona obtiene grados nuevos.
    titulos_ids: list[UUID] = field(default_factory=list)

    activo: bool = True
    observaciones: str | None = None

    id: UUID = field(default_factory=uuid4)
    creado_en: datetime = field(default_factory=ahora_utc)
    actualizado_en: datetime = field(default_factory=ahora_utc)

    def __post_init__(self) -> None:
        self.nombre_completo = " ".join((self.nombre_completo or "").split()).upper()
        if not self.nombre_completo:
            raise ErrorValidacion("El nombre del docente es obligatorio", campo="nombre_completo")
        if len(self.nombre_completo) > 200:
            raise ErrorValidacion("El nombre excede los 200 caracteres", campo="nombre_completo")

    @property
    def clave_busqueda(self) -> str:
        return normalizar_texto(f"{self.nombre_completo} {self.identificacion.valor}")

    @property
    def puede_validarse_en_registro(self) -> bool:
        """`True` si el documento es una cedula contrastable con el SENESCYT."""
        return self.identificacion.es_cedula

    def actualizar(
        self,
        *,
        nombre_completo: str | None = None,
        genero_id: UUID | None = None,
        persona_id: UUID | None = None,
        activo: bool | None = None,
        observaciones: str | None = None,
    ) -> None:
        if nombre_completo is not None:
            self.nombre_completo = nombre_completo
        if genero_id is not None:
            self.genero_id = genero_id
        if persona_id is not None:
            self.persona_id = persona_id
        if activo is not None:
            self.activo = activo
        if observaciones is not None:
            self.observaciones = observaciones
        self.actualizado_en = ahora_utc()
        self.__post_init__()

    def establecer_titulos(self, titulos_ids: list[UUID]) -> None:
        """Reemplaza el conjunto de titulos, conservando el orden y sin repetir."""
        vistos: set[UUID] = set()
        unicos: list[UUID] = []
        for titulo_id in titulos_ids:
            if titulo_id not in vistos:
                vistos.add(titulo_id)
                unicos.append(titulo_id)
        self.titulos_ids = unicos
        self.actualizado_en = ahora_utc()

    def __eq__(self, otro: object) -> bool:
        return isinstance(otro, Docente) and otro.id == self.id

    def __hash__(self) -> int:
        return hash(self.id)


@dataclass(slots=True, kw_only=True)
class FilaDistributivo:
    """Carga de un docente en una carrera durante un periodo academico.

    La clave natural es `(docente, pao, carrera)`: un mismo docente puede dictar
    en varias carreras el mismo periodo, y cada combinacion es una fila con su
    propia distribucion de horas.
    """

    docente_id: UUID
    pao_id: UUID
    facultad_id: UUID
    carrera_id: UUID

    sede_id: UUID | None = None
    nivel_id: UUID | None = None
    titularidad_id: UUID | None = None
    dedicacion_id: UUID | None = None
    categoria_id: UUID | None = None
    tipo_titulo_id: UUID | None = None

    #: Asignatura que imparte. **No viene del consolidado**: el distributivo
    #: reparte horas por tipo de actividad, no por materia. Se captura a mano
    #: porque el reporte institucional la exige; mientras nadie la complete,
    #: viaja vacia al Excel en lugar de rellenarse con un dato inventado.
    #:
    #: Apuntan al catalogo y no son texto libre: el mismo nombre escrito de dos
    #: formas en cien filas se corrige una sola vez, en el catalogo, en lugar
    #: de cien. La pantalla de captura sigue admitiendo texto y crea el
    #: elemento cuando no existe, para no volver lenta la carga masiva.
    #:
    #: Son **varias**: un docente puede dictar mas de una materia en la misma
    #: carrera y periodo, y el consolidado no las distingue —reparte horas por
    #: tipo de actividad, no por materia—, asi que la fila es una sola y las
    #: asignaturas, muchas. El orden se conserva: es el que se escribio.
    asignaturas_ids: list[UUID] = field(default_factory=list)

    horas: DistribucionHoras = field(default_factory=DistribucionHoras.vacia)

    #: Medida administrativa del periodo (contratos nuevos, reducciones de
    #: jornada). Texto libre en el origen.
    medida: str | None = None
    observaciones: str | None = None

    id: UUID = field(default_factory=uuid4)
    creado_en: datetime = field(default_factory=ahora_utc)
    actualizado_en: datetime = field(default_factory=ahora_utc)
    creado_por: UUID | None = None

    def __post_init__(self) -> None:
        if self.medida is not None:
            self.medida = " ".join(self.medida.split()) or None

    # ----------------------------------------------------------- propiedades
    @property
    def total_horas(self) -> float:
        return self.horas.total

    @property
    def tiene_carga(self) -> bool:
        return self.total_horas > 0

    @property
    def requiere_asignatura(self) -> bool:
        """`True` si la fila dicta clase pero nadie registro que asignatura.

        Es lo que el reporte institucional deja en blanco, asi que sirve para
        saber cuanto falta por completar antes de emitirlo.
        """
        return self.horas.total_docencia > 0 and not self.asignaturas_ids

    # ------------------------------------------------------------ mutaciones
    def definir_asignaturas(self, asignaturas_ids: Iterable[UUID]) -> None:
        """Reemplaza las asignaturas. Una lista vacia las retira todas.

        Va aparte de `actualizar` porque alli un valor ausente significa «no lo
        cambies», y aqui una lista vacia tiene que significar «quitalas»: sin
        este metodo no habria forma de corregir una asignacion equivocada.

        Conserva el orden y descarta repetidas: escribir «Calculo, Calculo» no
        deja la materia dos veces en la misma fila.
        """
        vistas: set[UUID] = set()
        unicas: list[UUID] = []
        for asignatura_id in asignaturas_ids:
            if asignatura_id not in vistas:
                vistas.add(asignatura_id)
                unicas.append(asignatura_id)
        self.asignaturas_ids = unicas
        self.actualizado_en = ahora_utc()

    def actualizar(
        self,
        *,
        facultad_id: UUID | None = None,
        carrera_id: UUID | None = None,
        sede_id: UUID | None = None,
        nivel_id: UUID | None = None,
        titularidad_id: UUID | None = None,
        dedicacion_id: UUID | None = None,
        categoria_id: UUID | None = None,
        tipo_titulo_id: UUID | None = None,
        asignaturas_ids: Iterable[UUID] | None = None,
        horas: DistribucionHoras | None = None,
        medida: str | None = None,
        observaciones: str | None = None,
    ) -> None:
        """Aplica solo los campos recibidos.

        `docente_id` y `pao_id` no se modifican: cambiarlos convertiria la fila
        en otra distinta. Para eso se crea una nueva y se elimina esta.
        """
        if facultad_id is not None:
            self.facultad_id = facultad_id
        if carrera_id is not None:
            self.carrera_id = carrera_id
        if sede_id is not None:
            self.sede_id = sede_id
        if nivel_id is not None:
            self.nivel_id = nivel_id
        if titularidad_id is not None:
            self.titularidad_id = titularidad_id
        if dedicacion_id is not None:
            self.dedicacion_id = dedicacion_id
        if categoria_id is not None:
            self.categoria_id = categoria_id
        if tipo_titulo_id is not None:
            self.tipo_titulo_id = tipo_titulo_id
        if asignaturas_ids is not None:
            self.definir_asignaturas(asignaturas_ids)
        if horas is not None:
            self.horas = horas
        if medida is not None:
            self.medida = medida
        if observaciones is not None:
            self.observaciones = observaciones

        self.actualizado_en = ahora_utc()
        self.__post_init__()

    def __eq__(self, otro: object) -> bool:
        return isinstance(otro, FilaDistributivo) and otro.id == self.id

    def __hash__(self) -> int:
        return hash(self.id)


def separar_asignaturas(crudo: str | None) -> list[str]:
    """Parte «Calculo I, Algebra Lineal» en materias individuales.

    La coma es el separador porque es el que pide el reporte: cuando una fila
    tiene varias materias, salen todas en la misma celda separadas por comas.
    Usar el mismo signo para entrar y para salir evita que quien captura tenga
    que recordar dos convenciones.

    **El limite de esto**: una materia cuyo nombre lleve una coma se parte en
    dos. Para esos casos esta el selector del formulario, que elige del
    catalogo y no interpreta el texto.
    """
    if not crudo:
        return []

    limpias: list[str] = []
    vistas: set[str] = set()
    for parte in str(crudo).split(","):
        normalizada = " ".join(parte.split())
        if not normalizada:
            continue
        clave = normalizar_texto(normalizada)
        if clave in vistas:
            continue
        vistas.add(clave)
        limpias.append(normalizada)
    return limpias


def separar_titulos(crudo: str | None) -> list[str]:
    """Parte la celda `TITULO` del consolidado en titulos individuales.

    El origen concatena con ` & ` —hasta doce titulos en una sola celda—, asi que
    guardarla tal cual haria imposible buscar por titulo o contar cuantos
    docentes tienen uno determinado.
    """
    if not crudo:
        return []

    partes = [p.strip(" ,;") for p in _SEPARADOR_TITULOS.split(str(crudo))]

    limpias: list[str] = []
    vistos: set[str] = set()
    for parte in partes:
        normalizada = " ".join(parte.split()).upper()
        if not normalizada or normalizada in {"NA", "N/A", "-"}:
            continue
        clave = normalizar_texto(normalizada)
        if clave in vistos:
            continue
        vistos.add(clave)
        limpias.append(normalizada)
    return limpias
