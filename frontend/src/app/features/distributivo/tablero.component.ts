import { DatePipe, DecimalPipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';

import { DescargaService } from '@core/descarga.service';
import { NotificacionesService } from '@core/notificaciones.service';
import {
  ETIQUETAS_ESTADO_VALIDACION,
  FormatoReporte,
  Permiso,
  TipoResumen,
  type Conteo,
  type ErrorApi,
  type FilaComparativa,
  type TableroDistributivo,
  type ValidacionDeGrupo,
} from '@domain/modelos';
import { RepositorioDistributivo } from '@domain/puertos';
import { CargandoComponent } from '@shared/componentes/cargando.component';
import { VacioComponent } from '@shared/componentes/vacio.component';
import { PermisoDirective } from '@shared/directivas/permiso.directive';

import {
  GraficoAnilloComponent,
  GraficoBarrasComponent,
} from '@features/tablero/graficos.component';

import { SelectorGruposComponent } from './selector-grupos.component';

/**
 * Tablero del distributivo docente.
 *
 * Compara dos **grupos** de periodos, no dos periodos: un semestre son tres
 * —tecnologia, grado y posgrado— mas sus interciclos, y mirar solo el de grado
 * deja fuera media institucion. Usa el mismo selector y la misma propuesta por
 * defecto que los resumenes, para que las dos pantallas no digan cifras
 * distintas del mismo periodo.
 *
 * El eje del que cuelga todo es el estado de validacion, que el sistema
 * academico empezo a entregar en 2026-2; los periodos anteriores lo tienen
 * vacio, y por eso el porcentaje se calcula sobre las filas **evaluadas** y no
 * sobre el total. Un grupo sin ese dato muestra un guion, no un cero: no es que
 * nada estuviera aprobado, es que no se sabe.
 */
@Component({
  selector: 'ute-tablero-distributivo',
  standalone: true,
  imports: [
    DatePipe,
    DecimalPipe,
    CargandoComponent,
    VacioComponent,
    PermisoDirective,
    SelectorGruposComponent,
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
  private readonly descarga = inject(DescargaService);

  protected readonly Permiso = Permiso;

  protected readonly datos = signal<TableroDistributivo | null>(null);
  protected readonly cargando = signal(true);

  /** Grupo 1 es la referencia y grupo 2 el que se examina, como en resumenes. */
  protected readonly grupoA = signal<readonly string[]>([]);
  protected readonly grupoB = signal<readonly string[]>([]);

  protected readonly descargando = signal<FormatoReporte | null>(null);
  protected readonly formatos = [
    { valor: FormatoReporte.XLSX, etiqueta: 'Excel' },
    { valor: FormatoReporte.CSV, etiqueta: 'CSV' },
    { valor: FormatoReporte.PDF, etiqueta: 'PDF' },
  ];

  constructor() {
    this.cargar();
  }

  protected cargar(): void {
    this.cargando.set(true);
    this.repositorio.tablero(this.grupoA(), this.grupoB()).subscribe({
      next: (tablero) => {
        this.datos.set(tablero);
        // El backend propone los dos ultimos semestres cuando no se pide nada;
        // se reflejan en el selector para que la pantalla diga que compara.
        if (this.grupoA().length === 0 && this.grupoB().length === 0) {
          this.grupoA.set(this.idsDe(tablero, tablero.anterior?.codigos ?? []));
          this.grupoB.set(this.idsDe(tablero, tablero.actual?.codigos ?? []));
        }
        this.cargando.set(false);
      },
      error: (error: ErrorApi) => {
        this.notificaciones.error(error.mensaje ?? 'No se pudo calcular el tablero');
        this.cargando.set(false);
      },
    });
  }

  private idsDe(datos: TableroDistributivo, codigos: readonly string[]): string[] {
    const buscados = new Set(codigos);
    return datos.periodos.filter((p) => buscados.has(p.codigo)).map((p) => p.id);
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
   * Diferencia de filas entre los dos grupos.
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

  /** Un grupo sin estados no aporta un porcentaje, aporta un guion. */
  protected porcentaje(grupo: ValidacionDeGrupo | null | undefined): string {
    if (!grupo || grupo.evaluadas === 0) return '—';
    return `${grupo.porcentajeAprobado.toFixed(1)} %`;
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

  /** Los codigos del grupo, para titular columnas sin repetir la logica. */
  protected codigosDe(grupo: ValidacionDeGrupo | null | undefined): string {
    return grupo?.codigos.join(' · ') || 'sin periodos';
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

    const valores = (grupo: ValidacionDeGrupo | null) =>
      new Map((grupo?.porEstado ?? []).map((c) => [c.etiqueta, c.valor]));

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

  // ------------------------------------------------------------- descarga
  /**
   * Descarga una de las dos tablas del tablero.
   *
   * Sale del mismo caso de uso que la pantalla, no de los datos ya cargados:
   * asi el archivo no puede decir otra cosa que lo que se esta viendo.
   */
  protected descargar(resumen: TipoResumen, formato: FormatoReporte): void {
    if (this.descargando()) return;
    this.descargando.set(formato);

    this.repositorio
      .exportarResumen(
        { resumen, grupoA: this.grupoA(), grupoB: this.grupoB(), grupo: 'b' },
        formato,
      )
      .subscribe({
        next: (archivo) => {
          this.descarga.guardar(archivo);
          this.descargando.set(null);
        },
        error: (error: ErrorApi) => {
          this.descargando.set(null);
          this.notificaciones.error(error.mensaje ?? 'No se pudo generar el archivo');
        },
      });
  }

  protected readonly TipoResumen = TipoResumen;
}
