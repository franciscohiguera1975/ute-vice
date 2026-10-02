import { DecimalPipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';

import { NotificacionesService } from '@core/notificaciones.service';
import { SesionStore } from '@core/sesion.store';
import { Permiso, type ErrorApi, type EstadisticasTickets } from '@domain/modelos';
import { RepositorioTickets } from '@domain/puertos';
import { CargandoComponent } from '@shared/componentes/cargando.component';

import {
  GraficoAnilloComponent,
  GraficoBarrasComponent,
  GraficoLineaComponent,
} from '@features/tablero/graficos.component';

/**
 * Dashboard de soporte.
 *
 * El alcance de los datos —propios o globales— ya lo decide el backend segun
 * `Permiso.TICKETS_ADMINISTRAR`; esta pantalla solo ajusta el texto segun lo
 * que el usuario puede ver, no vuelve a filtrar nada por su cuenta.
 */
@Component({
  selector: 'ute-estadisticas-tickets',
  standalone: true,
  imports: [DecimalPipe, CargandoComponent, GraficoAnilloComponent, GraficoBarrasComponent, GraficoLineaComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './estadisticas.component.html',
  styleUrl: './estadisticas.component.scss',
})
export class EstadisticasTicketsComponent {
  private readonly repositorio = inject(RepositorioTickets);
  private readonly notificaciones = inject(NotificacionesService);
  protected readonly sesion = inject(SesionStore);

  protected readonly Permiso = Permiso;
  protected readonly datos = signal<EstadisticasTickets | null>(null);
  protected readonly cargando = signal(true);
  protected readonly dias = signal(30);
  protected readonly opcionesDias = [7, 30, 90, 180];

  constructor() {
    this.cargar();
  }

  protected cambiarPeriodo(dias: number): void {
    this.dias.set(dias);
    this.cargar();
  }

  protected cargar(): void {
    this.cargando.set(true);
    this.repositorio.estadisticas(this.dias()).subscribe({
      next: (datos) => {
        this.datos.set(datos);
        this.cargando.set(false);
      },
      error: (error: ErrorApi) => {
        this.cargando.set(false);
        this.notificaciones.error('No fue posible cargar las estadisticas', error.mensaje);
      },
    });
  }

  protected tiempoPromedio(): string {
    const horas = this.datos()?.tiempoPromedioResolucionHoras;
    if (horas === null || horas === undefined) return '—';
    return horas < 48 ? `${horas.toFixed(1)} h` : `${(horas / 24).toFixed(1)} d`;
  }
}
