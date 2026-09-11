"""Casos de uso sobre docentes del distributivo."""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from app.application.base import CasoDeUso, ContextoEjecucion
from app.domain.entities.catalogo import ElementoCatalogo, TipoCatalogo
from app.domain.entities.distributivo import Docente
from app.domain.enums import Permiso
from app.domain.errors import NoEncontrado, ReglaDeNegocioViolada, YaExiste
from app.domain.ports.distributivo import FiltroDocentes
from app.domain.ports.repositorios import Pagina, Paginacion
from app.domain.ports.uow import UnidadDeTrabajo
from app.domain.value_objects import Cedula
from app.domain.value_objects_distributivo import Identificacion


@dataclass(frozen=True, slots=True)
class EntradaListarDocentes:
    filtro: FiltroDocentes = field(default_factory=FiltroDocentes)
    paginacion: Paginacion = field(default_factory=Paginacion)


@dataclass(frozen=True, slots=True)
class EntradaCrearDocente:
    identificacion: str
    nombre_completo: str
    genero_id: UUID | None = None
    titulos_ids: tuple[UUID, ...] = ()
    observaciones: str | None = None


@dataclass(frozen=True, slots=True)
class EntradaActualizarDocente:
    docente_id: UUID
    nombre_completo: str | None = None
    genero_id: UUID | None = None
    titulos_ids: tuple[UUID, ...] | None = None
    activo: bool | None = None
    observaciones: str | None = None


@dataclass(frozen=True, slots=True)
class DocenteDetalle:
    docente: Docente
    titulos: list[ElementoCatalogo] = field(default_factory=list)
    total_filas: int = 0


# ---------------------------------------------------------------------------


class ListarDocentes(CasoDeUso[EntradaListarDocentes, Pagina[Docente]]):
    nombre = "docentes.listar"
    descripcion = "Lista los docentes del distributivo"
    permiso_requerido = Permiso.DISTRIBUTIVO_LEER

    def __init__(self, uow: UnidadDeTrabajo) -> None:
        self._uow = uow

    async def _ejecutar(
        self, entrada: EntradaListarDocentes, contexto: ContextoEjecucion
    ) -> Pagina[Docente]:
        async with self._uow:
            return await self._uow.docentes.listar(entrada.filtro, entrada.paginacion)


class ObtenerDocente(CasoDeUso[UUID, DocenteDetalle]):
    """Detalle de un docente con sus titulos profesionales."""

    nombre = "docentes.obtener"
    descripcion = "Obtiene un docente con sus titulos profesionales"
    permiso_requerido = Permiso.DISTRIBUTIVO_LEER

    def __init__(self, uow: UnidadDeTrabajo) -> None:
        self._uow = uow

    async def _ejecutar(self, entrada: UUID, contexto: ContextoEjecucion) -> DocenteDetalle:
        async with self._uow:
            docente = await self._uow.docentes.obtener(entrada)
            if docente is None:
                raise NoEncontrado("Docente", entrada)
            return DocenteDetalle(
                docente=docente,
                titulos=await self._uow.docentes.titulos_de(entrada),
                total_filas=await self._uow.docentes.contar_filas(entrada),
            )


class CrearDocente(CasoDeUso[EntradaCrearDocente, Docente]):
    """Registra un docente.

    Si la identificacion es una cedula y esa persona ya existe en el padron del
    expediente academico, se enlazan automaticamente: es el mismo empleado visto
    desde dos modulos, y mantenerlos separados obligaria a actualizar dos veces.
    """

    nombre = "docentes.crear"
    descripcion = "Registra un docente del distributivo"
    permiso_requerido = Permiso.DISTRIBUTIVO_ESCRIBIR

    def __init__(self, uow: UnidadDeTrabajo) -> None:
        self._uow = uow

    async def _ejecutar(self, entrada: EntradaCrearDocente, contexto: ContextoEjecucion) -> Docente:
        identificacion = Identificacion(entrada.identificacion)

        async with self._uow:
            if await self._uow.docentes.existe_identificacion(identificacion.valor):
                raise YaExiste("docente", "identificacion", identificacion.valor)

            docente = Docente(
                identificacion=identificacion,
                nombre_completo=entrada.nombre_completo,
                genero_id=entrada.genero_id,
                titulos_ids=list(entrada.titulos_ids),
                observaciones=entrada.observaciones,
                persona_id=await self._buscar_persona(identificacion),
            )
            creado = await self._uow.docentes.agregar(docente)
            await self._uow.commit()
            return creado

    async def _buscar_persona(self, identificacion: Identificacion) -> UUID | None:
        """Enlaza con el expediente academico si la cedula ya esta registrada."""
        if not identificacion.es_cedula:
            return None
        persona = await self._uow.personas.obtener_por_cedula(Cedula(identificacion.valor))
        return persona.id if persona else None


class ActualizarDocente(CasoDeUso[EntradaActualizarDocente, Docente]):
    """Modifica un docente.

    La identificacion no se cambia: es su identidad en el consolidado y en el
    historico. Un error de digitacion se corrige creando el registro correcto y
    reasignando sus filas.
    """

    nombre = "docentes.actualizar"
    descripcion = "Modifica los datos de un docente"
    permiso_requerido = Permiso.DISTRIBUTIVO_ESCRIBIR

    def __init__(self, uow: UnidadDeTrabajo) -> None:
        self._uow = uow

    async def _ejecutar(
        self, entrada: EntradaActualizarDocente, contexto: ContextoEjecucion
    ) -> Docente:
        async with self._uow:
            docente = await self._uow.docentes.obtener(entrada.docente_id)
            if docente is None:
                raise NoEncontrado("Docente", entrada.docente_id)

            docente.actualizar(
                nombre_completo=entrada.nombre_completo,
                genero_id=entrada.genero_id,
                activo=entrada.activo,
                observaciones=entrada.observaciones,
            )
            if entrada.titulos_ids is not None:
                await self._validar_titulos(entrada.titulos_ids)
                docente.establecer_titulos(list(entrada.titulos_ids))

            actualizado = await self._uow.docentes.actualizar(docente)
            await self._uow.commit()
            return actualizado

    async def _validar_titulos(self, titulos_ids: tuple[UUID, ...]) -> None:
        for titulo_id in titulos_ids:
            if (
                await self._uow.catalogos.obtener(TipoCatalogo.TITULO_PROFESIONAL, titulo_id)
            ) is None:
                raise NoEncontrado("Titulo profesional", titulo_id)


class EliminarDocente(CasoDeUso[UUID, None]):
    """Elimina un docente sin filas en el distributivo.

    Con filas registradas se rechaza: borrarlo arrastraria su historico de carga
    horaria. La via correcta es desactivarlo.
    """

    nombre = "docentes.eliminar"
    descripcion = "Elimina un docente que no tenga filas en el distributivo"
    permiso_requerido = Permiso.DISTRIBUTIVO_ELIMINAR

    def __init__(self, uow: UnidadDeTrabajo) -> None:
        self._uow = uow

    async def _ejecutar(self, entrada: UUID, contexto: ContextoEjecucion) -> None:
        async with self._uow:
            docente = await self._uow.docentes.obtener(entrada)
            if docente is None:
                raise NoEncontrado("Docente", entrada)

            filas = await self._uow.docentes.contar_filas(entrada)
            if filas:
                raise ReglaDeNegocioViolada(
                    f"El docente tiene {filas} fila(s) en el distributivo. "
                    "Desactivelo en lugar de eliminarlo para conservar el historico."
                )

            await self._uow.docentes.eliminar(entrada)
            await self._uow.commit()
