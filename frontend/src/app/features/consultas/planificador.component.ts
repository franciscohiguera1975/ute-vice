import { DecimalPipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';

import { NotificacionesService } from '@core/notificaciones.service';
import type { ErrorApi, EstadoPlanificador } from '@domain/modelos';
import { RepositorioConsultas } from '@domain/puertos';
import { CargandoComponent } from '@shared/componentes/cargando.component';
import { InsigniaComponent } from '@shared/componentes/insignia.component';
import { FechaLocalPipe } from '@shared/pipes/formato.pipe';

import { SubmenuConsultasComponent } from './submenu.component';

/**
 * Estado del planificador.
 *
 * Existe sobre todo para responder una pregunta concreta del operador: *¿por
 * que el sistema no esta consultando ahora mismo?*. Muestra la franja horaria
 * vigente, el presupuesto y la capacidad estimada, en lugar de dejar que el
 * comportamiento parezca arbitrario.
 */
@Component({
  selector: 'ute-planificador',
  standalone: true,
  imports: [
    DecimalPipe,
    CargandoComponent,
    InsigniaComponent,
    FechaLocalPipe,
    SubmenuConsultasComponent,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './planificador.component.html',
  styleUrl: './planificador.component.scss',
})
export class PlanificadorComponent {
  private readonly repositorio = inject(RepositorioConsultas);
  private readonly notificaciones = inject(NotificacionesService);

  protected readonly estado = signal<EstadoPlanificador | null>(null);
  protected readonly cargando = signal(true);

  constructor() {
    this.cargar();
  }

  protected cargar(): void {
    this.cargando.set(true);
    this.repositorio.estadoPlanificador().subscribe({
      next: (estado) => {
        this.estado.set(estado);
        this.cargando.set(false);
      },
      error: (error: ErrorApi) => {
        this.cargando.set(false);
        this.notificaciones.error('No fue posible consultar el planificador', error.mensaje);
      },
    });
  }

  protected tonoFranja(franja: string): 'exito' | 'aviso' | 'neutro' {
    return { PICO: 'exito' as const, VALLE: 'aviso' as const }[franja] ?? 'neutro';
  }

  protected etiquetaFranja(franja: string): string {
    return (
      {
        PICO: 'Horario de oficina',
        VALLE: 'Tarde-noche',
        INACTIVA: 'Fuera de horario',
      }[franja] ?? franja
    );
  }
}
