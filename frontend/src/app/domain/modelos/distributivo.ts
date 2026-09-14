/** Modelos del distributivo docente. Reflejan los del backend. */

import type { Pagina } from './comunes';

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
