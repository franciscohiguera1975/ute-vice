/**
 * Formulas y agregaciones puras del Tablero Docente.
 *
 * Replican, sin reinterpretarlas, las reglas del prototipo HTML que origino
 * esta pantalla (`docs/dashboard_ejecutivo/Tablero docente UTE.html`). Son
 * funciones puras a proposito: no dependen de Angular ni de la red, para que
 * se puedan probar sueltas (ver `tablero-docente.calculos.spec.ts`) y para que
 * el componente pueda recalcular todo en el cliente cuando cambia un filtro,
 * sin pedirle nada nuevo al backend.
 */

import type { DocenteResumen, FilaSplitCarrera } from '@domain/modelos';

// ---------------------------------------------------------------------------
// Dedicacion y titularidad
// ---------------------------------------------------------------------------

/** Las cuatro dedicaciones que maneja el tablero. `NA` es «sin dedicacion». */
export type Dedicacion = 'TC' | 'MT' | 'TP' | 'NA';

export const DEDICACIONES_FILTRABLES: readonly Dedicacion[] = ['TC', 'MT', 'TP'];

export const ETIQUETAS_DEDICACION: Readonly<Record<Dedicacion, string>> = {
  TC: 'Tiempo completo',
  MT: 'Medio tiempo',
  TP: 'Tiempo parcial',
  NA: 'Sin dedicación',
};

/**
 * Normaliza el texto del catalogo (`TIEMPO COMPLETO`, `MEDIO TIEMPO`...) a
 * una de las cuatro claves que usan las formulas. El backend entrega el
 * texto tal cual esta en `cat_dedicaciones`; esta es la unica frontera donde
 * se traduce.
 */
export function claveDedicacion(nombreCatalogo: string): Dedicacion {
  const n = (nombreCatalogo || '').toUpperCase();
  if (n.startsWith('TIEMPO COMPLETO')) return 'TC';
  if (n.startsWith('MEDIO TIEMPO')) return 'MT';
  if (n.startsWith('TIEMPO PARCIAL')) return 'TP';
  return 'NA';
}

/** `titularidad` empieza con «TITULAR» — así, literal, mayúsculas incluidas. */
export function esTitular(titularidad: string): boolean {
  return /^TITULAR/.test((titularidad || '').toUpperCase());
}

// ---------------------------------------------------------------------------
// Topes del Reglamento
// ---------------------------------------------------------------------------

export function topeDa(dedicacion: Dedicacion, titular: boolean): number {
  switch (dedicacion) {
    case 'TC':
      return titular ? 20 : 22;
    case 'MT':
      return 12;
    case 'TP':
      return 11;
    default:
      return 0;
  }
}

export function topeH(dedicacion: Dedicacion): number {
  switch (dedicacion) {
    case 'TC':
      return 40;
    case 'MT':
      return 20;
    case 'TP':
      return 19.99;
    default:
      return 40;
  }
}

// ---------------------------------------------------------------------------
// Alertas por docente
// ---------------------------------------------------------------------------

export type NivelSemaforo = 'ok' | 'warn' | 'bad';

export interface Alerta {
  readonly nivel: NivelSemaforo;
  readonly texto: string;
}

/** Las cinco alertas del docente, literales del prototipo. */
export function alertasDocente(d: DocenteResumen): readonly Alerta[] {
  const ded = claveDedicacion(d.dedicacion);
  const titular = esTitular(d.titularidad);
  const tDa = topeDa(ded, titular);
  const tH = topeH(ded);
  const alertas: Alerta[] = [];

  if (ded !== 'NA' && d.tot > tH + 0.01) {
    alertas.push({
      nivel: 'bad',
      texto: ded === 'TP' ? 'TP con 20 h o más' : `Supera ${tH} h`,
    });
  }
  if (d.da > tDa + 0.01) {
    alertas.push({ nivel: 'bad', texto: `Da sobre el tope (${tDa} h)` });
  }
  if ((ded === 'TC' || ded === 'MT') && d.da === 0 && !d.esTecnicoDocente) {
    alertas.push({ nivel: 'warn', texto: 'Sin horas de clase' });
  }
  if (ded === 'TP' && d.da === 0 && !d.esTecnicoDocente) {
    alertas.push({ nivel: 'warn', texto: 'TP sin clases' });
  }
  if (ded === 'TC' && d.tot < 40 - 0.01) {
    alertas.push({ nivel: 'warn', texto: `TC con ${d.tot.toFixed(1)} h` });
  }
  return alertas;
}

// ---------------------------------------------------------------------------
// ETC (equivalente a tiempo completo, CACES)
// ---------------------------------------------------------------------------

export function etcDe(d: { readonly dedicacion: string; readonly tot: number }): number {
  const ded = claveDedicacion(d.dedicacion);
  if (ded === 'TC') return 1;
  if (ded === 'MT') return 0.5;
  return Math.min(d.tot, 40) / 40;
}

// ---------------------------------------------------------------------------
// Semaforos
// ---------------------------------------------------------------------------

/** Razon sobre el tope de Da. */
export function pill3(r: number): NivelSemaforo {
  if (!isFinite(r)) return 'bad';
  if (r > 1.001) return 'bad';
  if (r >= 0.8) return 'ok';
  if (r >= 0.5) return 'warn';
  return 'bad';
}

/** % de horas de gestion sobre el total. Maximo 25 %. */
export function gpill(r: number): NivelSemaforo {
  if (!isFinite(r)) return 'ok';
  if (r > 0.25) return 'bad';
  if (r > 0.18) return 'warn';
  return 'ok';
}

/** % de horas de investigacion sobre el total de la unidad. Referencia 6 %. */
export function ipill(r: number): NivelSemaforo {
  if (!isFinite(r)) return 'bad';
  if (r >= 0.06) return 'ok';
  if (r >= 0.03) return 'warn';
  return 'bad';
}

/** % de docentes TC sobre el total. Art. 109 LOES: 50 % minimo, 60 % optimo. */
export function tcPill(r: number): NivelSemaforo {
  if (!isFinite(r)) return 'bad';
  if (r >= 0.6) return 'ok';
  if (r >= 0.5) return 'warn';
  return 'bad';
}

/** Estudiantes por ETC. Umbrales de trabajo, no normativos. */
export function ratioPill(r: number): NivelSemaforo {
  if (!isFinite(r)) return 'ok';
  if (r < 15) return 'warn';
  if (r > 30) return 'bad';
  return 'ok';
}

// ---------------------------------------------------------------------------
// Filtros globales
// ---------------------------------------------------------------------------

export interface FiltrosTablero {
  readonly facultadCodigo: string | null;
  readonly nivel: string | null;
  readonly dedicacion: Dedicacion | null;
  readonly titularidad: 'titular' | 'no_titular' | null;
  /** Por defecto los tecnicos docentes se excluyen de casi todos los calculos. */
  readonly incluirTecnicos: boolean;
  /** Un docente con cargo directivo no compite por horas como el resto. */
  readonly excluirDirectivos: boolean;
}

export const FILTROS_VACIOS: FiltrosTablero = {
  facultadCodigo: null,
  nivel: null,
  dedicacion: null,
  titularidad: null,
  incluirTecnicos: false,
  excluirDirectivos: false,
};

/**
 * El filtro que no depende de la dimension (facultad/nivel/dedicacion): solo
 * valida, tecnico docente, directivo y titularidad. Es el mismo para ver al
 * docente como unidad o como fila de `split`: en `split`, el docente dueno de
 * la fila tiene que pasarlo igual aunque esa fila puntual sea de otra
 * facultad. `esDirectivo` se mira aqui y no en la fila de `split` por la
 * misma razon que `esTecnicoDocente`: es un atributo del docente completo, no
 * de una carrera puntual suya.
 */
function pasaFiltroBase(
  d: Pick<DocenteResumen, 'esValido' | 'esTecnicoDocente' | 'esDirectivo' | 'titularidad'>,
  f: FiltrosTablero,
): boolean {
  if (!d.esValido) return false;
  if (!f.incluirTecnicos && d.esTecnicoDocente) return false;
  if (f.excluirDirectivos && d.esDirectivo) return false;
  if (f.titularidad) {
    const titular = esTitular(d.titularidad);
    if ((f.titularidad === 'titular') !== titular) return false;
  }
  return true;
}

/**
 * Si el docente entra en el tablero, visto como unidad entera.
 *
 * Facultad, nivel y dedicacion se comparan contra sus atributos
 * «principales» —la fila de mas horas, o la lista de niveles donde dicta—:
 * es el mismo criterio que usan las pestanas Variacion, Mas horas, Tiempos
 * parciales y Organizacion.
 */
export function cumpleFiltroDocente(d: DocenteResumen, f: FiltrosTablero): boolean {
  if (!pasaFiltroBase(d, f)) return false;
  if (f.facultadCodigo && d.facultadCodigo !== f.facultadCodigo) return false;
  if (f.nivel && !d.niveles.includes(f.nivel)) return false;
  if (f.dedicacion && claveDedicacion(d.dedicacion) !== f.dedicacion) return false;
  return true;
}

/**
 * Si una fila de `split` entra en el tablero.
 *
 * Valida, tecnico docente y titularidad se miran en el docente dueno de la
 * fila; facultad, nivel y dedicacion se miran en la fila misma, porque es ahi
 * donde de verdad varian —es el desglose por carrera—.
 */
export function cumpleFiltroSplit(
  s: FilaSplitCarrera,
  docente: DocenteResumen | undefined,
  f: FiltrosTablero,
): boolean {
  if (!docente || !pasaFiltroBase(docente, f)) return false;
  if (f.facultadCodigo && s.facultadCodigo !== f.facultadCodigo) return false;
  if (f.nivel && s.nivel !== f.nivel) return false;
  if (f.dedicacion && claveDedicacion(s.dedicacion) !== f.dedicacion) return false;
  return true;
}

// ---------------------------------------------------------------------------
// Agregacion de filas de split (Da, Gestion, composicion de carga)
// ---------------------------------------------------------------------------

export interface AgregadoCarga {
  readonly docentes: number;
  readonly da: number;
  readonly d: number;
  readonly i: number;
  readonly v: number;
  readonly g: number;
  readonly tot: number;
  /** Suma del tope de Da de cada docente unico presente en el agregado. */
  readonly topeDaTotal: number;
  /** Da/total/gestion acumulados por docente, para promedios «por persona». */
  readonly porDocente: ReadonlyMap<string, { readonly da: number; readonly tot: number; readonly g: number }>;
}

export const AGREGADO_VACIO: AgregadoCarga = {
  docentes: 0,
  da: 0,
  d: 0,
  i: 0,
  v: 0,
  g: 0,
  tot: 0,
  topeDaTotal: 0,
  porDocente: new Map(),
};

/**
 * Suma horas de un conjunto de filas de `split`, con el tope de Da agregado
 * de los docentes que aparecen en ellas.
 *
 * `docentesPorId` tiene que traer el docente completo —no solo el de la fila—
 * porque el tope depende de la dedicacion y la titularidad «principales», que
 * viven en `DocenteResumen` y no en cada fila de `split`.
 */
export function agregarSplit(
  filas: readonly FilaSplitCarrera[],
  docentesPorId: ReadonlyMap<string, DocenteResumen>,
): AgregadoCarga {
  const ids = new Set<string>();
  let da = 0;
  let d = 0;
  let i = 0;
  let v = 0;
  let g = 0;
  let tot = 0;
  const porDocente = new Map<string, { da: number; tot: number; g: number }>();

  for (const s of filas) {
    ids.add(s.docenteId);
    da += s.da;
    d += s.d;
    i += s.i;
    v += s.v;
    g += s.g;
    tot += s.tot;
    const previo = porDocente.get(s.docenteId) ?? { da: 0, tot: 0, g: 0 };
    porDocente.set(s.docenteId, {
      da: previo.da + s.da,
      tot: previo.tot + s.tot,
      g: previo.g + s.g,
    });
  }

  let topeDaTotal = 0;
  for (const id of ids) {
    const docente = docentesPorId.get(id);
    if (!docente) continue;
    topeDaTotal += topeDa(claveDedicacion(docente.dedicacion), esTitular(docente.titularidad));
  }

  return { docentes: ids.size, da, d, i, v, g, tot, topeDaTotal, porDocente };
}

/**
 * Suma un valor del docente completo —ETC, tope de Da...— una sola vez por
 * cada id unico de una coleccion, aunque ese id aparezca repetido —por
 * ejemplo, en varias filas de `split` de la misma carrera—.
 */
export function sumaPorDocenteUnico(
  ids: Iterable<string>,
  docentesPorId: ReadonlyMap<string, DocenteResumen>,
  valor: (d: DocenteResumen) => number,
): number {
  let total = 0;
  for (const id of new Set(ids)) {
    const docente = docentesPorId.get(id);
    if (docente) total += valor(docente);
  }
  return total;
}

/** Agrupa una lista (docentes o filas de `split`) por su facultad. */
export function agruparPorFacultad<
  T extends { readonly facultadCodigo: string; readonly facultadNombre: string },
>(lista: readonly T[]): ReadonlyMap<string, { readonly nombre: string; readonly items: readonly T[] }> {
  const mapa = new Map<string, { nombre: string; items: T[] }>();
  for (const item of lista) {
    const entrada = mapa.get(item.facultadCodigo) ?? { nombre: item.facultadNombre, items: [] };
    entrada.items.push(item);
    mapa.set(item.facultadCodigo, entrada);
  }
  return mapa;
}

// ---------------------------------------------------------------------------
// Variacion de periodo
// ---------------------------------------------------------------------------

export interface MovimientoFacultad {
  readonly codigo: string;
  readonly nombre: string;
  readonly anterior: number;
  readonly actual: number;
  readonly entran: number;
  readonly salen: number;
}

/**
 * Docentes por facultad en los dos grupos, con quien entra y quien sale.
 *
 * Cada docente cuenta una vez, en su facultad principal —la de mas horas,
 * `DocenteResumen.facultadCodigo`—, igual en el grupo actual que en el
 * anterior.
 */
export function movimientoPorFacultad(
  actual: readonly DocenteResumen[],
  anterior: readonly DocenteResumen[],
): readonly MovimientoFacultad[] {
  const mapa = new Map<
    string,
    { nombre: string; actualIds: Set<string>; anteriorIds: Set<string> }
  >();

  const registra = (lista: readonly DocenteResumen[], clave: 'actualIds' | 'anteriorIds') => {
    for (const d of lista) {
      const entrada = mapa.get(d.facultadCodigo) ?? {
        nombre: d.facultadNombre,
        actualIds: new Set<string>(),
        anteriorIds: new Set<string>(),
      };
      entrada[clave].add(d.docenteId);
      mapa.set(d.facultadCodigo, entrada);
    }
  };
  registra(actual, 'actualIds');
  registra(anterior, 'anteriorIds');

  return [...mapa.entries()]
    .map(([codigo, v]) => ({
      codigo,
      nombre: v.nombre,
      anterior: v.anteriorIds.size,
      actual: v.actualIds.size,
      entran: [...v.actualIds].filter((id) => !v.anteriorIds.has(id)).length,
      salen: [...v.anteriorIds].filter((id) => !v.actualIds.has(id)).length,
    }))
    .sort((a, b) => b.actual - a.actual);
}

export interface MovimientoDePersonas {
  readonly entran: readonly DocenteResumen[];
  readonly salen: readonly DocenteResumen[];
}

/** Quien entra y quien sale entre los dos grupos, por id de docente. */
export function movimientoDePersonas(
  actual: readonly DocenteResumen[],
  anterior: readonly DocenteResumen[],
): MovimientoDePersonas {
  const idsActual = new Set(actual.map((d) => d.docenteId));
  const idsAnterior = new Set(anterior.map((d) => d.docenteId));
  return {
    entran: actual.filter((d) => !idsAnterior.has(d.docenteId)),
    salen: anterior.filter((d) => !idsActual.has(d.docenteId)),
  };
}

export function porcentajeTC(lista: readonly DocenteResumen[]): number {
  if (lista.length === 0) return 0;
  const tc = lista.filter((d) => claveDedicacion(d.dedicacion) === 'TC').length;
  return tc / lista.length;
}

// ---------------------------------------------------------------------------
// Tiempos parciales: histograma de Da
// ---------------------------------------------------------------------------

export interface BinTP {
  readonly etiqueta: string;
  readonly prueba: (da: number) => boolean;
}

/** Limites inclusivos por el lado superior, literales del prototipo. */
export const BINS_TP: readonly BinTP[] = [
  { etiqueta: '0 h', prueba: (da) => da === 0 },
  { etiqueta: '0,1–3 h', prueba: (da) => da > 0 && da <= 3 },
  { etiqueta: '3,1–6 h', prueba: (da) => da > 3 && da <= 6 },
  { etiqueta: '6,1–9 h', prueba: (da) => da > 6 && da <= 9 },
  { etiqueta: '9,1–11 h', prueba: (da) => da > 9 && da <= 11 },
  { etiqueta: 'Más de 11 h', prueba: (da) => da > 11 },
];

export function mediana(valores: readonly number[]): number {
  if (valores.length === 0) return 0;
  const s = [...valores].sort((a, b) => a - b);
  const n = s.length;
  return n % 2 === 1 ? s[(n - 1) / 2] : (s[n / 2 - 1] + s[n / 2]) / 2;
}

export function promedio(valores: readonly number[]): number {
  if (valores.length === 0) return 0;
  return valores.reduce((suma, v) => suma + v, 0) / valores.length;
}

// ---------------------------------------------------------------------------
// Organizacion: planta a tiempo completo
// ---------------------------------------------------------------------------

export interface PlantaDocente {
  readonly docentes: number;
  readonly tc: number;
  readonly mt: number;
  readonly tp: number;
  readonly etc: number;
}

export function plantaDe(lista: readonly DocenteResumen[]): PlantaDocente {
  let tc = 0;
  let mt = 0;
  let etc = 0;
  for (const d of lista) {
    const ded = claveDedicacion(d.dedicacion);
    if (ded === 'TC') tc++;
    else if (ded === 'MT') mt++;
    etc += etcDe(d);
  }
  return { docentes: lista.length, tc, mt, tp: lista.length - tc - mt, etc };
}

/**
 * Cuantos TC (o MT/TP convertidos) faltan para que la planta llegue a la
 * razon pedida, sin cambiar el total de docentes.
 *
 * `Math.max(0, ...)`: una facultad que ya cumple no "sobra" TC negativos.
 */
export function tcQueFaltanPara(razon: number, totalDocentes: number, tc: number): number {
  return Math.max(0, Math.ceil(razon * totalDocentes - tc - 1e-9));
}

/** Cuantas de las cuatro funciones (D, I, V, G) tienen horas > 0. */
export function cantidadDeFunciones(d: DocenteResumen): number {
  return [d.d, d.i, d.v, d.g].filter((h) => h > 0).length;
}
