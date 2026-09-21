/** Modelos del distributivo docente. Reflejan los del backend. */

import type { Pagina } from './comunes';
import type { Conteo } from './entidades';

// ---------------------------------------------------------------------------
// Catalogos
// ---------------------------------------------------------------------------

/**
 * Los doce catalogos. El valor es el segmento de URL de su API, igual que en el
 * backend: `/api/v1/catalogos/carreras`.
 */
export const TipoCatalogo = {
  PAO: 'paos',
  FACULTAD: 'facultades',
  CARRERA: 'carreras',
  SEDE: 'sedes',
  TITULARIDAD: 'titularidades',
  DEDICACION: 'dedicaciones',
  CATEGORIA: 'categorias',
  NIVEL: 'niveles',
  TITULO_PROFESIONAL: 'titulos-profesionales',
  TIPO_TITULO: 'tipos-titulo',
  GENERO: 'generos',
  ASIGNATURA: 'asignaturas',
} as const;
export type TipoCatalogo = (typeof TipoCatalogo)[keyof typeof TipoCatalogo];

export interface DescriptorCatalogo {
  readonly tipo: TipoCatalogo;
  readonly etiqueta: string;
  readonly singular: string;
}

export interface ElementoCatalogo {
  readonly id: string;
  readonly tipo: TipoCatalogo;
  readonly codigo: string;
  readonly nombre: string;
  readonly descripcion: string;
  readonly activo: boolean;
  readonly orden: number;
  /**
   * Codigo del mismo elemento en el ERP academico.
   *
   * No es unico: `FCSEE` y `PFCSEE` son dos unidades aqui y una sola —`FS`—
   * alla. Sirve para reconciliar, no para identificar.
   */
  readonly codigoErp: string;
  readonly atributos: Record<string, unknown>;
  readonly creadoEn: string;
  readonly actualizadoEn: string;
}

/** Forma minima para poblar un desplegable. */
export interface OpcionSelector {
  readonly id: string;
  readonly codigo: string;
  readonly nombre: string;
}

export interface FiltroCatalogo {
  readonly texto?: string;
  readonly activo?: boolean;
}

export interface DatosElementoCatalogo {
  readonly codigo: string;
  readonly nombre: string;
  readonly descripcion?: string;
  readonly activo?: boolean;
  readonly orden?: number;
  readonly codigoErp?: string;
  readonly atributos?: Record<string, unknown>;
}

export type CambiosElementoCatalogo = Partial<Omit<DatosElementoCatalogo, 'codigo'>>;

// ---------------------------------------------------------------------------
// Docentes
// ---------------------------------------------------------------------------

export interface Docente {
  readonly id: string;
  readonly identificacion: string;
  /** `false` cuando el documento es un pasaporte y no una cedula ecuatoriana. */
  readonly esCedula: boolean;
  readonly nombreCompleto: string;
  readonly generoId: string | null;
  /** Enlace con el expediente academico, cuando existe. */
  readonly personaId: string | null;
  readonly titulosIds: readonly string[];
  readonly activo: boolean;
  readonly observaciones: string | null;
  readonly creadoEn: string;
}

export interface DocenteDetalle {
  readonly docente: Docente;
  readonly titulos: readonly ElementoCatalogo[];
  readonly totalFilas: number;
}

export interface FiltroDocentes {
  readonly texto?: string;
  readonly generoId?: string;
  readonly activo?: boolean;
  readonly soloConPasaporte?: boolean;
}

export interface DatosDocente {
  readonly identificacion: string;
  readonly nombreCompleto: string;
  readonly generoId?: string | null;
  readonly titulosIds?: readonly string[];
  readonly observaciones?: string | null;
}

export type CambiosDocente = Partial<Omit<DatosDocente, 'identificacion'>> & {
  readonly activo?: boolean;
};

// ---------------------------------------------------------------------------
// Distributivo
// ---------------------------------------------------------------------------

/** Horas por subactividad, en cuatro bloques, con sus totales. */
export interface Horas {
  readonly docencia: Record<string, number>;
  readonly gestion: Record<string, number>;
  readonly investigacion: Record<string, number>;
  readonly vinculacion: Record<string, number>;
  readonly totalDocencia: number;
  readonly totalGestion: number;
  readonly totalInvestigacion: number;
  readonly totalVinculacion: number;
  readonly total: number;
}

/** Subactividades de cada bloque, en el orden del consolidado. */
export const CLAVES_HORAS = {
  docencia: 'abcdefghijklmn'.split('').map((c) => `D${c}`),
  gestion: 'abcdefghijklmn'.split('').map((c) => `G${c}`),
  investigacion: 'abcdefghij'.split('').map((c) => `I${c}`),
  vinculacion: 'abcdefghi'.split('').map((c) => `V${c}`),
} as const;

export const ETIQUETAS_BLOQUE: Record<keyof typeof CLAVES_HORAS, string> = {
  docencia: 'Docencia',
  gestion: 'Gestión',
  investigacion: 'Investigación',
  vinculacion: 'Vinculación',
};

export interface FilaDistributivo {
  readonly id: string;
  readonly docenteId: string;
  readonly docenteIdentificacion: string;
  readonly docenteNombre: string;

  readonly paoId: string;
  readonly pao: string;
  readonly facultadId: string;
  readonly facultad: string;
  readonly carreraId: string;
  readonly carrera: string;

  readonly sedeId: string | null;
  readonly sede: string | null;
  readonly nivelId: string | null;
  readonly nivel: string | null;
  readonly titularidadId: string | null;
  readonly titularidad: string | null;
  readonly dedicacionId: string | null;
  readonly dedicacion: string | null;
  readonly categoriaId: string | null;
  readonly categoria: string | null;
  readonly tipoTituloId: string | null;
  readonly tipoTitulo: string | null;

  readonly asignaturasIds: readonly string[];
  /** Nombres de las materias, en el orden en que se escribieron. */
  readonly asignaturas: readonly string[];
  /** `true` si dicta clase pero nadie registro que asignatura. */
  readonly requiereAsignatura: boolean;
  readonly horas: Horas;
  readonly totalHoras: number;
  readonly medida: string | null;
  readonly observaciones: string | null;
  readonly actualizadoEn: string;
}

export interface FiltroDistributivo {
  readonly texto?: string;
  readonly docenteId?: string;
  readonly paoId?: string;
  /** Varios periodos a la vez. Se suma al filtro de uno solo. */
  readonly paoIds?: readonly string[];
  readonly facultadId?: string;
  readonly carreraId?: string;
  /** Varias carreras a la vez: es como se emite el reporte institucional. */
  readonly carreraIds?: readonly string[];
  readonly sedeId?: string;
  readonly nivelId?: string;
  readonly titularidadId?: string;
  readonly dedicacionId?: string;
  readonly categoriaId?: string;
  readonly tipoTituloId?: string;
  readonly sinAsignatura?: boolean;
  readonly conCarga?: boolean;
}

export interface DatosFilaDistributivo {
  readonly docenteId: string;
  readonly paoId: string;
  readonly facultadId: string;
  readonly carreraId: string;
  readonly sedeId?: string | null;
  readonly nivelId?: string | null;
  readonly titularidadId?: string | null;
  readonly dedicacionId?: string | null;
  readonly categoriaId?: string | null;
  readonly tipoTituloId?: string | null;
  readonly asignaturasIds?: readonly string[];
  readonly horas?: Record<string, number>;
  readonly medida?: string | null;
  readonly observaciones?: string | null;
}

export type CambiosFilaDistributivo = Partial<
  Omit<DatosFilaDistributivo, 'docenteId' | 'paoId'>
>;

/**
 * Par etiqueta/valor de los resumenes del distributivo.
 *
 * Se distingue del `Conteo` del tablero, que ademas lleva el porcentaje: aqui
 * los totales se muestran en crudo.
 */
export interface ConteoSimple {
  readonly etiqueta: string;
  readonly valor: number;
}

export interface ResumenDistributivo {
  readonly totalFilas: number;
  readonly totalDocentes: number;
  readonly totalHoras: number;
  readonly filasSinAsignatura: number;
  readonly porCategoria: readonly ConteoSimple[];
  readonly porDedicacion: readonly ConteoSimple[];
  readonly porFacultad: readonly ConteoSimple[];
}

// ---------------------------------------------------------------------------
// Reporte institucional
// ---------------------------------------------------------------------------

export interface PeticionReporteDistributivo {
  /** Al menos uno. Varios periodos salen en un solo archivo. */
  readonly paoIds: readonly string[];
  readonly facultadIds?: readonly string[];
  readonly carreraIds?: readonly string[];
  /** Codigo de la plantilla. Vacio usa la institucional. */
  readonly plantilla?: string | null;
  readonly incluirColumnasAuditoria?: boolean;
}

/** Una plantilla de exportacion ofrecida por el backend. */
export interface PlantillaReporte {
  readonly codigo: string;
  readonly nombre: string;
  readonly descripcion: string;
  readonly admiteAuditoria: boolean;
}

/**
 * Definicion de una columna de la vista previa.
 *
 * Las columnas llegan con la respuesta en lugar de estar fijas aqui: es lo que
 * permite que una plantilla nueva del backend aparezca sola en la pantalla.
 */
export interface ColumnaReporte {
  readonly clave: string;
  readonly titulo: string;
  readonly ancho: number;
  readonly tipo: string;
  readonly alineacion: string;
  /** Color de la cabecera en RRGGBB, o `null` para el del tema. */
  readonly colorCabecera: string | null;
}

export interface VistaPreviaReporte {
  readonly plantilla: string;
  readonly nombrePlantilla: string;
  readonly columnas: readonly ColumnaReporte[];
  /** Valores en el orden de `columnas`, una lista por fila. */
  readonly filas: readonly (readonly unknown[])[];
  readonly totalFilas: number;
  readonly totalDocentes: number;
  readonly sinAsignatura: number;
  readonly sinAnioInicio: number;
  readonly periodos: readonly string[];
  readonly facultades: readonly string[];
  readonly carreras: readonly string[];
  readonly estaCompleto: boolean;
}

/** Una asignatura capturada para una fila del distributivo. */
export interface AsignaturaCapturada {
  readonly filaId: string;
  /** Una o varias materias separadas por comas. Vacio las retira todas. */
  readonly asignatura: string;
}

export interface ResultadoCapturaAsignaturas {
  readonly actualizadas: number;
  readonly sinCambios: number;
  /** Asignaturas que no estaban en el catalogo y se agregaron al vuelo. */
  readonly asignaturasCreadas: number;
}

export type PaginaDistributivo = Pagina<FilaDistributivo>;

// ---------------------------------------------------------------------------
// Tablero del distributivo
// ---------------------------------------------------------------------------

/** Un periodo academico con carga, como lo ofrece el selector del tablero. */
export interface PeriodoConFilas {
  readonly id: string;
  readonly codigo: string;
  readonly nombre: string;
  /** `2026-2`. Vacio si el catalogo no lo trae. */
  readonly semestre: string;
  readonly filas: number;
}

/**
 * Como quedo la validacion de un grupo de periodos.
 *
 * `evaluadas` es el denominador del porcentaje y **no** es `total`: los
 * periodos anteriores a 2026-2 no traen estado, y contarlos como reprobados
 * pintaria todo el historico en rojo. Cuando `evaluadas` es cero, la pantalla
 * muestra un guion en lugar de «0 %».
 */
export interface ValidacionDeGrupo {
  readonly codigos: readonly string[];
  readonly nombres: readonly string[];
  readonly total: number;
  readonly aprobadas: number;
  readonly pendientes: number;
  readonly conError: number;
  readonly sinEstado: number;
  readonly evaluadas: number;
  readonly porcentajeAprobado: number;
  readonly docentes: number;
  readonly horas: number;
  readonly porEstado: readonly Conteo[];
}

/** Una facultad con sus cifras en los dos periodos comparados. */
export interface FilaComparativa {
  readonly etiqueta: string;
  readonly totalActual: number;
  readonly aprobadasActual: number;
  readonly evaluadasActual: number;
  readonly porcentajeActual: number;
  readonly totalAnterior: number;
  readonly aprobadasAnterior: number;
  readonly evaluadasAnterior: number;
  readonly porcentajeAnterior: number;
  /** Puntos porcentuales ganados o perdidos entre los dos periodos. */
  readonly variacion: number;
}

export interface TableroDistributivo {
  readonly periodos: readonly PeriodoConFilas[];
  readonly actual: ValidacionDeGrupo | null;
  readonly anterior: ValidacionDeGrupo | null;
  readonly porFacultad: readonly FilaComparativa[];
  readonly porSede: readonly Conteo[];
  readonly porDedicacion: readonly Conteo[];
  readonly generadoEn: string;
}

/** Estados de validacion, con la etiqueta que ve el usuario. */
export const ETIQUETAS_ESTADO_VALIDACION: Readonly<Record<string, string>> = {
  OK: 'Validado',
  OK_EXCEPCION: 'Validado con excepcion',
  PENDIENTE: 'Validacion pendiente',
  ERROR: 'Con error',
  SIN_ESTADO: 'Sin estado registrado',
};

// ---------------------------------------------------------------------------
// Carga de un PAO
// ---------------------------------------------------------------------------

/** Lo que el usuario elige antes de subir el archivo. */
export interface PeticionCargaPao {
  readonly archivo: File;
  /** Semestre que cubre el archivo, `2026-2`. El archivo no lo trae. */
  readonly semestre: string;
  readonly interciclo: boolean;
  readonly actualizarExistentes: boolean;
  readonly hoja?: string;
}

export interface FilaRechazada {
  readonly numeroFila: number;
  readonly identificacion: string;
  readonly motivo: string;
}

export interface FilaConsolidada {
  readonly identificacion: string;
  readonly pao: string;
  readonly carrera: string;
  readonly sede: string | null;
  readonly filasOrigen: readonly number[];
  readonly totalHorasResultante: number;
}

export interface ResultadoCargaPao {
  readonly totalFilasLeidas: number;
  readonly filasCreadas: number;
  readonly filasActualizadas: number;
  readonly docentesCreados: number;
  readonly docentesExistentes: number;
  readonly filasConsolidadas: number;
  readonly titulosCreados: number;
  readonly elementosCatalogoCreados: Readonly<Record<string, number>>;
  readonly rechazadas: readonly FilaRechazada[];
  readonly consolidaciones: readonly FilaConsolidada[];
  /** Filas que el lector descarto: juntan varias carreras o sedes en una celda. */
  readonly noDesglosadas: readonly FilaRechazada[];
  readonly exitosa: boolean;
  readonly resumen: string;
  readonly periodo: string;
}

// ---------------------------------------------------------------------------
// Resumenes comparativos
// ---------------------------------------------------------------------------

/**
 * Lo que un grupo de periodos suma en conjunto.
 *
 * `docentes` **no es la suma de la columna por facultad**: un docente que
 * dicta en dos facultades cuenta una vez aqui y dos alli.
 */
export interface GrupoDePeriodos {
  readonly codigos: readonly string[];
  readonly filas: number;
  readonly docentes: number;
}

/**
 * Una facultad en los dos grupos que se comparan.
 *
 * Hubo una columna «% Avance» —el cociente de los dos recuentos de docentes—
 * que se retiro: se leia como una tasa de continuidad y no lo es. Una facultad
 * que pasa de 41 a 45 docentes marcaba 109,8 % aunque solo 38 de los 41
 * originales hubieran vuelto.
 */
export interface AvanceDeFacultad {
  readonly codigo: string;
  readonly nombre: string;
  readonly docentesA: number;
  readonly docentesB: number;
  readonly filasAprobadasB: number;
  /** Filas del grupo 2 que si traen estado. Es el denominador del porcentaje. */
  readonly filasEvaluadasB: number;
  readonly porcentajeAprobadoB: number;
}

/** Las filas de una facultad repartidas por estado de validacion. */
export interface EstadosDeFacultad {
  readonly codigo: string;
  readonly nombre: string;
  readonly ok: number;
  readonly okExcepcion: number;
  readonly pendiente: number;
  readonly conError: number;
  readonly sinEstado: number;
  readonly total: number;
  readonly evaluadas: number;
  readonly porcentajeAprobado: number;
}

export interface ResumenComparativo {
  readonly periodos: readonly PeriodoConFilas[];
  readonly grupoA: GrupoDePeriodos | null;
  readonly grupoB: GrupoDePeriodos | null;
  readonly avance: readonly AvanceDeFacultad[];
  readonly estadosA: readonly EstadosDeFacultad[];
  readonly estadosB: readonly EstadosDeFacultad[];
  readonly generadoEn: string;
}

/**
 * Que facultades y carreras existen realmente en lo ya elegido.
 *
 * Las dos viajan juntas porque se piden a la vez y tienen que ser coherentes:
 * con dos llamadas, la carrera podria llegar antes que la facultad que la
 * contiene y la pantalla mostraria un estado imposible durante un instante.
 */
export interface AmbitoDisponible {
  readonly facultades: readonly OpcionSelector[];
  readonly carreras: readonly OpcionSelector[];
}

/** Lo que identifica el resumen que se quiere descargar. */
export interface PeticionResumen {
  readonly resumen: TipoResumen;
  readonly grupoA: readonly string[];
  readonly grupoB: readonly string[];
  /** Para el resumen de estados: cual de los dos grupos se desglosa. */
  readonly grupo: 'a' | 'b';
  /** Como titular cada grupo. Vacio deja que el servidor use el semestre. */
  readonly etiquetaA?: string;
  readonly etiquetaB?: string;
  /** Sin elegir ninguna, se incluyen todas las dedicaciones. */
  readonly dedicacionIds?: readonly string[];
}

// ---------------------------------------------------------------------------
// Horas por docentes: horas de `Da` por carrera y facultad, en un PAO,
// filtradas por dedicacion (o todas)
// ---------------------------------------------------------------------------

export interface HorasPorFacultad {
  readonly codigo: string;
  readonly nombre: string;
  readonly docentes: number;
  readonly horasDa: number;
}

/** Una carrera con sus docentes de la dedicacion elegida. Lleva su facultad
 * porque una misma carrera se dicta en mas de una. */
export interface HorasPorCarrera {
  readonly facultadCodigo: string;
  readonly facultadNombre: string;
  readonly carrera: string;
  readonly docentes: number;
  readonly horasDa: number;
}

/** Docentes de un PAO, con sus horas de `Da` por carrera y facultad. Se puede
 * acotar a una dedicacion o dejarlas todas. */
export interface ResumenDeHoras {
  readonly periodos: readonly PeriodoConFilas[];
  readonly grupo: GrupoDePeriodos | null;
  readonly docentes: number;
  readonly horasDa: number;
  readonly porFacultad: readonly HorasPorFacultad[];
  readonly porCarrera: readonly HorasPorCarrera[];
  readonly generadoEn: string;
}

/**
 * El semestre que reune un grupo de periodos: `262651` y `262151` son `2026-2`.
 *
 * Es el rotulo por defecto de las columnas. Seis codigos no caben en una
 * cabecera; el semestre si, y es como se nombra el periodo al hablarlo.
 */
export function semestresDe(codigos: readonly string[]): string {
  const vistos: string[] = [];
  for (const codigo of codigos) {
    if (codigo.length < 3) continue;
    const semestre = `20${codigo.slice(0, 2)}-${codigo.slice(2, 3)}`;
    if (!vistos.includes(semestre)) vistos.push(semestre);
  }
  return vistos.join(' · ');
}

/** Los resumenes que ofrece la pantalla. El valor viaja en la URL. */
export const TipoResumen = {
  AVANCE: 'avance',
  ESTADOS: 'estados',
  /** Las dos del tablero. */
  APROBACION: 'aprobacion',
  COMPARATIVO: 'comparativo',
} as const;

export type TipoResumen = (typeof TipoResumen)[keyof typeof TipoResumen];
