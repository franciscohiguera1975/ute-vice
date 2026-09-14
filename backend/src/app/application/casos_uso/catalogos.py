"""Casos de uso de los catalogos del distributivo.

Un solo juego de casos de uso sirve a los doce catalogos. El `tipo` viaja en la
entrada y selecciona la tabla; las reglas —codigo unico, no borrar lo que esta
referenciado— son las mismas para todos, asi que escribirlas doce veces solo
multiplicaria las oportunidades de que una se olvide.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from app.application.base import CasoDeUso, ContextoEjecucion
from app.domain.entities.catalogo import ElementoCatalogo, TipoCatalogo
from app.domain.enums import Permiso
from app.domain.errors import NoEncontrado, ReglaDeNegocioViolada, YaExiste
from app.domain.ports.distributivo import FiltroCatalogo
from app.domain.ports.repositorios import Pagina, Paginacion
from app.domain.ports.uow import UnidadDeTrabajo


@dataclass(frozen=True, slots=True)
class EntradaListarCatalogo:
    tipo: TipoCatalogo
    filtro: FiltroCatalogo = field(default_factory=FiltroCatalogo)
    paginacion: Paginacion = field(default_factory=Paginacion)


@dataclass(frozen=True, slots=True)
class EntradaCatalogoCompleto:
    tipo: TipoCatalogo
    solo_activos: bool = True


@dataclass(frozen=True, slots=True)
class EntradaCrearElemento:
    tipo: TipoCatalogo
    codigo: str
    nombre: str
    descripcion: str = ""
    activo: bool = True
    orden: int = 0
    codigo_erp: str = ""
    atributos: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class EntradaActualizarElemento:
    tipo: TipoCatalogo
    elemento_id: UUID
    nombre: str | None = None
    descripcion: str | None = None
    activo: bool | None = None
    orden: int | None = None
    codigo_erp: str | None = None
    atributos: dict[str, object] | None = None


@dataclass(frozen=True, slots=True)
class EntradaObtenerElemento:
    tipo: TipoCatalogo
    elemento_id: UUID


# ---------------------------------------------------------------------------


class ListarCatalogo(CasoDeUso[EntradaListarCatalogo, Pagina[ElementoCatalogo]]):
    """Lista un catalogo con filtros y paginacion."""

    nombre = "catalogos.listar"
    descripcion = "Lista los elementos de un catalogo del distributivo"
    permiso_requerido = Permiso.CATALOGOS_LEER

    def __init__(self, uow: UnidadDeTrabajo) -> None:
        self._uow = uow

    async def _ejecutar(
        self, entrada: EntradaListarCatalogo, contexto: ContextoEjecucion
    ) -> Pagina[ElementoCatalogo]:
        async with self._uow:
            return await self._uow.catalogos.listar(
                entrada.tipo, entrada.filtro, entrada.paginacion
            )


class ObtenerCatalogoCompleto(CasoDeUso[EntradaCatalogoCompleto, list[ElementoCatalogo]]):
    """Catalogo entero, sin paginar, para poblar un selector.

    Es una operacion distinta de `listar` a proposito: un selector necesita
    todos los elementos de una vez, y paginarlo obligaria al frontend a
    encadenar peticiones para mostrar un desplegable.
    """

    nombre = "catalogos.completo"
    descripcion = "Devuelve un catalogo completo para poblar un selector"
    permiso_requerido = Permiso.CATALOGOS_LEER

    def __init__(self, uow: UnidadDeTrabajo) -> None:
        self._uow = uow

    async def _ejecutar(
        self, entrada: EntradaCatalogoCompleto, contexto: ContextoEjecucion
    ) -> list[ElementoCatalogo]:
        async with self._uow:
            elementos = await self._uow.catalogos.listar_todos(
                entrada.tipo, solo_activos=entrada.solo_activos
            )

        # Los selectores de facultad y carrera se recortan al alcance del
        # usuario: ofrecer opciones que luego no devuelven nada seria un
        # desplegable lleno de callejones sin salida. Los otros diez catalogos
        # —sede, dedicacion, genero…— no acotan a nadie y van completos.
        alcance = contexto.alcance
        if alcance.es_total:
            return elementos
        if entrada.tipo is TipoCatalogo.FACULTAD and alcance.facultades:
            return [e for e in elementos if e.id in alcance.facultades]
        if entrada.tipo is TipoCatalogo.CARRERA and alcance.carreras:
            return [e for e in elementos if e.id in alcance.carreras]
        return elementos


class ObtenerElementoCatalogo(CasoDeUso[EntradaObtenerElemento, ElementoCatalogo]):
    nombre = "catalogos.obtener"
    descripcion = "Obtiene un elemento de catalogo por su identificador"
    permiso_requerido = Permiso.CATALOGOS_LEER

    def __init__(self, uow: UnidadDeTrabajo) -> None:
        self._uow = uow

    async def _ejecutar(
        self, entrada: EntradaObtenerElemento, contexto: ContextoEjecucion
    ) -> ElementoCatalogo:
        async with self._uow:
            elemento = await self._uow.catalogos.obtener(entrada.tipo, entrada.elemento_id)
            if elemento is None:
                raise NoEncontrado(entrada.tipo.singular, entrada.elemento_id)
            return elemento


class CrearElementoCatalogo(CasoDeUso[EntradaCrearElemento, ElementoCatalogo]):
    """Agrega un elemento a un catalogo."""

    nombre = "catalogos.crear"
    descripcion = "Agrega un elemento a un catalogo del distributivo"
    permiso_requerido = Permiso.CATALOGOS_ESCRIBIR

    def __init__(self, uow: UnidadDeTrabajo) -> None:
        self._uow = uow

    async def _ejecutar(
        self, entrada: EntradaCrearElemento, contexto: ContextoEjecucion
    ) -> ElementoCatalogo:
        elemento = ElementoCatalogo(
            tipo=entrada.tipo,
            codigo=entrada.codigo,
            nombre=entrada.nombre,
            descripcion=entrada.descripcion,
            activo=entrada.activo,
            orden=entrada.orden,
            codigo_erp=entrada.codigo_erp,
            atributos=dict(entrada.atributos),
        )

        async with self._uow:
            if await self._uow.catalogos.existe_codigo(entrada.tipo, elemento.codigo):
                raise YaExiste(entrada.tipo.singular, "codigo", elemento.codigo)
            creado = await self._uow.catalogos.agregar(elemento)
            await self._uow.commit()
            return creado


class ActualizarElementoCatalogo(CasoDeUso[EntradaActualizarElemento, ElementoCatalogo]):
    """Modifica un elemento de catalogo.

    El codigo no se puede cambiar: es la identidad del elemento y hay filas del
    distributivo apuntando a el. Para corregir un codigo mal escrito se crea el
    nuevo y se desactiva el anterior.
    """

    nombre = "catalogos.actualizar"
    descripcion = "Modifica un elemento de catalogo"
    permiso_requerido = Permiso.CATALOGOS_ESCRIBIR

    def __init__(self, uow: UnidadDeTrabajo) -> None:
        self._uow = uow

    async def _ejecutar(
        self, entrada: EntradaActualizarElemento, contexto: ContextoEjecucion
    ) -> ElementoCatalogo:
        async with self._uow:
            elemento = await self._uow.catalogos.obtener(entrada.tipo, entrada.elemento_id)
            if elemento is None:
                raise NoEncontrado(entrada.tipo.singular, entrada.elemento_id)

            elemento.actualizar(
                nombre=entrada.nombre,
                descripcion=entrada.descripcion,
                activo=entrada.activo,
                orden=entrada.orden,
                codigo_erp=entrada.codigo_erp,
                atributos=entrada.atributos,
            )
            actualizado = await self._uow.catalogos.actualizar(elemento)
            await self._uow.commit()
            return actualizado


class EliminarElementoCatalogo(CasoDeUso[EntradaObtenerElemento, None]):
    """Elimina un elemento de catalogo que nadie este usando.

    Si hay filas del distributivo apuntando a el, se rechaza: borrarlo dejaria
    el historico sin ese dato, y el historico es justamente lo que da valor al
    consolidado. La via correcta es desactivarlo, que lo retira de los
    selectores sin tocar lo ya registrado.
    """

    nombre = "catalogos.eliminar"
    descripcion = "Elimina un elemento de catalogo sin referencias"
    permiso_requerido = Permiso.CATALOGOS_ESCRIBIR

    def __init__(self, uow: UnidadDeTrabajo) -> None:
        self._uow = uow

    async def _ejecutar(self, entrada: EntradaObtenerElemento, contexto: ContextoEjecucion) -> None:
        async with self._uow:
            elemento = await self._uow.catalogos.obtener(entrada.tipo, entrada.elemento_id)
            if elemento is None:
                raise NoEncontrado(entrada.tipo.singular, entrada.elemento_id)

            referencias = await self._uow.catalogos.contar_referencias(
                entrada.tipo, entrada.elemento_id
            )
            if referencias:
                raise ReglaDeNegocioViolada(
                    f"'{elemento.nombre}' esta siendo usado por {referencias} "
                    "registro(s) y no puede eliminarse. Desactivelo para retirarlo "
                    "de los selectores sin perder el historico."
                )

            await self._uow.catalogos.eliminar(entrada.tipo, entrada.elemento_id)
            await self._uow.commit()


class ListarTiposCatalogo(CasoDeUso[None, list[dict[str, str]]]):
    """Los doce catalogos disponibles, con su etiqueta.

    El frontend lo usa para construir el menu de catalogos sin llevar una copia
    de la lista que se desincronizaria al agregar uno nuevo.
    """

    nombre = "catalogos.tipos"
    descripcion = "Lista los catalogos disponibles del distributivo"
    permiso_requerido = Permiso.CATALOGOS_LEER

    async def _ejecutar(self, entrada: None, contexto: ContextoEjecucion) -> list[dict[str, str]]:
        return [
            {"tipo": t.value, "etiqueta": t.etiqueta, "singular": t.singular} for t in TipoCatalogo
        ]
