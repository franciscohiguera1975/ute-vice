import { ChangeDetectionStrategy, Component, inject, input, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';

import { CatalogosStore } from '@core/catalogos.store';
import { NotificacionesService } from '@core/notificaciones.service';
import { SesionStore } from '@core/sesion.store';
import {
  ESTADOS_TICKET,
  ETIQUETAS_ESTADO_TICKET,
  ETIQUETAS_PRIORIDAD_TICKET,
  Permiso,
  PRIORIDADES_TICKET,
  TipoCatalogo,
  TONO_ESTADO_TICKET,
  TONO_PRIORIDAD_TICKET,
  type ErrorApi,
  type EstadoTicket,
  type PrioridadTicket,
  type Responsable,
  type TicketDetalle,
} from '@domain/modelos';
import { RepositorioTickets } from '@domain/puertos';
import { CargandoComponent } from '@shared/componentes/cargando.component';
import { EditorEnriquecidoComponent } from '@shared/componentes/editor-enriquecido.component';
import { InsigniaComponent } from '@shared/componentes/insignia.component';
import { SelectorBuscableComponent } from '@shared/componentes/selector-buscable.component';
import { PermisoDirective } from '@shared/directivas/permiso.directive';
import { DesdeHacePipe, FechaLocalPipe } from '@shared/pipes/formato.pipe';

import { sinContenido } from './html-sin-contenido';

@Component({
  selector: 'ute-detalle-ticket',
  standalone: true,
  imports: [
    FormsModule,
    RouterLink,
    CargandoComponent,
    InsigniaComponent,
    SelectorBuscableComponent,
    EditorEnriquecidoComponent,
    PermisoDirective,
    DesdeHacePipe,
    FechaLocalPipe,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './detalle.component.html',
  styleUrl: './detalle.component.scss',
})
export class DetalleTicketComponent {
  private readonly repositorio = inject(RepositorioTickets);
  private readonly notificaciones = inject(NotificacionesService);
  private readonly router = inject(Router);
  protected readonly sesion = inject(SesionStore);
  protected readonly catalogos = inject(CatalogosStore);

  /** Enlazado desde la ruta gracias a `withComponentInputBinding()`. */
  readonly id = input.required<string>();

  protected readonly Permiso = Permiso;
  protected readonly TipoCatalogo = TipoCatalogo;
  protected readonly ETIQUETAS_ESTADO_TICKET = ETIQUETAS_ESTADO_TICKET;
  protected readonly TONO_ESTADO_TICKET = TONO_ESTADO_TICKET;
  protected readonly ETIQUETAS_PRIORIDAD_TICKET = ETIQUETAS_PRIORIDAD_TICKET;
  protected readonly TONO_PRIORIDAD_TICKET = TONO_PRIORIDAD_TICKET;
  protected readonly estados = ESTADOS_TICKET;
  protected readonly prioridades = PRIORIDADES_TICKET;

  protected readonly detalle = signal<TicketDetalle | null>(null);
  protected readonly cargando = signal(true);
  protected readonly responsables = signal<readonly Responsable[]>([]);
  protected readonly asignando = signal(false);
  protected readonly hoy = new Date().toISOString().slice(0, 10);
  protected readonly guardandoFecha = signal(false);

  // --- Triage: prioridad, categoria y fecha limite se guardan juntos ---
  protected readonly prioridadEdit = signal<PrioridadTicket | ''>('');
  protected readonly categoriaIdEdit = signal('');
  protected readonly fechaLimiteEdit = signal('');
  protected readonly guardandoDetalles = signal(false);

  // --- Nuevo seguimiento ---
  protected readonly nuevoComentario = signal('');
  protected readonly nuevoEstado = signal<EstadoTicket | ''>('');
  protected readonly enviandoSeguimiento = signal(false);

  constructor() {
    // `input.required` ya esta disponible cuando corre el constructor porque el
    // enrutador enlaza las entradas antes de crear el componente.
    queueMicrotask(() => this.cargar());

    this.catalogos.cargar();
    this.repositorio.responsables().subscribe({
      next: (lista) => this.responsables.set(lista),
      error: () => this.notificaciones.aviso('No fue posible cargar la lista de responsables'),
    });
  }

  protected cargar(): void {
    this.cargando.set(true);
    this.repositorio.obtener(this.id()).subscribe({
      next: (detalle) => {
        this.detalle.set(detalle);
        this.cargando.set(false);
        this.prioridadEdit.set(detalle.ticket.prioridad ?? '');
        this.categoriaIdEdit.set(detalle.ticket.categoriaId ?? '');
        this.fechaLimiteEdit.set(detalle.ticket.fechaLimite ?? '');
      },
      error: (error: ErrorApi) => {
        this.cargando.set(false);
        this.notificaciones.error('No fue posible cargar el ticket', error.mensaje);
        void this.router.navigate(['/tickets']);
      },
    });
  }

  /** `true` si el triage cambio frente a lo ya guardado: habilita el boton. */
  protected hayCambiosDetalles(): boolean {
    const ticket = this.detalle()?.ticket;
    if (!ticket) return false;
    return (
      (ticket.prioridad ?? '') !== this.prioridadEdit() ||
      (ticket.categoriaId ?? '') !== this.categoriaIdEdit() ||
      (ticket.fechaLimite ?? '') !== this.fechaLimiteEdit()
    );
  }

  protected guardarDetalles(): void {
    this.guardandoDetalles.set(true);
    this.repositorio
      .actualizarDetalles(this.id(), {
        prioridad: this.prioridadEdit() || null,
        categoriaId: this.categoriaIdEdit() || null,
        fechaLimite: this.fechaLimiteEdit() || null,
      })
      .subscribe({
        next: () => {
          this.guardandoDetalles.set(false);
          this.notificaciones.exito('Detalles actualizados');
          this.cargar();
        },
        error: (error: ErrorApi) => {
          this.guardandoDetalles.set(false);
          this.notificaciones.error('No fue posible actualizar los detalles', error.mensaje);
        },
      });
  }

  protected asignar(usuarioId: string): void {
    this.asignando.set(true);
    this.repositorio.asignar(this.id(), usuarioId || null).subscribe({
      next: () => {
        this.asignando.set(false);
        this.notificaciones.exito('Responsable actualizado');
        this.cargar();
      },
      error: (error: ErrorApi) => {
        this.asignando.set(false);
        this.notificaciones.error('No fue posible asignar el ticket', error.mensaje);
      },
    });
  }

  protected cambiarFechaSolicitud(fecha: string): void {
    const actual = this.detalle()?.ticket.fechaSolicitud;
    if (!fecha || fecha === actual) return;

    this.guardandoFecha.set(true);
    this.repositorio.cambiarFechaSolicitud(this.id(), fecha).subscribe({
      next: () => {
        this.guardandoFecha.set(false);
        this.notificaciones.exito('Fecha de solicitud actualizada');
        this.cargar();
      },
      error: (error: ErrorApi) => {
        this.guardandoFecha.set(false);
        this.notificaciones.error('No fue posible actualizar la fecha', error.mensaje);
      },
    });
  }

  protected agregarSeguimiento(): void {
    if (sinContenido(this.nuevoComentario())) {
      this.notificaciones.aviso('Escriba un comentario');
      return;
    }

    this.enviandoSeguimiento.set(true);
    this.repositorio
      .agregarSeguimiento(this.id(), {
        comentario: this.nuevoComentario(),
        estadoNuevo: this.nuevoEstado() || null,
      })
      .subscribe({
        next: () => {
          this.enviandoSeguimiento.set(false);
          this.nuevoComentario.set('');
          this.nuevoEstado.set('');
          this.notificaciones.exito('Seguimiento agregado');
          // Se recarga el detalle completo: agrega la fila a la tabla en la
          // misma pantalla, sin navegar, tal como se sigue el caso en vivo.
          this.cargar();
        },
        error: (error: ErrorApi) => {
          this.enviandoSeguimiento.set(false);
          this.notificaciones.error('No fue posible agregar el seguimiento', error.mensaje);
        },
      });
  }
}
