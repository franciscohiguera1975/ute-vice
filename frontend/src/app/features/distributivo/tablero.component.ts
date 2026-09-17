import { DatePipe, DecimalPipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { NotificacionesService } from '@core/notificaciones.service';
import {
  ETIQUETAS_ESTADO_VALIDACION,
  type Conteo,
  type ErrorApi,
  type FilaComparativa,
  type TableroDistributivo,
  type ValidacionDePeriodo,
} from '@domain/modelos';
import { RepositorioDistributivo } from '@domain/puertos';
import { CargandoComponent } from '@shared/componentes/cargando.component';
import { VacioComponent } from '@shared/componentes/vacio.component';

import {
  GraficoAnilloComponent,
  GraficoBarrasComponent,
} from '@features/tablero/graficos.component';

/**
 * Tablero del distributivo docente.
 *
 * Compara dos periodos. El eje del que cuelga todo es el estado de validacion,
 * que el sistema academico empezo a entregar en 2026-2; los periodos anteriores
 * lo tienen vacio, y por eso el porcentaje se calcula sobre las filas
 * **evaluadas** y no sobre el total. Un periodo sin ese dato muestra un guion,
 * no un cero: no es que nada estuviera aprobado, es que no se sabe.
 */
@Component({
  selector: 'ute-tablero-distributivo',
  standalone: true,
  imports: [
    DatePipe,
    DecimalPipe,
    FormsModule,
    CargandoComponent,
    VacioComponent,
    GraficoAnilloComponent,
    GraficoBarrasComponent,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './tablero.component.html',
  styleUrl: './tablero.component.scss',
})
export class TableroDistributivoComponent {
  private readonly repositorio = inject(RepositorioDistributivo);
  private readonly notificaciones = inject(NotificacionesService);

  protected readonly datos = signal<TableroDistributivo | null>(null);
  protected readonly cargando = signal(true);
  protected readonly paoId = signal('');
  protected readonly paoAnteriorId = signal('');

  constructor() {
    this.cargar();
  }

  protected cargar(): void {
    this.cargando.set(true);
    this.repositorio.tablero(this.paoId() || undefined, this.paoAnteriorId() || undefined).subscribe({
      next: (tablero) => {
        this.datos.set(tablero);
        // El backend decide los periodos cuando no se indican; se reflejan en
        // los selectores para que la pantalla diga exactamente que compara.
        this.paoId.set(tablero.actual?.paoId ?? '');
        this.paoAnteriorId.set(tablero.anterior?.paoId ?? '');
        this.cargando.set(false);
      },
      error: (error: ErrorApi) => {
        this.notificaciones.error(error.mensaje ?? 'No se pudo calcular el tablero');
        this.cargando.set(false);
      },
    });
  }

  protected cambiarActual(id: string): void {
    this.paoId.set(id);
    // Se deja que el backend vuelva a elegir el comparado: al cambiar de nivel
    // —grado a posgrado— el anterior que estaba puesto ya no es comparable.
    this.paoAnteriorId.set('');
    this.cargar();
  }

  protected cambiarAnterior(id: string): void {
    this.paoAnteriorId.set(id);
    this.cargar();
  }

  // ------------------------------------------------------------ derivados
  protected readonly estadosConEtiqueta = computed<readonly Conteo[]>(() =>
    (this.datos()?.actual?.porEstado ?? []).map((c) => ({
      ...c,
      etiqueta: ETIQUETAS_ESTADO_VALIDACION[c.etiqueta] ?? c.etiqueta,
    })),
  );

  /** Avance por facultad, en puntos de porcentaje sobre las evaluadas. */
  protected readonly avancePorFacultad = computed<readonly Conteo[]>(() =>
    (this.datos()?.porFacultad ?? [])
      .filter((f) => f.evaluadasActual > 0)
      .map((f) => ({
        etiqueta: f.etiqueta,
        valor: Math.round(f.porcentajeActual),
        porcentaje: f.porcentajeActual,
      })),
  );

  /**
   * Diferencia de filas entre los dos periodos.
   *
   * Es lo primero que se mira al recibir un PAO nuevo: si el periodo entrante
   * trae mucha menos carga que el anterior, la exportacion vino incompleta.
   */
  protected readonly variacionDeFilas = computed(() => {
    const d = this.datos();
    if (!d?.actual || !d.anterior) return null;
    return d.actual.total - d.anterior.total;
  });

  protected readonly hayComparacion = computed(() => (this.datos()?.anterior?.evaluadas ?? 0) > 0);

  /** Un periodo sin estados no aporta un porcentaje, aporta un guion. */
  protected porcentaje(periodo: ValidacionDePeriodo | null | undefined): string {
    if (!periodo || periodo.evaluadas === 0) return '—';
    return `${periodo.porcentajeAprobado.toFixed(1)} %`;
  }

  protected porcentajeFila(aprobadas: number, evaluadas: number): string {
    return evaluadas === 0 ? '—' : `${((aprobadas / evaluadas) * 100).toFixed(1)} %`;
  }

  protected variacionDeFila(fila: FilaComparativa): string {
    if (fila.evaluadasActual === 0 || fila.evaluadasAnterior === 0) return '—';
    const signo = fila.variacion > 0 ? '+' : '';
    return `${signo}${fila.variacion.toFixed(1)}`;
  }

  protected etiquetaEstado(codigo: string): string {
    return ETIQUETAS_ESTADO_VALIDACION[codigo] ?? codigo;
  }

  /**
   * Las cinco filas de la tabla de estados, incluidas las que valen cero.
   *
   * El backend omite los estados sin filas —lo que es correcto para el
   * anillo—, pero la tabla tiene que mostrar los cinco siempre: que
   * «Con error» valga cero es justamente lo que se quiere leer.
   */
  protected readonly desgloseDeEstados = computed(() => {
    const d = this.datos();
    const orden = ['OK', 'OK_EXCEPCION', 'PENDIENTE', 'ERROR', 'SIN_ESTADO'];

    const valores = (periodo: ValidacionDePeriodo | null) =>
      new Map((periodo?.porEstado ?? []).map((c) => [c.etiqueta, c.valor]));

    const actual = valores(d?.actual ?? null);
    const anterior = valores(d?.anterior ?? null);
    const totalActual = d?.actual?.total ?? 0;
    const totalAnterior = d?.anterior?.total ?? 0;

    return orden.map((codigo) => ({
      codigo,
      etiqueta: this.etiquetaEstado(codigo),
      actual: actual.get(codigo) ?? 0,
      porcentajeActual: totalActual ? ((actual.get(codigo) ?? 0) / totalActual) * 100 : 0,
      anterior: anterior.get(codigo) ?? 0,
      porcentajeAnterior: totalAnterior ? ((anterior.get(codigo) ?? 0) / totalAnterior) * 100 : 0,
    }));
  });
}
