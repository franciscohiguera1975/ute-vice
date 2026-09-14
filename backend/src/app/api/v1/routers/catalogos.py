"""Endpoints de los catalogos del distributivo.

Un solo router sirve a los doce catalogos: el tipo viaja en la ruta
(`/catalogos/carreras`, `/catalogos/sedes`, …). Duplicar doce routers
identicos solo multiplicaria las oportunidades de que uno quede desalineado.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Query, status

from app.api.dependencias import ContextoDep, UowDep, requiere
from app.api.esquemas.comunes import (
    ParametrosPaginacion,
    RespuestaMensaje,
    RespuestaPaginada,
)
from app.api.esquemas.distributivo import (
    ElementoCatalogoActualizar,
    ElementoCatalogoCrear,
    ElementoCatalogoSalida,
    OpcionSelector,
    TipoCatalogoSalida,
)
from app.application.casos_uso.catalogos import (
    ActualizarElementoCatalogo,
    CrearElementoCatalogo,
    EliminarElementoCatalogo,
    EntradaActualizarElemento,
    EntradaCatalogoCompleto,
    EntradaCrearElemento,
    EntradaListarCatalogo,
    EntradaObtenerElemento,
    ListarCatalogo,
    ListarTiposCatalogo,
    ObtenerCatalogoCompleto,
    ObtenerElementoCatalogo,
)
from app.domain.entities.catalogo import TipoCatalogo
from app.domain.enums import Permiso
from app.domain.ports.distributivo import FiltroCatalogo

router = APIRouter(prefix="/catalogos", tags=["Catalogos del distributivo"])

TipoDep = Annotated[
    TipoCatalogo,
    Path(description="Catalogo: paos, facultades, carreras, sedes, titularidades, …"),
]


@router.get(
    "",
    response_model=list[TipoCatalogoSalida],
    summary="Catalogos disponibles",
    dependencies=[requiere(Permiso.CATALOGOS_LEER)],
)
async def tipos(contexto: ContextoDep) -> list[TipoCatalogoSalida]:
    """Los doce catalogos con su etiqueta.

    El frontend construye el menu con esto en lugar de llevar su propia copia de
    la lista, que se desincronizaria al agregar un catalogo nuevo.
    """
    caso = ListarTiposCatalogo()
    return [TipoCatalogoSalida(**t) for t in await caso(None, contexto)]


@router.get(
    "/{tipo}/opciones",
    response_model=list[OpcionSelector],
    summary="Catalogo completo para poblar un selector",
    dependencies=[requiere(Permiso.CATALOGOS_LEER)],
)
async def opciones(
    tipo: TipoDep,
    uow: UowDep,
    contexto: ContextoDep,
    incluir_inactivos: Annotated[
        bool, Query(description="Incluye los elementos desactivados")
    ] = False,
) -> list[OpcionSelector]:
    """Devuelve el catalogo entero, sin paginar.

    Un desplegable necesita todos los elementos de una vez; paginarlo obligaria
    al frontend a encadenar peticiones para pintar una lista.
    """
    caso = ObtenerCatalogoCompleto(uow)
    elementos = await caso(
        EntradaCatalogoCompleto(tipo=tipo, solo_activos=not incluir_inactivos), contexto
    )
    return [OpcionSelector.desde(e) for e in elementos]


@router.get(
    "/{tipo}",
    response_model=RespuestaPaginada[ElementoCatalogoSalida],
    summary="Listar un catalogo",
    dependencies=[requiere(Permiso.CATALOGOS_LEER)],
)
async def listar(
    tipo: TipoDep,
    uow: UowDep,
    contexto: ContextoDep,
    paginacion: Annotated[ParametrosPaginacion, Depends()],
    texto: Annotated[str | None, Query(description="Busqueda por codigo o nombre")] = None,
    activo: bool | None = None,
) -> RespuestaPaginada[ElementoCatalogoSalida]:
    caso = ListarCatalogo(uow)
    pagina = await caso(
        EntradaListarCatalogo(
            tipo=tipo,
            filtro=FiltroCatalogo(texto=texto, activo=activo),
            paginacion=paginacion.a_dominio(),
        ),
        contexto,
    )
    return RespuestaPaginada.desde(pagina, [ElementoCatalogoSalida.desde(e) for e in pagina.items])


@router.post(
    "/{tipo}",
    response_model=ElementoCatalogoSalida,
    status_code=status.HTTP_201_CREATED,
    summary="Agregar un elemento al catalogo",
    dependencies=[requiere(Permiso.CATALOGOS_ESCRIBIR)],
    responses={409: {"description": "Ya existe un elemento con ese codigo"}},
)
async def crear(
    tipo: TipoDep, datos: ElementoCatalogoCrear, uow: UowDep, contexto: ContextoDep
) -> ElementoCatalogoSalida:
    caso = CrearElementoCatalogo(uow)
    elemento = await caso(
        EntradaCrearElemento(
            tipo=tipo,
            codigo=datos.codigo,
            nombre=datos.nombre,
            descripcion=datos.descripcion,
            activo=datos.activo,
            orden=datos.orden,
            codigo_erp=datos.codigo_erp,
            atributos=datos.atributos,
        ),
        contexto,
    )
    return ElementoCatalogoSalida.desde(elemento)


@router.get(
    "/{tipo}/{elemento_id}",
    response_model=ElementoCatalogoSalida,
    summary="Obtener un elemento del catalogo",
    dependencies=[requiere(Permiso.CATALOGOS_LEER)],
)
async def obtener(
    tipo: TipoDep, elemento_id: UUID, uow: UowDep, contexto: ContextoDep
) -> ElementoCatalogoSalida:
    caso = ObtenerElementoCatalogo(uow)
    elemento = await caso(EntradaObtenerElemento(tipo=tipo, elemento_id=elemento_id), contexto)
    return ElementoCatalogoSalida.desde(elemento)


@router.patch(
    "/{tipo}/{elemento_id}",
    response_model=ElementoCatalogoSalida,
    summary="Modificar un elemento del catalogo",
    dependencies=[requiere(Permiso.CATALOGOS_ESCRIBIR)],
)
async def actualizar(
    tipo: TipoDep,
    elemento_id: UUID,
    datos: ElementoCatalogoActualizar,
    uow: UowDep,
    contexto: ContextoDep,
) -> ElementoCatalogoSalida:
    """El codigo no es modificable: es la identidad del elemento y hay filas del
    distributivo apuntando a el."""
    caso = ActualizarElementoCatalogo(uow)
    elemento = await caso(
        EntradaActualizarElemento(
            tipo=tipo,
            elemento_id=elemento_id,
            nombre=datos.nombre,
            descripcion=datos.descripcion,
            activo=datos.activo,
            orden=datos.orden,
            codigo_erp=datos.codigo_erp,
            atributos=datos.atributos,
        ),
        contexto,
    )
    return ElementoCatalogoSalida.desde(elemento)


@router.delete(
    "/{tipo}/{elemento_id}",
    response_model=RespuestaMensaje,
    summary="Eliminar un elemento sin referencias",
    dependencies=[requiere(Permiso.CATALOGOS_ESCRIBIR)],
    responses={
        422: {"description": "El elemento esta referenciado: desactivelo en lugar de borrarlo"}
    },
)
async def eliminar(
    tipo: TipoDep, elemento_id: UUID, uow: UowDep, contexto: ContextoDep
) -> RespuestaMensaje:
    caso = EliminarElementoCatalogo(uow)
    await caso(EntradaObtenerElemento(tipo=tipo, elemento_id=elemento_id), contexto)
    return RespuestaMensaje(mensaje="Elemento eliminado")
