"""Endpoints de titulos academicos."""

from __future__ import annotations

from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.api.dependencias import ContextoDep, UowDep, requiere
from app.api.esquemas.comunes import (
    ParametrosPaginacion,
    RespuestaMensaje,
    RespuestaPaginada,
)
from app.api.esquemas.nucleo import TituloActualizar, TituloCrear, TituloSalida
from app.application.casos_uso.titulos import (
    ActualizarTitulo,
    CrearTitulo,
    EliminarTitulo,
    EntradaActualizarTitulo,
    EntradaCrearTitulo,
    EntradaListarTitulos,
    ListarTitulos,
    ObtenerTitulo,
    VerificarTitulo,
)
from app.domain.enums import EstadoTitulo, NivelTitulo, Permiso
from app.domain.ports.repositorios import FiltroTitulos

router = APIRouter(prefix="/titulos", tags=["Titulos"])


@router.get(
    "",
    response_model=RespuestaPaginada[TituloSalida],
    summary="Listar titulos",
    dependencies=[requiere(Permiso.TITULOS_LEER)],
)
async def listar(
    uow: UowDep,
    contexto: ContextoDep,
    paginacion: Annotated[ParametrosPaginacion, Depends()],
    texto: Annotated[
        str | None, Query(description="Busqueda en denominacion, institucion o area")
    ] = None,
    persona_id: UUID | None = None,
    nivel: NivelTitulo | None = None,
    estado: EstadoTitulo | None = None,
    institucion: str | None = None,
    verificado: bool | None = None,
    requiere_atencion: Annotated[
        bool | None,
        Query(description="true devuelve retirados, por verificar y de nivel indeterminado"),
    ] = None,
    registro_desde: date | None = None,
    registro_hasta: date | None = None,
) -> RespuestaPaginada[TituloSalida]:
    caso = ListarTitulos(uow)
    pagina = await caso(
        EntradaListarTitulos(
            filtro=FiltroTitulos(
                texto=texto,
                persona_id=persona_id,
                nivel=nivel,
                estado=estado,
                institucion=institucion,
                verificado=verificado,
                requiere_atencion=requiere_atencion,
                registro_desde=registro_desde,
                registro_hasta=registro_hasta,
            ),
            paginacion=paginacion.a_dominio(),
        ),
        contexto,
    )
    return RespuestaPaginada.desde(pagina, [TituloSalida.desde(t) for t in pagina.items])


@router.post(
    "",
    response_model=TituloSalida,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar un titulo manualmente",
    dependencies=[requiere(Permiso.TITULOS_ESCRIBIR)],
)
async def crear(datos: TituloCrear, uow: UowDep, contexto: ContextoDep) -> TituloSalida:
    """Un titulo cargado a mano nace `POR_VERIFICAR` y con origen `MANUAL`.

    Eso lo protege del reconciliador —que solo retira lo que el mismo trajo— y
    deja explicito que su respaldo es documental.
    """
    caso = CrearTitulo(uow)
    titulo = await caso(
        EntradaCrearTitulo(
            persona_id=datos.persona_id,
            denominacion=datos.denominacion,
            institucion=datos.institucion,
            nivel=datos.nivel,
            numero_registro=datos.numero_registro,
            fecha_registro=datos.fecha_registro,
            fecha_graduacion=datos.fecha_graduacion,
            area_conocimiento=datos.area_conocimiento,
            pais=datos.pais,
            observacion_registro=datos.observacion_registro,
        ),
        contexto,
    )
    return TituloSalida.desde(titulo)


@router.get(
    "/{titulo_id}",
    response_model=TituloSalida,
    summary="Obtener un titulo",
    dependencies=[requiere(Permiso.TITULOS_LEER)],
)
async def obtener(titulo_id: UUID, uow: UowDep, contexto: ContextoDep) -> TituloSalida:
    caso = ObtenerTitulo(uow)
    return TituloSalida.desde(await caso(titulo_id, contexto))


@router.patch(
    "/{titulo_id}",
    response_model=TituloSalida,
    summary="Corregir un titulo cargado manualmente",
    dependencies=[requiere(Permiso.TITULOS_ESCRIBIR)],
    responses={
        422: {"description": "Los titulos obtenidos del registro nacional no son editables"}
    },
)
async def actualizar(
    titulo_id: UUID, datos: TituloActualizar, uow: UowDep, contexto: ContextoDep
) -> TituloSalida:
    caso = ActualizarTitulo(uow)
    titulo = await caso(
        EntradaActualizarTitulo(
            titulo_id=titulo_id,
            denominacion=datos.denominacion,
            institucion=datos.institucion,
            nivel=datos.nivel,
            numero_registro=datos.numero_registro,
            fecha_registro=datos.fecha_registro,
            fecha_graduacion=datos.fecha_graduacion,
            area_conocimiento=datos.area_conocimiento,
            observacion_registro=datos.observacion_registro,
        ),
        contexto,
    )
    return TituloSalida.desde(titulo)


@router.post(
    "/{titulo_id}/verificar",
    response_model=TituloSalida,
    summary="Marcar un titulo como verificado",
    dependencies=[requiere(Permiso.TITULOS_VERIFICAR)],
)
async def verificar(titulo_id: UUID, uow: UowDep, contexto: ContextoDep) -> TituloSalida:
    """Deja constancia de que un funcionario reviso el respaldo documental."""
    caso = VerificarTitulo(uow)
    return TituloSalida.desde(await caso(titulo_id, contexto))


@router.delete(
    "/{titulo_id}",
    response_model=RespuestaMensaje,
    summary="Eliminar un titulo cargado manualmente",
    dependencies=[requiere(Permiso.TITULOS_ELIMINAR)],
    responses={422: {"description": "Los titulos del registro nacional no se eliminan"}},
)
async def eliminar(titulo_id: UUID, uow: UowDep, contexto: ContextoDep) -> RespuestaMensaje:
    caso = EliminarTitulo(uow)
    await caso(titulo_id, contexto)
    return RespuestaMensaje(mensaje="Titulo eliminado")
