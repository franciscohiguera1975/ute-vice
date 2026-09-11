import { ChangeDetectionStrategy, Component, computed, inject, input, signal } from '@angular/core';
import { Router, RouterLink } from '@angular/router';

import { NotificacionesService } from '@core/notificaciones.service';
import { SesionStore } from '@core/sesion.store';
import {
  ETIQUETAS_ESTADO_CONSULTA,
  ETIQUETAS_ESTADO_TITULO,
  ETIQUETAS_NIVEL,
  ETIQUETAS_ORIGEN,
  ETIQUETAS_VINCULACION,
  OrigenTitulo,
  Permiso,
  TONO_ESTADO_TITULO,
  type ErrorApi,
  type PersonaDetalle,
  type Titulo,
} from '@domain/modelos';
import { RepositorioConsultas, RepositorioPersonas, RepositorioTitulos } from '@domain/puertos';
import { CargandoComponent } from '@shared/componentes/cargando.component';
import { ConfirmarComponent } from '@shared/componentes/confirmar.component';
import { InsigniaComponent } from '@shared/componentes/insignia.component';
import { VacioComponent } from '@shared/componentes/vacio.component';
import { PermisoDirective } from '@shared/directivas/permiso.directive';
import { DesdeHacePipe, FechaLocalPipe } from '@shared/pipes/formato.pipe';

@Component({
  selector: 'ute-detalle-persona',
  standalone: true,
  imports: [
    RouterLink,
    CargandoComponent,
    ConfirmarComponent,
    InsigniaComponent,
    VacioComponent,
    PermisoDirective,
    FechaLocalPipe,
    DesdeHacePipe,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './detalle.component.html',
  styleUrl: './detalle.component.scss',
})
export class DetallePersonaComponent {
  private readonly personas = inject(RepositorioPersonas);
  private readonly titulos = inject(RepositorioTitulos);
  private readonly consultas = inject(RepositorioConsultas);
  private readonly notificaciones = inject(NotificacionesService);
  private readonly router = inject(Router);
  protected readonly sesion = inject(SesionStore);

  /** Enlazado desde la ruta gracias a `withComponentInputBinding()`. */
  readonly id = input.required<string>();

  protected readonly Permiso = Permiso;
  protected readonly OrigenTitulo = OrigenTitulo;
  protected readonly ETIQUETAS = {
    nivel: ETIQUETAS_NIVEL,
    estadoTitulo: ETIQUETAS_ESTADO_TITULO,
    origen: ETIQUETAS_ORIGEN,
    vinculacion: ETIQUETAS_VINCULACION,
    estadoConsulta: ETIQUETAS_ESTADO_CONSULTA,
  };
  protected readonly TONO_ESTADO_TITULO = TONO_ESTADO_TITULO;

  protected readonly detalle = signal<PersonaDetalle | null>(null);
  protected readonly cargando = signal(true);
  protected readonly consultando = signal(false);
  protected readonly confirmarConsultaForzada = signal(false);
  protected readonly confirmarEliminar = signal(false);

  /** Los titulos retirados se muestran aparte: son el hallazgo a auditar. */
  protected readonly titulosVigentes = computed(() =>
    (this.detalle()?.titulos ?? []).filter((t) => t.estado !== 'RETIRADO'),
  );
  protected readonly titulosRetirados = computed(() =>
    (this.detalle()?.titulos ?? []).filter((t) => t.estado === 'RETIRADO'),
  );

  constructor() {
    // `input.required` ya esta disponible cuando corre el constructor porque el
    // enrutador enlaza las entradas antes de crear el componente.
    queueMicrotask(() => this.cargar());
  }

  protected cargar(): void {
    this.cargando.set(true);
    this.personas.obtener(this.id()).subscribe({
      next: (detalle) => {
        this.detalle.set(detalle);
        this.cargando.set(false);
      },
      error: (error: ErrorApi) => {
        this.cargando.set(false);
        this.notificaciones.error('No fue posible cargar la persona', error.mensaje);
        void this.router.navigate(['/personas']);
      },
    });
  }

  protected consultar(forzar = false): void {
    this.confirmarConsultaForzada.set(false);
    this.consultando.set(true);

    this.consultas.consultarPersona(this.id(), forzar).subscribe({
      next: (resultado) => {
        this.consultando.set(false);

        if (resultado.requiereIntervencion) {
          this.notificaciones.aviso(
            'La consulta requiere verificacion humana',
            'Quedo en la cola de desafios pendientes. Resuelvala desde Consultas.',
          );
        } else if (resultado.log.huboCambios) {
          this.notificaciones.exito('Se detectaron cambios', resultado.log.resumen);
        } else {
          this.notificaciones.info('Consulta completada', resultado.log.resumen);
        }
        this.cargar();
      },
      error: (error: ErrorApi) => {
        this.consultando.set(false);

        // 409 significa que la persona ya fue cubierta en el periodo vigente:
        // se ofrece forzar, en lugar de dejar al usuario sin salida.
        if (error.estado === 409) {
          this.confirmarConsultaForzada.set(true);
          return;
        }
        this.notificaciones.error('No fue posible completar la consulta', error.mensaje);
      },
    });
  }

  protected verificarTitulo(titulo: Titulo): void {
    this.titulos.verificar(titulo.id).subscribe({
      next: () => {
        this.notificaciones.exito('Titulo marcado como verificado');
        this.cargar();
      },
      error: (error: ErrorApi) =>
        this.notificaciones.error('No fue posible verificar el titulo', error.mensaje),
    });
  }

  protected eliminar(): void {
    this.confirmarEliminar.set(false);
    this.personas.eliminar(this.id()).subscribe({
      next: () => {
        this.notificaciones.exito('Persona eliminada');
        void this.router.navigate(['/personas']);
      },
      error: (error: ErrorApi) =>
        this.notificaciones.error('No fue posible eliminar', error.mensaje),
    });
  }
}
