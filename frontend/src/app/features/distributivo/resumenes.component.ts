import { DatePipe, DecimalPipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';

import { NotificacionesService } from '@core/notificaciones.service';
import { PermisoDirective } from '@shared/directivas/permiso.directive';
import { DescargaService } from '@core/descarga.service';
import {
  FormatoReporte,
  Permiso,
  TipoResumen,
  type ErrorApi,
  type EstadosDeFacultad,
  type PeriodoConFilas,
  type ResumenComparativo,
} from '@domain/modelos';
import { RepositorioDistributivo } from '@domain/puertos';
import { CargandoComponent } from '@shared/componentes/cargando.component';
import { VacioComponent } from '@shared/componentes/vacio.component';

/** Un semestre con todos sus periodos: lo que se marca de un clic. */
interface Semestre {
  readonly clave: string;
  readonly periodos: readonly PeriodoConFilas[];
  readonly filas: number;
}

/** Cual de los dos grupos se esta editando. */
type Grupo = 'a' | 'b';

/**
 * Resumenes del distributivo.
 *
 * Compara **dos grupos de periodos**, no dos periodos. Un semestre son tres
 * periodos —tecnologia, grado y posgrado— mas sus interciclos, asi que «26-1
 * contra 26-2» son seis codigos contra tres. Marcar el semestre entero es un
 * clic; el detalle permite afinar periodo a periodo.
 */
@Component({
  selector: 'ute-resumenes-distributivo',
  standalone: true,
  imports: [DatePipe, DecimalPipe, CargandoComponent, VacioComponent, PermisoDirective],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './resumenes.component.html',
  styleUrl: './resumenes.component.scss',
})
export class ResumenesDistributivoComponent {
  private readonly repositorio = inject(RepositorioDistributivo);
  private readonly notificaciones = inject(NotificacionesService);
  private readonly descarga = inject(DescargaService);

  protected readonly TipoResumen = TipoResumen;
  protected readonly Permiso = Permiso;

  /** Formato en curso, o `null`. Evita disparar dos descargas a la vez. */
  protected readonly descargando = signal<FormatoReporte | null>(null);

  protected readonly formatos = [
    { valor: FormatoReporte.XLSX, etiqueta: 'Excel' },
    { valor: FormatoReporte.CSV, etiqueta: 'CSV' },
    { valor: FormatoReporte.PDF, etiqueta: 'PDF' },
  ];

  /** Los dos grupos, para recorrerlos en la plantilla sin perder el tipo. */
  protected readonly GRUPOS: readonly Grupo[] = ['a', 'b'];

  protected readonly datos = signal<ResumenComparativo | null>(null);
  protected readonly cargando = signal(true);
  protected readonly resumen = signal<TipoResumen>(TipoResumen.AVANCE);

  /** Ids elegidos en cada grupo. Vacios: el backend propone los dos ultimos semestres. */
  protected readonly grupoA = signal<readonly string[]>([]);
  protected readonly grupoB = signal<readonly string[]>([]);

  /** Que grupo muestra el desglose por estados. */
  protected readonly grupoDeEstados = signal<Grupo>('b');

  protected readonly opcionesResumen = [
    {
      valor: TipoResumen.AVANCE,
      etiqueta: 'Avance entre dos grupos de periodos',
      descripcion:
        'Cuantos de los docentes del primer grupo vuelven a tener carga en el segundo, ' +
        'por facultad, con lo aprobado del segundo.',
    },
    {
      valor: TipoResumen.ESTADOS,
      etiqueta: 'Estados del distributivo',
      descripcion:
        'Las filas de cada facultad repartidas por estado de validacion, con su ' +
        'porcentaje de aprobacion.',
    },
  ];

  constructor() {
    this.cargar();
  }

  protected cargar(): void {
    this.cargando.set(true);
    this.repositorio.resumenes(this.grupoA(), this.grupoB()).subscribe({
      next: (datos) => {
        this.datos.set(datos);
        // El backend propone los dos ultimos semestres cuando no se pide nada;
        // se reflejan en los selectores para que la pantalla diga que compara.
        if (this.grupoA().length === 0 && this.grupoB().length === 0) {
          this.grupoA.set(this.idsDeCodigos(datos, datos.grupoA?.codigos ?? []));
          this.grupoB.set(this.idsDeCodigos(datos, datos.grupoB?.codigos ?? []));
        }
        this.cargando.set(false);
      },
      error: (error: ErrorApi) => {
        this.notificaciones.error(error.mensaje ?? 'No se pudo calcular el resumen');
        this.cargando.set(false);
      },
    });
  }

  private idsDeCodigos(datos: ResumenComparativo, codigos: readonly string[]): string[] {
    const buscados = new Set(codigos);
    return datos.periodos.filter((p) => buscados.has(p.codigo)).map((p) => p.id);
  }

  // ----------------------------------------------------------- semestres
  protected readonly semestres = computed<readonly Semestre[]>(() => {
    const por = new Map<string, PeriodoConFilas[]>();
    for (const p of this.datos()?.periodos ?? []) {
      // Sin semestre en los atributos, se deriva del codigo: `2026-2` sale de
      // `262651` como `20` + `26` + `-` + `2`.
      const clave = p.semestre || `20${p.codigo.slice(0, 2)}-${p.codigo.slice(2, 3)}`;
      por.set(clave, [...(por.get(clave) ?? []), p]);
    }
    return [...por.entries()]
      .map(([clave, periodos]) => ({
        clave,
        periodos,
        filas: periodos.reduce((suma, p) => suma + p.filas, 0),
      }))
      .sort((x, y) => y.clave.localeCompare(x.clave));
  });

  private senal(grupo: Grupo) {
    return grupo === 'a' ? this.grupoA : this.grupoB;
  }

  protected seleccionado(grupo: Grupo, id: string): boolean {
    return this.senal(grupo)().includes(id);
  }

  protected semestreCompleto(grupo: Grupo, semestre: Semestre): boolean {
    return semestre.periodos.every((p) => this.seleccionado(grupo, p.id));
  }

  protected alternarSemestre(grupo: Grupo, semestre: Semestre): void {
    const ids = semestre.periodos.map((p) => p.id);
    const quitar = this.semestreCompleto(grupo, semestre);
    this.senal(grupo).update((actual) =>
      quitar
        ? actual.filter((id) => !ids.includes(id))
        : [...new Set([...actual, ...ids])],
    );
  }

  protected alternarPeriodo(grupo: Grupo, id: string): void {
    this.senal(grupo).update((actual) =>
      actual.includes(id) ? actual.filter((x) => x !== id) : [...actual, id],
    );
  }

  protected limpiar(grupo: Grupo): void {
    this.senal(grupo).set([]);
  }

  protected readonly puedeComparar = computed(
    () => this.grupoA().length > 0 || this.grupoB().length > 0,
  );

  // ------------------------------------------------------------ derivados
  protected readonly estadosMostrados = computed<readonly EstadosDeFacultad[]>(() => {
    const d = this.datos();
    if (!d) return [];
    return this.grupoDeEstados() === 'a' ? d.estadosA : d.estadosB;
  });

  protected readonly grupoMostrado = computed(() => {
    const d = this.datos();
    return this.grupoDeEstados() === 'a' ? (d?.grupoA ?? null) : (d?.grupoB ?? null);
  });

  /**
   * Totales de la tabla de estados.
   *
   * Se suman aqui y no en el backend porque son sumas de columnas ya
   * presentes: una llamada mas no aportaria nada.
   */
  protected readonly totalEstados = computed(() => {
    const filas = this.estadosMostrados();
    const suma = (extraer: (e: EstadosDeFacultad) => number) =>
      filas.reduce((total, e) => total + extraer(e), 0);

    const evaluadas = suma((e) => e.evaluadas);
    const aprobadas = suma((e) => e.ok + e.okExcepcion);
    return {
      ok: suma((e) => e.ok),
      okExcepcion: suma((e) => e.okExcepcion),
      pendiente: suma((e) => e.pendiente),
      conError: suma((e) => e.conError),
      sinEstado: suma((e) => e.sinEstado),
      total: suma((e) => e.total),
      evaluadas,
      porcentajeAprobado: evaluadas === 0 ? 0 : (aprobadas / evaluadas) * 100,
    };
  });

  /** Suma de la columna por facultad, que **no** es el total de docentes distintos. */
  protected readonly sumaColumnas = computed(() => {
    const filas = this.datos()?.avance ?? [];
    const suma = (extraer: (a: (typeof filas)[number]) => number) =>
      filas.reduce((total, a) => total + extraer(a), 0);
    return {
      docentesA: suma((a) => a.docentesA),
      docentesB: suma((a) => a.docentesB),
      filasB: suma((a) => a.filasB),
      aprobadasB: suma((a) => a.filasAprobadasB),
    };
  });

  protected porcentaje(parte: number, total: number): string {
    return total === 0 ? '—' : `${((parte / total) * 100).toFixed(1)} %`;
  }

  protected codigosDe(grupo: Grupo): string {
    const g = grupo === 'a' ? this.datos()?.grupoA : this.datos()?.grupoB;
    return g?.codigos.join(' · ') || 'sin periodos';
  }

  // ------------------------------------------------------------- descarga
  /**
   * Descarga el resumen que se esta viendo, en el formato elegido.
   *
   * El archivo lo arma el backend a partir del **mismo caso de uso** que
   * alimenta la pantalla, no de los datos ya cargados: asi no puede decir otra
   * cosa que lo que se esta viendo, y de paso salen los tres formatos del
   * mismo camino que el resto de los reportes.
   */
  protected descargar(formato: FormatoReporte): void {
    if (this.descargando()) return;
    this.descargando.set(formato);

    this.repositorio
      .exportarResumen(
        {
          resumen: this.resumen(),
          grupoA: this.grupoA(),
          grupoB: this.grupoB(),
          grupo: this.grupoDeEstados(),
        },
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
}
