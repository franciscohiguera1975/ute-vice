import { DatePipe, DecimalPipe, NgTemplateOutlet } from '@angular/common';
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
  type AgregadoCarga,
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
  pill3,
  plantaDe,
  plantaDeSplit,
  type PlantaDocente,
  porcentajeTC,
  promedio,
  ratioPill,
  sumaPorDocenteUnico,
  tcPill,
  tcQueFaltanPara,
  topeH,
  variacionPorFacultadYDedicacion,
  variacionPorNivel,
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
  imports: [
    DecimalPipe,
    DatePipe,
    NgTemplateOutlet,
    CargandoComponent,
    VacioComponent,
    SelectorGruposComponent,
  ],
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

  // ------------------------------------------------------- drill-down ---
  /** Que fila "clicable" esta desplegada ahora mismo, en toda la pantalla.
   * Una clave unica por fila (p.ej. `'da-facultad:' + codigo`); null si
   * ninguna lo esta. Solo una a la vez, igual que un acordeon. */
  protected readonly segmentoAbierto = signal<string | null>(null);

  protected alternarSegmento(clave: string): void {
    this.segmentoAbierto.update((actual) => (actual === clave ? null : clave));
  }

  /**
   * Segundo nivel del drill-down de tres niveles de Gestión (facultad →
   * carreras → docentes) e Investigación (mismo patrón). `segmentoAbierto` ya
   * ocupa el primer nivel —la fila de facultad—, así que una carrera abierta
   * dentro de esa facultad necesita su propio espacio de claves; la clave
   * incluye el código de facultad para que cada una tenga el suyo.
   */
  protected readonly carreraDrillAbierta = signal<string | null>(null);

  protected alternarCarreraDrill(clave: string): void {
    this.carreraDrillAbierta.update((actual) => (actual === clave ? null : clave));
  }

  /**
   * Los docentes de un conjunto de filas de `split`, con sus horas dentro de
   * ESE segmento —no su total del periodo completo—: asi el drill-down de
   * una carrera muestra cuanto dicta cada docente en esa carrera, no en
   * todas.
   */
  protected docentesDelSegmento(filas: readonly FilaSplitCarrera[]): Array<{
    readonly docente: DocenteResumen;
    readonly da: number;
    readonly d: number;
    readonly i: number;
    readonly v: number;
    readonly g: number;
    readonly tot: number;
  }> {
    const porId = this.docentesPorId();
    const agregado = agregarSplit(filas, porId);
    return [...agregado.porDocente.entries()]
      .map(([id, valores]) => ({ docente: porId.get(id)!, ...valores }))
      .filter((x) => x.docente)
      .sort((a, b) => b.tot - a.tot);
  }

  /**
   * Igual forma que `docentesDelSegmento`, pero para listas que ya son de
   * `DocenteResumen` completos —los TP por facultad y las cuatro tarjetas
   * KPI de Tiempos parciales—: aqui no hace falta pasar por `split` porque
   * el docente ya trae sus horas totales del periodo. Permite reusar la
   * misma tabla anidada de drill-down para ambos casos.
   */
  protected segmentoDeDocentes(lista: readonly DocenteResumen[]): Array<{
    readonly docente: DocenteResumen;
    readonly da: number;
    readonly d: number;
    readonly i: number;
    readonly v: number;
    readonly g: number;
    readonly tot: number;
  }> {
    return [...lista]
      .map((docente) => ({
        docente,
        da: docente.da,
        d: docente.d,
        i: docente.i,
        v: docente.v,
        g: docente.g,
        tot: docente.tot,
      }))
      .sort((a, b) => b.tot - a.tot);
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

  protected readonly variacionFacultades = computed(() =>
    variacionPorFacultadYDedicacion(this.docentesFiltrados(), this.docentesAnteriorFiltrados()),
  );

  /** El mayor total (anterior o actual) de todas las facultades, para escalar
   * la barra comparativa de cada fila —nunca 0, para no dividir por cero. */
  protected readonly maxVariacionFacultad = computed(() =>
    Math.max(1, ...this.variacionFacultades().flatMap((f) => [f.totalAnterior, f.totalActual])),
  );

  protected readonly variacionNiveles = computed(() =>
    variacionPorNivel(this.nivelesDisponibles(), this.docentesFiltrados(), this.docentesAnteriorFiltrados()),
  );

  /** `actual − anterior`, para colorear y escribir el signo del cambio. */
  protected delta(anterior: number, actual: number): number {
    return actual - anterior;
  }

  protected signoDelta(valor: number): '+' | '' {
    return valor > 0 ? '+' : '';
  }

  /**
   * Quien ingresa y quien sale de una facultad entre los dos periodos.
   *
   * «Ingresan»: docentes del grupo actual de esa facultad que no estaban en
   * el grupo anterior de esa misma facultad. «Salen»: al reves. Para cada uno
   * que sale, `situacion` dice si sigue en la institucion —en otra
   * facultad— o si de verdad se fue: se mira en `docentesPorId()`, que trae
   * a TODOS los docentes del grupo actual, sin los filtros globales ni el
   * de facultad, porque la pregunta es si existe en absoluto, no si pasa los
   * filtros de la pantalla.
   */
  protected ingresanYSalenDe(codigoFacultad: string): {
    readonly ingresan: readonly DocenteResumen[];
    readonly salen: ReadonlyArray<{
      readonly docente: DocenteResumen;
      /** El mismo docente en el periodo actual, si sigue existiendo —de ser
       * asi, su nombre es clicable y abre SU ficha, la del periodo actual,
       * no la del anterior—. */
      readonly sigue: DocenteResumen | null;
      readonly situacion: string;
    }>;
  } {
    const actualDeFacultad = this.docentesFiltrados().filter((d) => d.facultadCodigo === codigoFacultad);
    const anteriorDeFacultad = this.docentesAnteriorFiltrados().filter(
      (d) => d.facultadCodigo === codigoFacultad,
    );
    const idsActual = new Set(actualDeFacultad.map((d) => d.docenteId));
    const idsAnterior = new Set(anteriorDeFacultad.map((d) => d.docenteId));
    const porIdActualCompleto = this.docentesPorId();

    const ingresan = [...actualDeFacultad]
      .filter((d) => !idsAnterior.has(d.docenteId))
      .sort((a, b) => a.nombreCompleto.localeCompare(b.nombreCompleto));

    const salen = [...anteriorDeFacultad]
      .filter((d) => !idsActual.has(d.docenteId))
      .map((docente) => {
        const sigue = porIdActualCompleto.get(docente.docenteId) ?? null;
        return {
          docente,
          sigue,
          situacion: sigue
            ? `Sigue en ${sigue.facultadNombre || sigue.facultadCodigo}`
            : 'No está en el periodo actual',
        };
      })
      .sort((a, b) => a.docente.nombreCompleto.localeCompare(b.docente.nombreCompleto));

    return { ingresan, salen };
  }

  // =====================================================================
  // Pestana 2: Docencia directa (Da)
  // =====================================================================

  protected readonly agregadoDaGlobal = computed(() =>
    agregarSplit(this.splitFiltrado(), this.docentesPorId()),
  );

  protected readonly agregadoDaPorDedicacion = computed(() => {
    const porId = this.docentesPorId();
    const filas = this.splitFiltrado();
    return DEDICACIONES_FILTRABLES.map((ded) => {
      const filasDed = filas.filter((s) => claveDedicacion(s.dedicacion) === ded);
      return { dedicacion: ded, filas: filasDed, agregado: agregarSplit(filasDed, porId) };
    });
  });

  /**
   * «Docencia directa por facultad», desglosada por dedicación (TC/MT/TP) —
   * más una columna «Todas» con el agregado de la facultad entera, dedicación
   * incluida NA—. Cada combinación facultad+dedicación trae sus propias
   * `filas` de `split`, para el drill-down por celda (clic en una celda de
   * dedicación, no en la fila entera).
   */
  protected readonly daPorFacultadYDedicacion = computed(() => {
    const porId = this.docentesPorId();
    const grupos = agruparPorFacultad(this.splitFiltrado());
    return [...grupos.entries()]
      .map(([codigo, { nombre, items }]) => ({
        codigo,
        nombre,
        porDedicacion: DEDICACIONES_FILTRABLES.map((ded) => {
          const filas = items.filter((s) => claveDedicacion(s.dedicacion) === ded);
          return { dedicacion: ded, filas, agregado: agregarSplit(filas, porId) };
        }),
        total: agregarSplit(items, porId),
      }))
      .sort((a, b) => b.total.tot - a.total.tot);
  });

  /**
   * «Por nivel»: mismo indicador de Da desglosado por dedicación, pero por
   * nivel en vez de por facultad —usa `nivelesDisponibles()`, el catálogo
   * real, en vez de una lista fija de niveles—.
   */
  protected readonly daPorNivel = computed(() => {
    const porId = this.docentesPorId();
    const filas = this.splitFiltrado();
    return this.nivelesDisponibles().map((nivel) => {
      const filasNivel = filas.filter((s) => s.nivel === nivel);
      return {
        nivel,
        porDedicacion: DEDICACIONES_FILTRABLES.map((ded) => ({
          dedicacion: ded,
          agregado: agregarSplit(
            filasNivel.filter((s) => claveDedicacion(s.dedicacion) === ded),
            porId,
          ),
        })),
        total: agregarSplit(filasNivel, porId),
      };
    });
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
      .map((v) => ({
        facultad: v.facultad,
        carrera: v.carrera,
        filas: v.filas,
        agregado: agregarSplit(v.filas, porId),
      }))
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
        return { codigo, nombre, filas: items, agregado, conG };
      })
      .sort((a, b) => b.agregado.g / (b.agregado.tot || 1) - a.agregado.g / (a.agregado.tot || 1));
  });

  protected gpillDe(r: number): NivelSemaforo {
    return gpill(r);
  }

  /**
   * Agrupa `splitFiltrado()` de una facultad por carrera, con el agregado de
   * cada una y cuantos docentes de esa carrera tienen horas en `campo` —
   * mismo patron de agrupacion que `daPorCarrera`, pero acotado a una sola
   * facultad—. Comparte el calculo entre el drill-down de carreras de
   * Gestion y el de Investigacion (punto 2 y punto 6 del encargo): ambos
   * agrupan igual, solo cambia que columna de horas miran.
   */
  private carrerasConCampoDe(
    codigoFacultad: string,
    campo: 'g' | 'i',
  ): ReadonlyArray<{
    readonly carrera: string;
    readonly filas: readonly FilaSplitCarrera[];
    readonly agregado: AgregadoCarga;
    readonly conCampo: number;
  }> {
    const porId = this.docentesPorId();
    const mapa = new Map<string, FilaSplitCarrera[]>();
    for (const s of this.splitFiltrado()) {
      if (s.facultadCodigo !== codigoFacultad) continue;
      const filas = mapa.get(s.carrera) ?? [];
      filas.push(s);
      mapa.set(s.carrera, filas);
    }
    return [...mapa.entries()]
      .map(([carrera, filas]) => {
        const agregado = agregarSplit(filas, porId);
        const conCampo = [...agregado.porDocente.values()].filter((p) => p[campo] > 0).length;
        return { carrera, filas, agregado, conCampo };
      })
      .filter((x) => x.agregado.tot > 0);
  }

  /** Las carreras de una facultad con gestion, ordenadas de mayor a menor %G
   * —tercer nivel del drill-down de Gestion: facultad → carreras → docentes—. */
  protected carrerasConGestionDe(codigoFacultad: string): ReadonlyArray<{
    readonly carrera: string;
    readonly filas: readonly FilaSplitCarrera[];
    readonly agregado: AgregadoCarga;
    readonly conG: number;
  }> {
    return this.carrerasConCampoDe(codigoFacultad, 'g')
      .map((x) => ({ carrera: x.carrera, filas: x.filas, agregado: x.agregado, conG: x.conCampo }))
      .sort((a, b) => b.agregado.g / (b.agregado.tot || 1) - a.agregado.g / (a.agregado.tot || 1));
  }

  /**
   * Los docentes con gestion de una carrera (o de investigacion, segun
   * `campo`), ordenados por su horas de `campo` en esa carrera —no por su
   * total, a diferencia de `docentesDelSegmento`—, igual que el prototipo
   * original ordena por G o por I, no por horas totales.
   */
  private docentesConCampoDe(
    filas: readonly FilaSplitCarrera[],
    campo: 'g' | 'i',
  ): ReturnType<TableroDocenteComponent['docentesDelSegmento']> {
    return [...this.docentesDelSegmento(filas.filter((s) => s[campo] > 0))].sort(
      (a, b) => b[campo] - a[campo],
    );
  }

  protected docentesConGestionDe(
    filas: readonly FilaSplitCarrera[],
  ): ReturnType<TableroDocenteComponent['docentesDelSegmento']> {
    return this.docentesConCampoDe(filas, 'g');
  }

  // =====================================================================
  // Pestana 4: Mas horas
  // =====================================================================

  /**
   * Excluye a los directivos siempre, sin importar si «Excluir directivos»
   * esta marcado —igual que el original, que arma esta lista con
   * `base.filter(d=>!d.dir.length)` sin que ninguna casilla lo condicione—:
   * un docente con cargo directivo no compite por «quien tiene mas horas»
   * como el resto. En el resto de las pestañas la exclusion si es opcional,
   * porque el catalogo de cargos directivos es dinamico y no siempre esta
   * cargado; aqui se mantiene fija porque asi la define el prototipo.
   */
  protected readonly masHoras = computed(() => {
    const columna = this.ordenTop();
    return [...this.docentesFiltrados()]
      .filter((d) => !d.esDirectivo)
      .sort((a, b) => b[columna] - a[columna] || b.tot - a.tot);
  });

  protected excedeTope(d: DocenteResumen): boolean {
    const ded = claveDedicacion(d.dedicacion);
    return ded !== 'NA' && d.tot > topeH(ded) + 0.01;
  }

  /**
   * Cuantos directivos quedan fuera de `masHoras()` con los filtros actuales
   * (facultad/nivel/dedicacion/titularidad/tecnicos) — para la nota del KPI
   * «Docentes sin cargo directivo». Se cuenta con `excluirDirectivos: false`
   * para no restar dos veces si esa casilla tambien esta marcada.
   */
  protected readonly directivosEnFiltroTop = computed(() => {
    const f: FiltrosTablero = { ...this.filtros(), excluirDirectivos: false };
    return (this.datos()?.docentes ?? []).filter((d) => cumpleFiltroDocente(d, f) && d.esDirectivo).length;
  });

  /** Cuantos de `masHoras()` superan el tope de horas de su dedicacion. */
  protected readonly masHorasSuperanTope = computed(
    () => this.masHoras().filter((d) => this.excedeTope(d)).length,
  );

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
      docentes: items,
      cantidad: items.length,
      promedio: promedio(items.map((d) => d.da)),
      mediana: mediana(items.map((d) => d.da)),
      bins: BINS_TP.map((b) => items.filter((d) => b.prueba(d.da)).length),
    }));
    filas.push({
      codigo: '__total',
      nombre: 'Total',
      docentes: todos,
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
        filas: FilaSplitCarrera[];
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
        filas: [],
      };
      entrada.ids.add(s.docenteId);
      entrada.filas.push(s);
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
          filas: v.filas,
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

  /**
   * Las carreras de una facultad, con su propia planta a tiempo completo —el
   * drill-down de «Planta a tiempo completo» (facultad → sus carreras). No
   * hay un `DocenteResumen` por carrera, asi que se agrupa directamente
   * sobre `splitFiltrado()` y se usa `plantaDeSplit`, igual que ya agrupa
   * por carrera `daPorCarrera`.
   */
  protected carrerasDe(
    codigoFacultad: string,
  ): ReadonlyArray<{ readonly carrera: string; readonly planta: PlantaDocente }> {
    const mapa = new Map<string, FilaSplitCarrera[]>();
    for (const s of this.splitFiltrado()) {
      if (s.facultadCodigo !== codigoFacultad) continue;
      const filas = mapa.get(s.carrera) ?? [];
      filas.push(s);
      mapa.set(s.carrera, filas);
    }
    return [...mapa.entries()]
      .map(([carrera, filas]) => ({ carrera, planta: plantaDeSplit(filas) }))
      .sort((a, b) => b.planta.docentes - a.planta.docentes);
  }

  /**
   * «Tiempos completos: carga incompleta y pocas clases», por facultad.
   *
   * `directivos` cuenta, de la union de TC con carga incompleta y TC con
   * pocas clases, cuantos tienen cargo directivo —`DocenteResumen.esDirectivo`
   * ya trae ese dato, puesto en la ficha de detalle—, asi que no hace falta
   * ningun calculo nuevo ni dejar la columna en 0.
   */
  protected readonly tcPorFacultad = computed(() => {
    const grupos = agruparPorFacultad(this.tcDocentes());
    return [...grupos.entries()]
      .map(([codigo, { nombre, items }]) => {
        const incompletos = items.filter((d) => d.tot < 40 - 0.01);
        const pocaClase = items.filter((d) => d.da < 3);
        const sinClase = items.filter((d) => d.da === 0);
        const horasFaltantes = incompletos.reduce((suma, d) => suma + (40 - d.tot), 0);
        const idsBajos = new Set([...incompletos, ...pocaClase].map((d) => d.docenteId));
        const directivos = items.filter((d) => idsBajos.has(d.docenteId) && d.esDirectivo).length;
        return { codigo, nombre, tc: items.length, incompletos, pocaClase, sinClase, horasFaltantes, directivos };
      })
      .sort((a, b) => b.tc - a.tc);
  });

  /** La fila «Total» de `tcPorFacultad`, sumando todas las facultades —igual
   * que el original agrega una fila `__T` al final de cada tabla «por
   * facultad»—. */
  protected readonly tcPorFacultadTotal = computed(() => {
    const items = this.tcDocentes();
    const incompletos = items.filter((d) => d.tot < 40 - 0.01);
    const pocaClase = items.filter((d) => d.da < 3);
    const sinClase = items.filter((d) => d.da === 0);
    const horasFaltantes = incompletos.reduce((suma, d) => suma + (40 - d.tot), 0);
    const idsBajos = new Set([...incompletos, ...pocaClase].map((d) => d.docenteId));
    const directivos = items.filter((d) => idsBajos.has(d.docenteId) && d.esDirectivo).length;
    return { tc: items.length, incompletos, pocaClase, sinClase, horasFaltantes, directivos };
  });

  /** «Docentes con horas en las cuatro funciones», por facultad. */
  protected readonly funcionesPorFacultad = computed(() => {
    const grupos = agruparPorFacultad(this.docentesFiltrados());
    return [...grupos.entries()]
      .map(([codigo, { nombre, items }]) => {
        const cuatro = items.filter((d) => cantidadDeFunciones(d) === 4);
        const tres = items.filter((d) => cantidadDeFunciones(d) === 3);
        const tcCuatro = cuatro.filter((d) => claveDedicacion(d.dedicacion) === 'TC').length;
        return { codigo, nombre, docentes: items.length, cuatro, tres, tcCuatro };
      })
      .sort((a, b) => b.cuatro.length - a.cuatro.length);
  });

  /** La fila «Total» de `funcionesPorFacultad`. */
  protected readonly funcionesPorFacultadTotal = computed(() => {
    const items = this.docentesFiltrados();
    const cuatro = items.filter((d) => cantidadDeFunciones(d) === 4);
    const tres = items.filter((d) => cantidadDeFunciones(d) === 3);
    const tcCuatro = cuatro.filter((d) => claveDedicacion(d.dedicacion) === 'TC').length;
    return { docentes: items.length, cuatro, tres, tcCuatro };
  });

  /**
   * «Investigación frente al mínimo del 6 %», por facultad.
   *
   * `iProm` es las horas totales de investigación de la facultad entre
   * cuantos docentes tienen alguna —no el promedio de la investigacion
   * propia de cada quien—, igual que el prototipo original. `gap` es la
   * brecha en horas para llegar al 6 % de esa facultad, 0 si ya lo cumple.
   */
  protected readonly investigacionPorFacultad = computed(() => {
    const porId = this.docentesPorId();
    const grupos = agruparPorFacultad(this.splitFiltrado());
    return [...grupos.entries()]
      .map(([codigo, { nombre, items }]) => {
        const agregado = agregarSplit(items, porId);
        const conI = [...agregado.porDocente.entries()].filter(([, p]) => p.i > 0);
        const tcConI = conI.filter(
          ([id]) => claveDedicacion(porId.get(id)?.dedicacion ?? '') === 'TC',
        ).length;
        const gap = Math.max(0, agregado.tot * 0.06 - agregado.i);
        return {
          codigo,
          nombre,
          filas: items,
          agregado,
          conI: conI.length,
          iProm: conI.length ? agregado.i / conI.length : 0,
          tcConI,
          gap,
        };
      })
      .sort((a, b) => b.agregado.i / (b.agregado.tot || 1) - a.agregado.i / (a.agregado.tot || 1));
  });

  /** La fila «Total» de `investigacionPorFacultad`, sobre todo `splitFiltrado()`. */
  protected readonly investigacionTotal = computed(() => {
    const porId = this.docentesPorId();
    const agregado = this.agregadoDaGlobal();
    const conI = [...agregado.porDocente.entries()].filter(([, p]) => p.i > 0);
    const tcConI = conI.filter(
      ([id]) => claveDedicacion(porId.get(id)?.dedicacion ?? '') === 'TC',
    ).length;
    const gap = Math.max(0, agregado.tot * 0.06 - agregado.i);
    return { agregado, conI: conI.length, iProm: conI.length ? agregado.i / conI.length : 0, tcConI, gap };
  });

  /** Las carreras de una facultad con investigacion, ordenadas de mayor a
   * menor %I —mismo patron que `carrerasConGestionDe`, usando `campo: 'i'`—. */
  protected carrerasConInvestigacionDe(codigoFacultad: string): ReadonlyArray<{
    readonly carrera: string;
    readonly filas: readonly FilaSplitCarrera[];
    readonly agregado: AgregadoCarga;
    readonly conI: number;
  }> {
    return this.carrerasConCampoDe(codigoFacultad, 'i')
      .map((x) => ({ carrera: x.carrera, filas: x.filas, agregado: x.agregado, conI: x.conCampo }))
      .sort((a, b) => b.agregado.i / (b.agregado.tot || 1) - a.agregado.i / (a.agregado.tot || 1));
  }

  protected docentesConInvestigacionDe(
    filas: readonly FilaSplitCarrera[],
  ): ReturnType<TableroDocenteComponent['docentesDelSegmento']> {
    return this.docentesConCampoDe(filas, 'i');
  }
}
