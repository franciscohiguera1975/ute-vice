"""Endpoints de tickets de soporte tecnico."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.api.dependencias import ContextoDep, UowDep, requiere
from app.api.esquemas.comunes import ParametrosPaginacion, RespuestaPaginada
from app.api.esquemas.tickets import (
    AsignarTicketEntrada,
    ResponsableSalida,
    SeguimientoCrear,
    SeguimientoSalida,
    TicketCrear,
    TicketDetalleSalida,
    TicketSalida,
)
from app.application.casos_uso.tickets import (
    AgregarSeguimiento,
    AsignarTicket,
    CrearTicket,
    EntradaAgregarSeguimiento,
    EntradaAsignarTicket,
    EntradaCrearTicket,
    EntradaListarTickets,
    ListarResponsables,
    ListarTickets,
    ObtenerTicket,
)
from app.domain.enums import EstadoTicket, Permiso
from app.domain.ports.tickets import FiltroTickets

router = APIRouter(prefix="/tickets", tags=["Tickets"])


@router.get(
    "",
    response_model=RespuestaPaginada[TicketSalida],
    summary="Listar tickets",
    dependencies=[requiere(Permiso.TICKETS_LEER)],
)
async def listar(
    uow: UowDep,
    contexto: ContextoDep,
    paginacion: Annotated[ParametrosPaginacion, Depends()],
    texto: Annotated[str | None, Query(description="Busqueda por titulo o descripcion")] = None,
    estado: EstadoTicket | None = None,
    solicitante_id: UUID | None = None,
    asignado_a: UUID | None = None,
) -> RespuestaPaginada[TicketSalida]:
    caso = ListarTickets(uow)
    pagina = await caso(
        EntradaListarTickets(
            filtro=FiltroTickets(
                texto=texto,
                estado=estado,
                solicitante_id=solicitante_id,
                asignado_a=asignado_a,
            ),
            paginacion=paginacion.a_dominio(),
        ),
        contexto,
    )
    return RespuestaPaginada.desde(pagina, [TicketSalida.desde(v) for v in pagina.items])


@router.post(
    "",
    response_model=TicketSalida,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar un ticket",
    dependencies=[requiere(Permiso.TICKETS_ESCRIBIR)],
    responses={404: {"description": "El solicitante no existe"}},
)
async def crear(datos: TicketCrear, uow: UowDep, contexto: ContextoDep) -> TicketSalida:
    caso = CrearTicket(uow)
    ticket = await caso(
        EntradaCrearTicket(
            titulo=datos.titulo,
            descripcion=datos.descripcion,
            solicitante_id=datos.solicitante_id,
        ),
        contexto,
    )
    detalle = await ObtenerTicket(uow)(ticket.id, contexto)
    return TicketSalida.desde(detalle.vista)


@router.get(
    "/responsables",
    response_model=list[ResponsableSalida],
    summary="Usuarios de soporte tecnico disponibles para asignar",
    dependencies=[requiere(Permiso.TICKETS_LEER)],
)
async def responsables(uow: UowDep, contexto: ContextoDep) -> list[ResponsableSalida]:
    caso = ListarResponsables(uow)
    return [ResponsableSalida.desde(r) for r in await caso(None, contexto)]


@router.get(
    "/{ticket_id}",
    response_model=TicketDetalleSalida,
    summary="Detalle de un ticket con su tabla de seguimiento",
    dependencies=[requiere(Permiso.TICKETS_LEER)],
)
async def obtener(ticket_id: UUID, uow: UowDep, contexto: ContextoDep) -> TicketDetalleSalida:
    caso = ObtenerTicket(uow)
    return TicketDetalleSalida.desde(await caso(ticket_id, contexto))


@router.post(
    "/{ticket_id}/seguimientos",
    response_model=SeguimientoSalida,
    status_code=status.HTTP_201_CREATED,
    summary="Agrega un paso de seguimiento y, si aplica, cambia el estado",
    dependencies=[requiere(Permiso.TICKETS_ESCRIBIR)],
)
async def agregar_seguimiento(
    ticket_id: UUID, datos: SeguimientoCrear, uow: UowDep, contexto: ContextoDep
) -> SeguimientoSalida:
    caso = AgregarSeguimiento(uow)
    seguimiento = await caso(
        EntradaAgregarSeguimiento(
            ticket_id=ticket_id,
            comentario=datos.comentario,
            estado_nuevo=datos.estado_nuevo,
        ),
        contexto,
    )
    return SeguimientoSalida.desde(seguimiento)


@router.patch(
    "/{ticket_id}/asignar",
    response_model=TicketSalida,
    summary="Asigna o reasigna el responsable de un ticket",
    dependencies=[requiere(Permiso.TICKETS_ESCRIBIR)],
)
async def asignar(
    ticket_id: UUID, datos: AsignarTicketEntrada, uow: UowDep, contexto: ContextoDep
) -> TicketSalida:
    caso = AsignarTicket(uow)
    await caso(EntradaAsignarTicket(ticket_id=ticket_id, usuario_id=datos.usuario_id), contexto)
    detalle = await ObtenerTicket(uow)(ticket_id, contexto)
    return TicketSalida.desde(detalle.vista)
