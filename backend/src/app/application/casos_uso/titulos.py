"""Casos de uso sobre titulos academicos.

La escritura manual de titulos convive con la automatica. Un titulo cargado a
mano nace `POR_VERIFICAR` y de origen `MANUAL`: eso lo protege del reconciliador
—que solo retira lo que el mismo trajo— y deja explicito que su respaldo es
documental, no el registro nacional.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from uuid import UUID

from app.application.base import CasoDeUso, ContextoEjecucion
from app.domain.entities.titulo import Titulo
from app.domain.enums import EstadoTitulo, NivelTitulo, OrigenTitulo, Permiso
from app.domain.errors import NoEncontrado, ReglaDeNegocioViolada, YaExiste
from app.domain.ports.repositorios import FiltroTitulos, Pagina, Paginacion
from app.domain.ports.uow import UnidadDeTrabajo


@dataclass(frozen=True, slots=True)
class EntradaCrearTitulo:
    persona_id: UUID
    denominacion: str
    institucion: str
    nivel: NivelTitulo | None = None
    numero_registro: str | None = None
    fecha_registro: date | None = None
    fecha_graduacion: date | None = None
    area_conocimiento: str | None = None
    pais: str = "ECUADOR"
    observacion_registro: str | None = None


@dataclass(frozen=True, slots=True)
class EntradaActualizarTitulo:
    titulo_id: UUID
    denominacion: str | None = None
    institucion: str | None = None
    nivel: NivelTitulo | None = None
    numero_registro: str | None = None
    fecha_registro: date | None = None
    fecha_graduacion: date | None = None
    area_conocimiento: str | None = None
    observacion_registro: str | None = None


@dataclass(frozen=True, slots=True)
class EntradaListarTitulos:
    filtro: FiltroTitulos = field(default_factory=FiltroTitulos)
    paginacion: Paginacion = field(default_factory=Paginacion)


# ---------------------------------------------------------------------------


class CrearTitulo(CasoDeUso[EntradaCrearTitulo, Titulo]):
    """Registra un titulo a mano, con respaldo documental."""

    nombre = "titulos.crear"
    descripcion = "Registra manualmente un titulo academico de una persona"
    permiso_requerido = Permiso.TITULOS_ESCRIBIR

    def __init__(self, uow: UnidadDeTrabajo) -> None:
        self._uow = uow

    async def _ejecutar(self, entrada: EntradaCrearTitulo, contexto: ContextoEjecucion) -> Titulo:
        async with self._uow:
            persona = await self._uow.personas.obtener(entrada.persona_id)
            if persona is None:
                raise NoEncontrado("Persona", entrada.persona_id)

            titulo = Titulo(
                persona_id=entrada.persona_id,
                denominacion=entrada.denominacion,
                institucion=entrada.institucion,
                nivel=entrada.nivel or NivelTitulo.NO_DETERMINADO,
                numero_registro=entrada.numero_registro,
                fecha_registro=entrada.fecha_registro,
                fecha_graduacion=entrada.fecha_graduacion,
                area_conocimiento=entrada.area_conocimiento,
                pais=entrada.pais.upper(),
                observacion_registro=entrada.observacion_registro,
                origen=OrigenTitulo.MANUAL,
                estado=EstadoTitulo.POR_VERIFICAR,
            )

            # La huella evita duplicar un titulo que ya existe para esa persona.
            existentes = await self._uow.titulos.listar_por_persona(entrada.persona_id)
            if any(t.huella == titulo.huella for t in existentes):
                raise YaExiste("titulo", "huella", titulo.denominacion)

            creado = await self._uow.titulos.agregar(titulo)
            persona.titulos_registrados = len(existentes) + 1
            await self._uow.personas.actualizar(persona)
            await self._uow.commit()
            return creado


class ActualizarTitulo(CasoDeUso[EntradaActualizarTitulo, Titulo]):
    """Corrige los datos de un titulo.

    Un titulo de origen SENESCYT no se edita: sus datos provienen del registro
    nacional y modificarlos crearia una discrepancia silenciosa que la siguiente
    consulta revertiria sin dejar rastro.
    """

    nombre = "titulos.actualizar"
    descripcion = "Corrige los datos de un titulo cargado manualmente"
    permiso_requerido = Permiso.TITULOS_ESCRIBIR

    def __init__(self, uow: UnidadDeTrabajo) -> None:
        self._uow = uow

    async def _ejecutar(
        self, entrada: EntradaActualizarTitulo, contexto: ContextoEjecucion
    ) -> Titulo:
        async with self._uow:
            titulo = await self._uow.titulos.obtener(entrada.titulo_id)
            if titulo is None:
                raise NoEncontrado("Titulo", entrada.titulo_id)

            if titulo.origen is OrigenTitulo.SENESCYT:
                raise ReglaDeNegocioViolada(
                    "Este titulo proviene del registro nacional y no puede editarse. "
                    "Para corregirlo, ejecute una consulta de actualizacion."
                )

            if entrada.denominacion is not None:
                titulo.denominacion = entrada.denominacion
            if entrada.institucion is not None:
                titulo.institucion = entrada.institucion
            if entrada.nivel is not None:
                titulo.nivel = entrada.nivel
            if entrada.numero_registro is not None:
                titulo.numero_registro = entrada.numero_registro or None
            if entrada.fecha_registro is not None:
                titulo.fecha_registro = entrada.fecha_registro
            if entrada.fecha_graduacion is not None:
                titulo.fecha_graduacion = entrada.fecha_graduacion
            if entrada.area_conocimiento is not None:
                titulo.area_conocimiento = entrada.area_conocimiento
            if entrada.observacion_registro is not None:
                titulo.observacion_registro = entrada.observacion_registro

            # La huella se recalcula: los campos que la componen pudieron cambiar.
            titulo.huella = Titulo.calcular_huella(
                denominacion=titulo.denominacion,
                institucion=titulo.institucion,
                numero_registro=titulo.numero_registro,
            )
            titulo.__post_init__()

            actualizado = await self._uow.titulos.actualizar(titulo)
            await self._uow.commit()
            return actualizado


class ListarTitulos(CasoDeUso[EntradaListarTitulos, Pagina[Titulo]]):
    nombre = "titulos.listar"
    descripcion = "Lista titulos con filtros y paginacion"
    permiso_requerido = Permiso.TITULOS_LEER

    def __init__(self, uow: UnidadDeTrabajo) -> None:
        self._uow = uow

    async def _ejecutar(
        self, entrada: EntradaListarTitulos, contexto: ContextoEjecucion
    ) -> Pagina[Titulo]:
        async with self._uow:
            return await self._uow.titulos.listar(entrada.filtro, entrada.paginacion)


class ObtenerTitulo(CasoDeUso[UUID, Titulo]):
    nombre = "titulos.obtener"
    descripcion = "Obtiene un titulo por su identificador"
    permiso_requerido = Permiso.TITULOS_LEER

    def __init__(self, uow: UnidadDeTrabajo) -> None:
        self._uow = uow

    async def _ejecutar(self, entrada: UUID, contexto: ContextoEjecucion) -> Titulo:
        async with self._uow:
            titulo = await self._uow.titulos.obtener(entrada)
            if titulo is None:
                raise NoEncontrado("Titulo", entrada)
            return titulo


class VerificarTitulo(CasoDeUso[UUID, Titulo]):
    """Un analista da fe de que reviso el respaldo documental del titulo."""

    nombre = "titulos.verificar"
    descripcion = "Marca un titulo como verificado por un funcionario"
    permiso_requerido = Permiso.TITULOS_VERIFICAR

    def __init__(self, uow: UnidadDeTrabajo) -> None:
        self._uow = uow

    async def _ejecutar(self, entrada: UUID, contexto: ContextoEjecucion) -> Titulo:
        if contexto.actor is None:
            raise ReglaDeNegocioViolada("La verificacion requiere un usuario identificado")

        async with self._uow:
            titulo = await self._uow.titulos.obtener(entrada)
            if titulo is None:
                raise NoEncontrado("Titulo", entrada)

            titulo.marcar_verificado(contexto.actor.id)
            actualizado = await self._uow.titulos.actualizar(titulo)
            await self._uow.commit()
            return actualizado


class EliminarTitulo(CasoDeUso[UUID, None]):
    """Elimina un titulo cargado manualmente.

    Los de origen SENESCYT no se borran: si dejaron de ser validos, la via es
    marcarlos retirados, que es lo que hace el reconciliador automaticamente.
    """

    nombre = "titulos.eliminar"
    descripcion = "Elimina un titulo cargado manualmente"
    permiso_requerido = Permiso.TITULOS_ELIMINAR

    def __init__(self, uow: UnidadDeTrabajo) -> None:
        self._uow = uow

    async def _ejecutar(self, entrada: UUID, contexto: ContextoEjecucion) -> None:
        async with self._uow:
            titulo = await self._uow.titulos.obtener(entrada)
            if titulo is None:
                raise NoEncontrado("Titulo", entrada)
            if titulo.origen is OrigenTitulo.SENESCYT:
                raise ReglaDeNegocioViolada(
                    "Un titulo obtenido del registro nacional no se elimina. "
                    "Si dejo de estar vigente, quedara marcado como retirado en la "
                    "proxima consulta."
                )

            persona = await self._uow.personas.obtener(titulo.persona_id)
            await self._uow.titulos.eliminar(titulo.id)
            if persona is not None:
                persona.titulos_registrados = max(0, persona.titulos_registrados - 1)
                await self._uow.personas.actualizar(persona)
            await self._uow.commit()
