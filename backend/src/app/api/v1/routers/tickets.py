"""Endpoints de tickets de soporte tecnico."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from fastapi.responses import FileResponse

from app.api.dependencias import ContextoDep, SettingsDep, UowDep, requiere
from app.api.esquemas.comunes import ParametrosPaginacion, RespuestaPaginada
from app.api.esquemas.tickets import (
    AsignarTicketEntrada,
    DetallesTicketEntrada,
    EstadisticasTicketsSalida,
    FechaSolicitudEntrada,
    ImagenSubidaSalida,
    ResponsableSalida,
    SeguimientoCrear,
    SeguimientoSalida,
    TicketCrear,
    TicketDetalleSalida,
    TicketSalida,
)
from app.application.casos_uso.tickets import (
    ActualizarDetallesTicket,
    AgregarSeguimiento,
    AsignarTicket,
    CambiarFechaSolicitud,
    CrearTicket,
    EntradaActualizarDetallesTicket,
    EntradaAgregarSeguimiento,
    EntradaAsignarTicket,
    EntradaCambiarFechaSolicitud,
    EntradaCrearTicket,
    EntradaEstadisticasTickets,
    EntradaListarTickets,
    ListarResponsables,
    ListarTickets,
    ObtenerEstadisticasTickets,
    ObtenerTicket,
)
from app.domain.enums import EstadoTicket, Permiso, PrioridadTicket
from app.domain.errors import NoEncontrado
from app.domain.ports.tickets import FiltroTickets
from app.infrastructure.almacenamiento.imagenes_editor import guardar_imagen, resolver_imagen

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
    prioridad: PrioridadTicket | None = None,
    categoria_id: UUID | None = None,
) -> RespuestaPaginada[TicketSalida]:
    caso = ListarTickets(uow)
    pagina = await caso(
        EntradaListarTickets(
            filtro=FiltroTickets(
                texto=texto,
                estado=estado,
                solicitante_id=solicitante_id,
                asignado_a=asignado_a,
                prioridad=prioridad,
                categoria_id=categoria_id,
            ),
            paginacion=paginacion.a_dominio(),
        ),
        contexto,
    )
    return RespuestaPaginada.desde(pagina, [TicketSalida.desde(v) for v in pagina.items])


@router.get(
    "/estadisticas",
    response_model=EstadisticasTicketsSalida,
    summary="Metricas de tickets para el dashboard de soporte",
    dependencies=[requiere(Permiso.TICKETS_LEER)],
)
async def estadisticas(
    uow: UowDep,
    contexto: ContextoDep,
    dias: Annotated[int, Query(ge=1, le=365, description="Ventana de la tendencia diaria")] = 30,
) -> EstadisticasTicketsSalida:
    caso = ObtenerEstadisticasTickets(uow)
    resultado = await caso(EntradaEstadisticasTickets(dias=dias), contexto)
    return EstadisticasTicketsSalida.desde(resultado)


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
            fecha_solicitud=datos.fecha_solicitud,
            prioridad=datos.prioridad,
            categoria_id=datos.categoria_id,
            fecha_limite=datos.fecha_limite,
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


@router.post(
    "/imagenes",
    response_model=ImagenSubidaSalida,
    status_code=status.HTTP_201_CREATED,
    summary="Sube una imagen insertada desde el editor enriquecido",
    dependencies=[requiere(Permiso.TICKETS_ESCRIBIR)],
)
async def subir_imagen(
    settings: SettingsDep,
    archivo: Annotated[UploadFile, File(description="Imagen PNG, JPEG, WEBP o GIF")],
) -> ImagenSubidaSalida:
    nombre = await guardar_imagen(archivo, settings.tickets)
    # Relativa a la raiz de la API (como el resto de rutas de este router): el
    # frontend le antepone su URL base configurada, igual que a cualquier otra
    # peticion — no conviene que el backend asuma su propio host o prefijo.
    return ImagenSubidaSalida(url=f"/tickets/imagenes/{nombre}")


@router.get(
    "/imagenes/{nombre}",
    summary="Sirve una imagen insertada desde el editor enriquecido",
)
async def obtener_imagen(nombre: str, settings: SettingsDep) -> FileResponse:
    """Sin `requiere(...)`, a proposito: un `<img src>` de HTML no puede llevar
    el encabezado `Authorization`, asi que esta ruta no puede exigir el token
    Bearer que protege al resto de la API. Queda resguardada solo por el
    nombre aleatorio (UUID) que genera `guardar_imagen` — nunca listable ni
    adivinable —, igual que un enlace de archivo "no listado" de cualquier
    proveedor de almacenamiento. La subida si exige `TICKETS_ESCRIBIR`.
    """
    ruta = resolver_imagen(nombre, settings.tickets)
    if ruta is None:
        raise NoEncontrado("Imagen", nombre)
    return FileResponse(ruta)


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


@router.patch(
    "/{ticket_id}/fecha-solicitud",
    response_model=TicketSalida,
    summary="Corrige la fecha en que se pidio el soporte",
    dependencies=[requiere(Permiso.TICKETS_ESCRIBIR)],
)
async def cambiar_fecha_solicitud(
    ticket_id: UUID, datos: FechaSolicitudEntrada, uow: UowDep, contexto: ContextoDep
) -> TicketSalida:
    caso = CambiarFechaSolicitud(uow)
    await caso(
        EntradaCambiarFechaSolicitud(ticket_id=ticket_id, fecha_solicitud=datos.fecha_solicitud),
        contexto,
    )
    detalle = await ObtenerTicket(uow)(ticket_id, contexto)
    return TicketSalida.desde(detalle.vista)


@router.patch(
    "/{ticket_id}/detalles",
    response_model=TicketSalida,
    summary="Actualiza prioridad, categoria y fecha limite de un ticket",
    dependencies=[requiere(Permiso.TICKETS_ESCRIBIR)],
)
async def actualizar_detalles(
    ticket_id: UUID, datos: DetallesTicketEntrada, uow: UowDep, contexto: ContextoDep
) -> TicketSalida:
    caso = ActualizarDetallesTicket(uow)
    await caso(
        EntradaActualizarDetallesTicket(
            ticket_id=ticket_id,
            prioridad=datos.prioridad,
            categoria_id=datos.categoria_id,
            fecha_limite=datos.fecha_limite,
        ),
        contexto,
    )
    detalle = await ObtenerTicket(uow)(ticket_id, contexto)
    return TicketSalida.desde(detalle.vista)
