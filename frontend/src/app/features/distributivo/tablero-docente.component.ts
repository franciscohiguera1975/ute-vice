import { DatePipe, DecimalPipe } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  ViewChild,
  computed,
  inject,
  signal,
} from '@angular/core';

import { NotificacionesService } from '@core/notificaciones.service';
import {
  type DocenteResumen,
  type ErrorApi,
  type FilaSplitCarrera,
  type TableroDocente,
} from '@domain/modelos';
import { RepositorioDistributivo } from '@domain/puertos';
import { CargandoComponent } from '@shared/componentes/cargando.component';
import { VacioComponent } from '@shared/componentes/vacio.component';

import { SelectorGruposComponent } from './selector-grupos.component';
import {
  type Alerta,
  BINS_TP,
  DEDICACIONES_FILTRABLES,
  type Dedicacion,
  ETIQUETAS_DEDICACION,
  type FiltrosTablero,
  type NivelSemaforo,
  agregarSplit,
  agruparPorFacultad,
  alertasDocente,
  cantidadDeFunciones,
  claveDedicacion,
  cumpleFiltroDocente,
  cumpleFiltroSplit,
  etcDe,
  gpill,
  ipill,
  mediana,
  movimientoDePersonas,
  movimientoPorFacultad,
  pill3,
  plantaDe,
  porcentajeTC,
  promedio,
  ratioPill,
  sumaPorDocenteUnico,
  tcPill,
  tcQueFaltanPara,
  topeH,
} from './tablero-docente.calculos';

type Pestana = 'variacion' | 'da' | 'gestion' | 'top' | 'tp' | 'estudiantes' | 'organizacion';
type ColumnaTop = 'tot' | 'da' | 'd' | 'i' | 'v' | 'g';

const PESTANAS: ReadonlyArray<{ readonly id: Pestana; readonly etiqueta: string }> = [
  { id: 'variacion', etiqueta: 'Variación de periodo' },
  { id: 'da', etiqueta: 'Docencia directa (Da)' },
  { id: 'gestion', etiqueta: 'Gestión' },
  { id: 'top', etiqueta: 'Más horas' },
  { id: 'tp', etiqueta: 'Tiempos parciales' },
  { id: 'estudiantes', etiqueta: 'Estudiantes por docente' },
  { id: 'organizacion', etiqueta: 'Organización' },
];

/**
 * Tablero Docente.
 *
 * Replica el diseño y los calculos de un prototipo HTML standalone
 * (`docs/dashboard_ejecutivo/Tablero docente UTE.html`), alimentado por la
 * base de datos. El backend solo entrega datos crudos por docente y por
 * carrera —`RepositorioDistributivo.tableroDocente`—; todas las formulas
 * —topes, alertas, ETC, semaforos— y los filtros globales de la pantalla se
 * calculan aqui, en el cliente, sobre funciones puras de
 * `tablero-docente.calculos.ts`. Cambiar un filtro no dispara entonces una
 * peticion nueva.
 *
 * La pestana «Estudiantes por docente» cuenta estudiantes por `carreraId`, no
 * por sede: la sede de la matricula estudiantil es texto libre de Banner, sin
 * catalogo propio, y cruzarla con `cat_sedes` por nombre caeria en el mismo
 * fuzzy-matching que se evito para la carrera — ver `estudiantesPorCarrera`.
 */
@Component({
  selector: 'ute-tablero-docente',
  standalone: true,
  imports: [DecimalPipe, DatePipe, CargandoComponent, VacioComponent, SelectorGruposComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './tablero-docente.component.html',
  styleUrl: './tablero-docente.component.scss',
})
export class TableroDocenteComponent {
  private readonly repositorio = inject(RepositorioDistributivo);
  private readonly notificaciones = inject(NotificacionesService);

  @ViewChild('dlg') private readonly dialogo?: ElementRef<HTMLDialogElement>;

  protected readonly PESTANAS = PESTANAS;
  protected readonly DEDICACIONES_FILTRABLES = DEDICACIONES_FILTRABLES;
  protected readonly ETIQUETAS_DEDICACION = ETIQUETAS_DEDICACION;
  protected readonly BINS_TP = BINS_TP;

  protected readonly datos = signal<TableroDocente | null>(null);
  protected readonly cargando = signal(true);

  protected readonly grupoA = signal<readonly string[]>([]);
  protected readonly grupoB = signal<readonly string[]>([]);

  protected readonly pestana = signal<Pestana>('variacion');

  // --------------------------------------------------------------- filtros
  protected readonly facultad = signal('');
  protected readonly nivel = signal('');
  protected readonly dedicacion = signal('');
  protected readonly titularidad = signal<'' | 'titular' | 'no_titular'>('');
  protected readonly incluirTecnicos = signal(false);
  protected readonly excluirDirectivos = signal(false);

  protected readonly filtros = computed<FiltrosTablero>(() => ({
    facultadCodigo: this.facultad() || null,
    nivel: this.nivel() || null,
    dedicacion: (this.dedicacion() || null) as Dedicacion | null,
    titularidad: this.titularidad() || null,
    incluirTecnicos: this.incluirTecnicos(),
    excluirDirectivos: this.excluirDirectivos(),
  }));

  protected readonly hayFiltrosActivos = computed(() => {
    const f = this.filtros();
    return !!(f.facultadCodigo || f.nivel || f.dedicacion || f.titularidad);
  });

  protected limpiarFiltros(): void {
    this.facultad.set('');
    this.nivel.set('');
    this.dedicacion.set('');
    this.titularidad.set('');
  }

  // ----------------------------------------------------------- top (orden)
  protected readonly ordenTop = signal<ColumnaTop>('tot');
  protected ordenarTopPor(columna: ColumnaTop): void {
    this.ordenTop.set(columna);
  }

  // ------------------------------------------------------- ficha de detalle
  protected readonly docenteAbierto = signal<DocenteResumen | null>(null);

  protected abrirDocente(d: DocenteResumen): void {
    this.docenteAbierto.set(d);
    this.dialogo?.nativeElement.showModal();
  }

  protected cerrarDocente(): void {
    this.dialogo?.nativeElement.close();
    this.docenteAbierto.set(null);
  }

  protected readonly docenteAnteriorAbierto = computed<DocenteResumen | null>(() => {
    const d = this.docenteAbierto();
    if (!d) return null;
    return (this.datos()?.docentesAnterior ?? []).find((x) => x.docenteId === d.docenteId) ?? null;
  });

  protected alertasDe(d: DocenteResumen): readonly Alerta[] {
    return alertasDocente(d);
  }

  /** Las cinco barras de horas de la ficha de detalle. */
  protected barrasHoras(
    d: DocenteResumen,
  ): ReadonlyArray<{ readonly etiqueta: string; readonly valor: number }> {
    return [
      { etiqueta: 'Docencia (D)', valor: d.d },
      { etiqueta: 'Clases (Da)', valor: d.da },
      { etiqueta: 'Investigación (I)', valor: d.i },
      { etiqueta: 'Vinculación (V)', valor: d.v },
      { etiqueta: 'Gestión (G)', valor: d.g },
    ];
  }

  /** Ancho de cada barra, sobre una escala de al menos 40 h —el tope de un TC—. */
  protected anchoBarra(valor: number, total: number): number {
    const base = Math.max(40, total);
    return base ? Math.min(100, (valor / base) * 100) : 0;
  }

  /**
   * `valor / total`, o 0 sin dividir por cero.
   *
   * Existe para que la plantilla no mezcle un operador ternario con un `pipe`
   * en la misma expresión —ambiguo de leer y facil de romper—; aqui se
   * resuelve en TypeScript y la plantilla solo formatea un numero.
   */
  protected razon(valor: number, total: number): number {
    return total ? valor / total : 0;
  }

  protected porcentaje(valor: number, total: number): number {
    return this.razon(valor, total) * 100;
  }

  protected claveDedicacionDe(d: { readonly dedicacion: string }): Dedicacion {
    return claveDedicacion(d.dedicacion);
  }

  // -------------------------------------------------------------- carga
  constructor() {
    this.cargar();
  }

  protected cargar(): void {
    this.cargando.set(true);
    this.repositorio.tableroDocente(this.grupoA(), this.grupoB()).subscribe({
      next: (tablero) => {
        this.datos.set(tablero);
        // El backend propone los dos ultimos semestres cuando no se pide
        // nada; se reflejan en el selector para que la pantalla diga que
        // compara, igual que en `/distributivo/tablero`.
        if (this.grupoA().length === 0 && this.grupoB().length === 0) {
          this.grupoA.set(this.idsDe(tablero, tablero.codigosAnterior));
          this.grupoB.set(this.idsDe(tablero, tablero.codigosActual));
        }
        this.cargando.set(false);
      },
      error: (error: ErrorApi) => {
        this.notificaciones.error(error.mensaje ?? 'No se pudo calcular el tablero docente');
        this.cargando.set(false);
      },
    });
  }

  private idsDe(tablero: TableroDocente, codigos: readonly string[]): string[] {
    const buscados = new Set(codigos);
    return tablero.periodos.filter((p) => buscados.has(p.codigo)).map((p) => p.id);
  }

  /** El subtitulo de la cabecera: que periodos se estan comparando. */
  protected readonly subtitulo = computed(() => {
    const d = this.datos();
    if (!d) return '';
    const nombrePorCodigo = new Map(d.periodos.map((p) => [p.codigo, `${p.codigo} - ${p.nombre}`]));
    const etiqueta = (codigos: readonly string[]) =>
      codigos.map((c) => nombrePorCodigo.get(c) ?? c).join(', ');
    const actual = etiqueta(d.codigosActual);
    const anterior = etiqueta(d.codigosAnterior);
    if (!actual) return '';
    return anterior ? `${actual} (comparado con ${anterior})` : actual;
  });

  // ---------------------------------------------------- listas filtradas
  protected readonly docentesFiltrados = computed(() =>
    (this.datos()?.docentes ?? []).filter((d) => cumpleFiltroDocente(d, this.filtros())),
  );

  protected readonly docentesAnteriorFiltrados = computed(() =>
    (this.datos()?.docentesAnterior ?? []).filter((d) => cumpleFiltroDocente(d, this.filtros())),
  );

  /** Todos los docentes del grupo actual, sin filtrar: el dueno de cada fila
   * de `split`, para resolver su tope de Da y sus atributos principales. */
  protected readonly docentesPorId = computed(
    () => new Map((this.datos()?.docentes ?? []).map((d) => [d.docenteId, d])),
  );

  protected readonly splitFiltrado = computed(() => {
    const porId = this.docentesPorId();
    const f = this.filtros();
    return (this.datos()?.split ?? []).filter((s) => cumpleFiltroSplit(s, porId.get(s.docenteId), f));
  });

  // -------------------------------------------------------------- opciones
  protected readonly facultadesDisponibles = computed(() => {
    const vistas = new Map<string, string>();
    for (const d of this.datos()?.docentes ?? []) vistas.set(d.facultadCodigo, d.facultadNombre);
    return [...vistas.entries()]
      .map(([codigo, nombre]) => ({ codigo, nombre }))
      .sort((a, b) => a.nombre.localeCompare(b.nombre));
  });

  protected readonly nivelesDisponibles = computed(() => {
    const vistos = new Set<string>();
    for (const d of this.datos()?.docentes ?? []) for (const n of d.niveles) vistos.add(n);
    return [...vistos].sort();
  });

  // =====================================================================
  // Pestana 1: Variacion de periodo
  // =====================================================================

  protected readonly movimiento = computed(() =>
    movimientoDePersonas(this.docentesFiltrados(), this.docentesAnteriorFiltrados()),
  );

  protected readonly porcentajeTCActual = computed(() => porcentajeTC(this.docentesFiltrados()));
  protected readonly porcentajeTCAnterior = computed(() =>
    porcentajeTC(this.docentesAnteriorFiltrados()),
  );

  protected readonly movimientoFacultades = computed(() =>
    movimientoPorFacultad(this.docentesFiltrados(), this.docentesAnteriorFiltrados()),
  );

  // =====================================================================
  // Pestana 2: Docencia directa (Da)
  // =====================================================================

  protected readonly agregadoDaGlobal = computed(() =>
    agregarSplit(this.splitFiltrado(), this.docentesPorId()),
  );

  protected readonly agregadoDaPorDedicacion = computed(() => {
    const porId = this.docentesPorId();
    const filas = this.splitFiltrado();
    return DEDICACIONES_FILTRABLES.map((ded) => ({
      dedicacion: ded,
      agregado: agregarSplit(
        filas.filter((s) => claveDedicacion(s.dedicacion) === ded),
        porId,
      ),
    }));
  });

  protected readonly daPorFacultad = computed(() => {
    const porId = this.docentesPorId();
    const grupos = agruparPorFacultad(this.splitFiltrado());
    return [...grupos.entries()]
      .map(([codigo, { nombre, items }]) => ({
        codigo,
        nombre,
        agregado: agregarSplit(items, porId),
      }))
      .sort((a, b) => b.agregado.tot - a.agregado.tot);
  });

  protected readonly daPorCarrera = computed(() => {
    const porId = this.docentesPorId();
    const mapa = new Map<
      string,
      { facultad: string; carrera: string; filas: FilaSplitCarrera[] }
    >();
    for (const s of this.splitFiltrado()) {
      const clave = `${s.facultadCodigo}|${s.carrera}`;
      const entrada = mapa.get(clave) ?? { facultad: s.facultadNombre, carrera: s.carrera, filas: [] };
      entrada.filas.push(s);
      mapa.set(clave, entrada);
    }
    return [...mapa.values()]
      .map((v) => ({ facultad: v.facultad, carrera: v.carrera, agregado: agregarSplit(v.filas, porId) }))
      .sort((a, b) => b.agregado.tot - a.agregado.tot);
  });

  protected pill3De(r: number): NivelSemaforo {
    return pill3(r);
  }

  // =====================================================================
  // Pestana 3: Gestion (G)
  // =====================================================================

  protected readonly agregadoGGlobal = computed(() =>
    agregarSplit(this.splitFiltrado(), this.docentesPorId()),
  );

  protected readonly docentesConGestion = computed(
    () => [...this.agregadoGGlobal().porDocente.values()].filter((p) => p.g > 0).length,
  );

  protected readonly gestionPromedio = computed(() => {
    const conG = this.docentesConGestion();
    return conG ? this.agregadoGGlobal().g / conG : 0;
  });

  protected readonly gPorFacultad = computed(() => {
    const porId = this.docentesPorId();
    const grupos = agruparPorFacultad(this.splitFiltrado());
    return [...grupos.entries()]
      .map(([codigo, { nombre, items }]) => {
        const agregado = agregarSplit(items, porId);
        const conG = [...agregado.porDocente.values()].filter((p) => p.g > 0).length;
        return { codigo, nombre, agregado, conG };
      })
      .sort((a, b) => b.agregado.g / (b.agregado.tot || 1) - a.agregado.g / (a.agregado.tot || 1));
  });

  protected gpillDe(r: number): NivelSemaforo {
    return gpill(r);
  }

  // =====================================================================
  // Pestana 4: Mas horas
  // =====================================================================

  /** Hereda la exclusion de directivos de `docentesFiltrados`: un docente con
   * cargo directivo no compite por "quien tiene mas horas" como el resto. */
  protected readonly masHoras = computed(() => {
    const columna = this.ordenTop();
    return [...this.docentesFiltrados()].sort((a, b) => b[columna] - a[columna] || b.tot - a.tot);
  });

  protected excedeTope(d: DocenteResumen): boolean {
    const ded = claveDedicacion(d.dedicacion);
    return ded !== 'NA' && d.tot > topeH(ded) + 0.01;
  }

  // =====================================================================
  // Pestana 5: Tiempos parciales (TP)
  // =====================================================================

  protected readonly docentesTP = computed(() =>
    this.docentesFiltrados().filter((d) => claveDedicacion(d.dedicacion) === 'TP'),
  );

  protected readonly tpPromedioDa = computed(() => promedio(this.docentesTP().map((d) => d.da)));
  protected readonly tpMedianaDa = computed(() => mediana(this.docentesTP().map((d) => d.da)));

  protected readonly tpSobreTope = computed(() => this.docentesTP().filter((d) => d.da > 11));
  protected readonly tpSinClases = computed(() => this.docentesTP().filter((d) => d.da === 0));
  protected readonly tpBajoMinimo = computed(() =>
    this.docentesTP().filter((d) => d.da > 0 && d.da < 2),
  );
  protected readonly tp20oMas = computed(() => this.docentesTP().filter((d) => d.tot >= 20));

  protected readonly tpPorFacultad = computed(() => {
    const todos = this.docentesTP();
    const grupos = agruparPorFacultad(todos);
    const filas = [...grupos.entries()].map(([codigo, { nombre, items }]) => ({
      codigo,
      nombre,
      cantidad: items.length,
      promedio: promedio(items.map((d) => d.da)),
      mediana: mediana(items.map((d) => d.da)),
      bins: BINS_TP.map((b) => items.filter((d) => b.prueba(d.da)).length),
    }));
    filas.push({
      codigo: '__total',
      nombre: 'Total',
      cantidad: todos.length,
      promedio: promedio(todos.map((d) => d.da)),
      mediana: mediana(todos.map((d) => d.da)),
      bins: BINS_TP.map((b) => todos.filter((d) => b.prueba(d.da)).length),
    });
    return filas;
  });

  // =====================================================================
  // Pestana 6: Estudiantes por docente
  // =====================================================================

  /**
   * Estudiantes matriculados por carrera, del endpoint
   * (`TableroDocente.estudiantesPorCarrera`), indexados por `carreraId`.
   *
   * Es un total por carrera, no por sede —ver la nota de clase arriba—, asi
   * que una carrera con varias sedes reporta el mismo total en cada una de
   * sus filas de `estudiantesPorCarrera`.
   */
  private readonly estudiantesPorCarreraId = computed(() => {
    const mapa = new Map<string, number>();
    for (const e of this.datos()?.estudiantesPorCarrera ?? []) {
      mapa.set(e.carreraId, e.totalEstudiantes);
    }
    return mapa;
  });

  protected readonly estudiantesPorCarrera = computed(() => {
    const porId = this.docentesPorId();
    const estudiantesPorId = this.estudiantesPorCarreraId();
    const mapa = new Map<
      string,
      {
        facultad: string;
        carrera: string;
        carreraId: string;
        sede: string;
        ids: Set<string>;
      }
    >();
    for (const s of this.splitFiltrado()) {
      const clave = `${s.facultadCodigo}|${s.carreraId}|${s.sede}`;
      const entrada = mapa.get(clave) ?? {
        facultad: s.facultadNombre,
        carrera: s.carrera,
        carreraId: s.carreraId,
        sede: s.sede || '—',
        ids: new Set<string>(),
      };
      entrada.ids.add(s.docenteId);
      mapa.set(clave, entrada);
    }
    return [...mapa.values()]
      .map((v) => {
        const etc = sumaPorDocenteUnico(v.ids, porId, (d) => etcDe(d));
        const estudiantes = estudiantesPorId.get(v.carreraId) ?? 0;
        return {
          facultad: v.facultad,
          carrera: v.carrera,
          sede: v.sede,
          etc,
          estudiantes,
          ratio: etc > 0 ? estudiantes / etc : 0,
        };
      })
      .sort((a, b) => a.facultad.localeCompare(b.facultad) || a.carrera.localeCompare(b.carrera));
  });

  protected ratioPillDe(r: number): NivelSemaforo {
    return ratioPill(r);
  }

  // =====================================================================
  // Pestana 7: Organizacion
  // =====================================================================

  protected readonly tcDocentes = computed(() =>
    this.docentesFiltrados().filter((d) => claveDedicacion(d.dedicacion) === 'TC'),
  );

  protected readonly tcIncompletos = computed(
    () => this.tcDocentes().filter((d) => d.tot < 40 - 0.01).length,
  );

  protected readonly tcPocaClase = computed(() => this.tcDocentes().filter((d) => d.da < 3).length);
  protected readonly tcSinClase = computed(() => this.tcDocentes().filter((d) => d.da === 0).length);

  protected readonly docentesCuatroFunciones = computed(
    () => this.docentesFiltrados().filter((d) => cantidadDeFunciones(d) === 4).length,
  );
  protected readonly docentesTresFunciones = computed(
    () => this.docentesFiltrados().filter((d) => cantidadDeFunciones(d) === 3).length,
  );

  protected readonly porcentajeInvestigacion = computed(() => {
    const a = this.agregadoDaGlobal();
    return a.tot ? a.i / a.tot : 0;
  });

  protected ipillDe(r: number): NivelSemaforo {
    return ipill(r);
  }
  protected tcPillDe(r: number): NivelSemaforo {
    return tcPill(r);
  }

  protected readonly plantaPorFacultad = computed(() => {
    const grupos = agruparPorFacultad(this.docentesFiltrados());
    const filas = [...grupos.entries()].map(([codigo, { nombre, items }]) => ({
      codigo,
      nombre,
      planta: plantaDe(items),
    }));
    filas.sort((a, b) => b.planta.docentes - a.planta.docentes);
    const total = plantaDe(this.docentesFiltrados());
    return { filas, total };
  });

  protected faltanPara(razon: number, n: number, tc: number): number {
    return tcQueFaltanPara(razon, n, tc);
  }
}
