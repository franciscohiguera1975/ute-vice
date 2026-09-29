"""Casos de uso del modulo de tickets de soporte tecnico."""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from app.application.base import CasoDeUso, ContextoEjecucion
from app.domain.entities.ticket import SeguimientoTicket, Ticket
from app.domain.enums import EstadoTicket, Permiso
from app.domain.errors import ErrorValidacion, NoEncontrado
from app.domain.ports.repositorios import Pagina, Paginacion
from app.domain.ports.tickets import FiltroTickets, VistaTicket
from app.domain.ports.uow import UnidadDeTrabajo

# ---------------------------------------------------------------------------
# Entradas y salidas
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class EntradaCrearTicket:
    titulo: str
    descripcion: str
    solicitante_id: UUID


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


class ListarResponsables(CasoDeUso[None, list[Responsable]]):
    """Usuarios activos con rol de soporte tecnico, para poblar el selector de
    asignacion sin exigirle a soporte tecnico el permiso de administracion."""

    nombre = "tickets.listar_responsables"
    descripcion = "Lista los usuarios de soporte tecnico disponibles para asignar tickets"
    permiso_requerido = Permiso.TICKETS_LEER

    def __init__(self, uow: UnidadDeTrabajo) -> None:
        self._uow = uow

    async def _ejecutar(self, entrada: None, contexto: ContextoEjecucion) -> list[Responsable]:
        async with self._uow:
            pagina = await self._uow.usuarios.listar(
                Paginacion(tamano=200),
                activo=True,
                rol="SOPORTE_TECNICO",
            )
            return [Responsable(id=u.id, nombre_completo=u.nombre_completo) for u in pagina.items]
