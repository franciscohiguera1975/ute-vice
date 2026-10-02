"""Casos de uso del modulo de tickets de soporte tecnico."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from uuid import UUID

from app.application.base import CasoDeUso, ContextoEjecucion
from app.domain.entities.catalogo import TipoCatalogo
from app.domain.entities.ticket import SeguimientoTicket, Ticket
from app.domain.enums import EstadoTicket, Permiso, PrioridadTicket
from app.domain.errors import ErrorValidacion, NoEncontrado
from app.domain.ports.repositorios import Pagina, Paginacion
from app.domain.ports.tickets import EstadisticasTickets, FiltroTickets, VistaTicket
from app.domain.ports.uow import UnidadDeTrabajo
from app.domain.value_objects import ahora_utc

# ---------------------------------------------------------------------------
# Entradas y salidas
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class EntradaCrearTicket:
    titulo: str
    descripcion: str
    solicitante_id: UUID
    fecha_solicitud: date | None = None
    """`None` toma la fecha de hoy: el registro tardio es la excepcion, no la regla."""
    prioridad: PrioridadTicket | None = None
    categoria_id: UUID | None = None
    fecha_limite: date | None = None


@dataclass(frozen=True, slots=True)
class EntradaListarTickets:
    filtro: FiltroTickets = field(default_factory=FiltroTickets)
    paginacion: Paginacion = field(default_factory=Paginacion)


@dataclass(frozen=True, slots=True)
class TicketConSeguimiento:
    """Vista de detalle: el ticket y su tabla de seguimiento completa."""

    vista: VistaTicket
    seguimientos: list[SeguimientoTicket] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class EntradaAgregarSeguimiento:
    ticket_id: UUID
    comentario: str
    estado_nuevo: EstadoTicket | None = None


@dataclass(frozen=True, slots=True)
class EntradaAsignarTicket:
    ticket_id: UUID
    usuario_id: UUID | None


@dataclass(frozen=True, slots=True)
class EntradaCambiarFechaSolicitud:
    ticket_id: UUID
    fecha_solicitud: date


@dataclass(frozen=True, slots=True)
class EntradaActualizarDetallesTicket:
    ticket_id: UUID
    prioridad: PrioridadTicket | None = None
    categoria_id: UUID | None = None
    fecha_limite: date | None = None


@dataclass(frozen=True, slots=True)
class EntradaEstadisticasTickets:
    dias: int = 30


@dataclass(frozen=True, slots=True)
class Responsable:
    id: UUID
    nombre_completo: str


# ---------------------------------------------------------------------------
# Casos de uso
# ---------------------------------------------------------------------------


class CrearTicket(CasoDeUso[EntradaCrearTicket, Ticket]):
    """Registra una solicitud de soporte a nombre de un solicitante existente."""

    nombre = "tickets.crear"
    descripcion = "Registra un ticket de soporte tecnico"
    permiso_requerido = Permiso.TICKETS_ESCRIBIR

    def __init__(self, uow: UnidadDeTrabajo) -> None:
        self._uow = uow

    async def _ejecutar(self, entrada: EntradaCrearTicket, contexto: ContextoEjecucion) -> Ticket:
        async with self._uow:
            solicitante = await self._uow.personas.obtener(entrada.solicitante_id)
            if solicitante is None:
                raise NoEncontrado("Persona", entrada.solicitante_id)

            ticket = Ticket(
                titulo=entrada.titulo,
                descripcion=entrada.descripcion,
                solicitante_id=entrada.solicitante_id,
                fecha_solicitud=entrada.fecha_solicitud or ahora_utc().date(),
                prioridad=entrada.prioridad,
                categoria_id=entrada.categoria_id,
                fecha_limite=entrada.fecha_limite,
                creado_por=contexto.actor_id,
            )
            creado = await self._uow.tickets.agregar(ticket)
            await self._uow.commit()
            return creado


class ListarTickets(CasoDeUso[EntradaListarTickets, Pagina[VistaTicket]]):
    nombre = "tickets.listar"
    descripcion = "Lista tickets con filtros de busqueda y paginacion"
    permiso_requerido = Permiso.TICKETS_LEER

    def __init__(self, uow: UnidadDeTrabajo) -> None:
        self._uow = uow

    async def _ejecutar(
        self, entrada: EntradaListarTickets, contexto: ContextoEjecucion
    ) -> Pagina[VistaTicket]:
        async with self._uow:
            return await self._uow.tickets.listar(entrada.filtro, entrada.paginacion)


class ObtenerTicket(CasoDeUso[UUID, TicketConSeguimiento]):
    """Detalle de un ticket con toda su tabla de seguimiento."""

    nombre = "tickets.obtener"
    descripcion = "Obtiene un ticket con su tabla de seguimiento"
    permiso_requerido = Permiso.TICKETS_LEER

    def __init__(self, uow: UnidadDeTrabajo) -> None:
        self._uow = uow

    async def _ejecutar(self, entrada: UUID, contexto: ContextoEjecucion) -> TicketConSeguimiento:
        async with self._uow:
            vista = await self._uow.tickets.obtener(entrada)
            if vista is None:
                raise NoEncontrado("Ticket", entrada)
            seguimientos = await self._uow.tickets.listar_seguimientos(entrada)
            return TicketConSeguimiento(vista=vista, seguimientos=seguimientos)


class AgregarSeguimiento(CasoDeUso[EntradaAgregarSeguimiento, SeguimientoTicket]):
    """Deja un comentario de avance y, opcionalmente, cambia el estado.

    Ambos movimientos quedan en el mismo paso de la tabla de seguimiento: no
    tiene sentido separar "comenté que ya lo revisé" de "lo marqué como
    abierto" cuando en la practica son la misma accion del operador.
    """

    nombre = "tickets.agregar_seguimiento"
    descripcion = "Agrega un paso de seguimiento y, si aplica, cambia el estado del ticket"
    permiso_requerido = Permiso.TICKETS_ESCRIBIR

    def __init__(self, uow: UnidadDeTrabajo) -> None:
        self._uow = uow

    async def _ejecutar(
        self, entrada: EntradaAgregarSeguimiento, contexto: ContextoEjecucion
    ) -> SeguimientoTicket:
        if not entrada.comentario.strip():
            raise ErrorValidacion("El comentario no puede estar vacio", campo="comentario")

        async with self._uow:
            vista = await self._uow.tickets.obtener(entrada.ticket_id)
            if vista is None:
                raise NoEncontrado("Ticket", entrada.ticket_id)
            ticket = vista.ticket

            estado_anterior = ticket.estado
            estado_nuevo = entrada.estado_nuevo if entrada.estado_nuevo != estado_anterior else None

            seguimiento = SeguimientoTicket(
                ticket_id=ticket.id,
                autor_id=contexto.actor_id,
                comentario=entrada.comentario.strip(),
                estado_anterior=estado_anterior if estado_nuevo else None,
                estado_nuevo=estado_nuevo,
            )
            creado = await self._uow.tickets.agregar_seguimiento(seguimiento)

            if estado_nuevo:
                ticket.cambiar_estado(estado_nuevo)
                await self._uow.tickets.actualizar(ticket)

            await self._uow.commit()
            return creado


class AsignarTicket(CasoDeUso[EntradaAsignarTicket, Ticket]):
    """Asigna o reasigna el responsable de un ticket.

    Deja rastro en la tabla de seguimiento con un comentario generado, para que
    quien revise el historico vea cuando y a quien se asigno el caso sin tener
    que cruzarlo con un log aparte.
    """

    nombre = "tickets.asignar"
    descripcion = "Asigna o reasigna el responsable de un ticket"
    permiso_requerido = Permiso.TICKETS_ESCRIBIR

    def __init__(self, uow: UnidadDeTrabajo) -> None:
        self._uow = uow

    async def _ejecutar(self, entrada: EntradaAsignarTicket, contexto: ContextoEjecucion) -> Ticket:
        async with self._uow:
            vista = await self._uow.tickets.obtener(entrada.ticket_id)
            if vista is None:
                raise NoEncontrado("Ticket", entrada.ticket_id)
            ticket = vista.ticket

            nombre_responsable = "sin responsable"
            if entrada.usuario_id is not None:
                usuario = await self._uow.usuarios.obtener(entrada.usuario_id)
                if usuario is None:
                    raise NoEncontrado("Usuario", entrada.usuario_id)
                nombre_responsable = usuario.nombre_completo

            ticket.asignar(entrada.usuario_id)
            actualizado = await self._uow.tickets.actualizar(ticket)

            comentario = (
                f"Asignado a {nombre_responsable}"
                if entrada.usuario_id is not None
                else "Sin responsable asignado"
            )
            await self._uow.tickets.agregar_seguimiento(
                SeguimientoTicket(
                    ticket_id=ticket.id,
                    autor_id=contexto.actor_id,
                    comentario=comentario,
                )
            )

            await self._uow.commit()
            return actualizado


class CambiarFechaSolicitud(CasoDeUso[EntradaCambiarFechaSolicitud, Ticket]):
    """Corrige la fecha en que se pidio el soporte.

    Existe porque el registro del ticket suele quedar unos dias detras del
    pedido real; se deja un seguimiento automatico con el valor anterior para
    que el ajuste no borre el rastro de lo que decia antes.
    """

    nombre = "tickets.cambiar_fecha_solicitud"
    descripcion = "Corrige la fecha de solicitud de un ticket"
    permiso_requerido = Permiso.TICKETS_ESCRIBIR

    def __init__(self, uow: UnidadDeTrabajo) -> None:
        self._uow = uow

    async def _ejecutar(
        self, entrada: EntradaCambiarFechaSolicitud, contexto: ContextoEjecucion
    ) -> Ticket:
        async with self._uow:
            vista = await self._uow.tickets.obtener(entrada.ticket_id)
            if vista is None:
                raise NoEncontrado("Ticket", entrada.ticket_id)
            ticket = vista.ticket

            fecha_anterior = ticket.fecha_solicitud
            if fecha_anterior == entrada.fecha_solicitud:
                return ticket

            ticket.cambiar_fecha_solicitud(entrada.fecha_solicitud)
            actualizado = await self._uow.tickets.actualizar(ticket)

            await self._uow.tickets.agregar_seguimiento(
                SeguimientoTicket(
                    ticket_id=ticket.id,
                    autor_id=contexto.actor_id,
                    comentario=(
                        f"Fecha de solicitud corregida: {fecha_anterior.isoformat()} → "
                        f"{entrada.fecha_solicitud.isoformat()}"
                    ),
                )
            )

            await self._uow.commit()
            return actualizado


class ActualizarDetallesTicket(CasoDeUso[EntradaActualizarDetallesTicket, Ticket]):
    """Triage del caso: prioridad, categoria y fecha limite, los tres juntos.

    Se editan en una sola operacion porque en la practica se deciden en el
    mismo momento, al revisar el caso; separar en tres llamadas solo
    multiplicaria los pasos de seguimiento sin aportar nada.
    """

    nombre = "tickets.actualizar_detalles"
    descripcion = "Actualiza prioridad, categoria y fecha limite de un ticket"
    permiso_requerido = Permiso.TICKETS_ESCRIBIR

    def __init__(self, uow: UnidadDeTrabajo) -> None:
        self._uow = uow

    async def _ejecutar(
        self, entrada: EntradaActualizarDetallesTicket, contexto: ContextoEjecucion
    ) -> Ticket:
        async with self._uow:
            vista = await self._uow.tickets.obtener(entrada.ticket_id)
            if vista is None:
                raise NoEncontrado("Ticket", entrada.ticket_id)
            ticket = vista.ticket

            sin_cambios = (
                ticket.prioridad == entrada.prioridad
                and ticket.categoria_id == entrada.categoria_id
                and ticket.fecha_limite == entrada.fecha_limite
            )
            if sin_cambios:
                return ticket

            categoria_nombre = "sin categoria"
            if entrada.categoria_id is not None:
                categoria = await self._uow.catalogos.obtener(
                    TipoCatalogo.CATEGORIA_TICKET, entrada.categoria_id
                )
                categoria_nombre = categoria.nombre if categoria else "sin categoria"

            ticket.actualizar_detalles(
                prioridad=entrada.prioridad,
                categoria_id=entrada.categoria_id,
                fecha_limite=entrada.fecha_limite,
            )
            actualizado = await self._uow.tickets.actualizar(ticket)

            prioridad_texto = entrada.prioridad.etiqueta if entrada.prioridad else "sin prioridad"
            fecha_texto = (
                entrada.fecha_limite.isoformat() if entrada.fecha_limite else "sin fecha limite"
            )
            await self._uow.tickets.agregar_seguimiento(
                SeguimientoTicket(
                    ticket_id=ticket.id,
                    autor_id=contexto.actor_id,
                    comentario=(
                        f"Detalles actualizados: prioridad {prioridad_texto}, "
                        f"categoria {categoria_nombre}, {fecha_texto}"
                    ),
                )
            )

            await self._uow.commit()
            return actualizado


#: Roles que pueden quedar como responsables de un ticket. Se incluye ADMIN
#: ademas de SOPORTE_TECNICO porque un administrador a veces resuelve el caso
#: el mismo, en instalaciones donde aun no hay un equipo de soporte dedicado.
_ROLES_RESPONSABLES = ("SOPORTE_TECNICO", "ADMIN")


class ListarResponsables(CasoDeUso[None, list[Responsable]]):
    """Usuarios activos que pueden quedar como responsables de un ticket, para
    poblar el selector de asignacion sin exigir el permiso de administracion."""

    nombre = "tickets.listar_responsables"
    descripcion = "Lista los usuarios disponibles para asignar tickets"
    permiso_requerido = Permiso.TICKETS_LEER

    def __init__(self, uow: UnidadDeTrabajo) -> None:
        self._uow = uow

    async def _ejecutar(self, entrada: None, contexto: ContextoEjecucion) -> list[Responsable]:
        async with self._uow:
            vistos: dict[UUID, Responsable] = {}
            for rol in _ROLES_RESPONSABLES:
                pagina = await self._uow.usuarios.listar(
                    Paginacion(tamano=200), activo=True, rol=rol
                )
                for u in pagina.items:
                    vistos[u.id] = Responsable(id=u.id, nombre_completo=u.nombre_completo)
            return sorted(vistos.values(), key=lambda r: r.nombre_completo)


class ObtenerEstadisticasTickets(CasoDeUso[EntradaEstadisticasTickets, EstadisticasTickets]):
    """Dashboard de soporte: metricas propias, o globales con el permiso adecuado.

    El alcance nunca se decide por el rol del actor, solo por si tiene
    `TICKETS_ADMINISTRAR`: con el permiso ve todos los tickets, sin el, solo
    los que tiene asignados. Es lo mismo que pide "el admin ve la situacion de
    todos, soporte ve sus propios soportes realizados".
    """

    nombre = "tickets.estadisticas"
    descripcion = "Metricas de tickets para el dashboard de soporte"
    permiso_requerido = Permiso.TICKETS_LEER

    def __init__(self, uow: UnidadDeTrabajo) -> None:
        self._uow = uow

    async def _ejecutar(
        self, entrada: EntradaEstadisticasTickets, contexto: ContextoEjecucion
    ) -> EstadisticasTickets:
        alcance_propio = None
        if contexto.actor is not None and not contexto.actor.puede(Permiso.TICKETS_ADMINISTRAR):
            alcance_propio = contexto.actor_id

        hasta = ahora_utc().date()
        desde = hasta - timedelta(days=max(1, entrada.dias))
        async with self._uow:
            return await self._uow.tickets.estadisticas(
                asignado_a=alcance_propio, desde=desde, hasta=hasta
            )
