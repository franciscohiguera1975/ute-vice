import { DatePipe, DecimalPipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';

import { NotificacionesService } from '@core/notificaciones.service';
import {
  ETIQUETAS_ESTADO_CONSULTA,
  ETIQUETAS_NIVEL,
  type Conteo,
  type ErrorApi,
  type EstadoConsulta,
  type NivelTitulo,
  type Tablero,
} from '@domain/modelos';
import { RepositorioTablero } from '@domain/puertos';
import { CargandoComponent } from '@shared/componentes/cargando.component';

import {
  GraficoAnilloComponent,
  GraficoBarrasComponent,
  GraficoLineaComponent,
} from './graficos.component';

@Component({
  selector: 'ute-tablero',
  standalone: true,
  imports: [
    DatePipe,
    DecimalPipe,
    RouterLink,
    CargandoComponent,
    GraficoBarrasComponent,
    GraficoAnilloComponent,
    GraficoLineaComponent,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './tablero.component.html',
  styleUrl: './tablero.component.scss',
})
export class TableroComponent {
  private readonly repositorio = inject(RepositorioTablero);
  private readonly notificaciones = inject(NotificacionesService);

  protected readonly datos = signal<Tablero | null>(null);
  protected readonly cargando = signal(true);
  protected readonly dias = signal(30);

  protected readonly opcionesDias = [7, 30, 90, 180];

  /**
   * Niveles con etiqueta legible.
   *
   * El backend devuelve el codigo (`TERCER_NIVEL`); la traduccion ocurre aqui,
   * en el borde, usando el mismo diccionario que el resto de la interfaz.
   */
  protected readonly nivelesConEtiqueta = computed<readonly Conteo[]>(() =>
    (this.datos()?.titulos.porNivel ?? []).map((c) => ({
      ...c,
      etiqueta: ETIQUETAS_NIVEL[c.etiqueta as NivelTitulo] ?? c.etiqueta,
    })),
  );

  protected readonly estadosConEtiqueta = computed<readonly Conteo[]>(() =>
    (this.datos()?.consultas.porEstado ?? []).map((c) => ({
      ...c,
      etiqueta: ETIQUETAS_ESTADO_CONSULTA[c.etiqueta as EstadoConsulta] ?? c.etiqueta,
    })),
  );

  /** Situaciones que requieren atencion de un funcionario. */
  protected readonly alertas = computed(() => {
    const d = this.datos();
    if (!d) return [];

    const lista: { texto: string; ruta: string; parametros?: Record<string, string> }[] = [];

    if (d.cobertura.nuncaConsultadas > 0) {
      lista.push({
        texto: `${d.cobertura.nuncaConsultadas} persona(s) nunca consultadas`,
        ruta: '/personas',
        parametros: { nuncaConsultadas: 'true' },
      });
    }
    if (d.cobertura.conErrorUltimaConsulta > 0) {
      lista.push({
        texto: `${d.cobertura.conErrorUltimaConsulta} consulta(s) con error pendientes de reintento`,
        ruta: '/consultas/logs',
        parametros: { soloErrores: 'true' },
      });
    }
    if (d.titulos.retirados > 0) {
      lista.push({
        texto: `${d.titulos.retirados} titulo(s) retirados del registro nacional`,
        ruta: '/titulos',
        parametros: { estado: 'RETIRADO' },
      });
    }
    if (d.titulos.porVerificar > 0) {
      lista.push({
        texto: `${d.titulos.porVerificar} titulo(s) cargados a mano sin verificar`,
        ruta: '/titulos',
        parametros: { estado: 'POR_VERIFICAR' },
      });
    }
    if (d.consultas.esperandoDesafio > 0) {
      lista.push({
        texto: `${d.consultas.esperandoDesafio} consulta(s) esperando verificacion humana`,
        ruta: '/consultas/jobs',
      });
    }
    return lista;
  });

  constructor() {
    this.cargar();
  }

  protected cambiarPeriodo(dias: number): void {
    this.dias.set(dias);
    this.cargar();
  }

  protected cargar(): void {
    this.cargando.set(true);
    this.repositorio.obtener(this.dias()).subscribe({
      next: (tablero) => {
        this.datos.set(tablero);
        this.cargando.set(false);
      },
      error: (error: ErrorApi) => {
        this.cargando.set(false);
        this.notificaciones.error('No fue posible cargar el tablero', error.mensaje);
      },
    });
  }
}
