/**
 * Tipos compartidos por todo el dominio del frontend.
 *
 * El dominio del frontend es deliberadamente un espejo del backend: mismos
 * nombres, mismas enumeraciones, mismas reglas. Esa correspondencia hace que un
 * cambio de contrato se detecte al compilar, no en produccion.
 */

/** Respuesta paginada. Es la misma forma para todos los listados de la API. */
export interface Pagina<T> {
  readonly items: readonly T[];
  readonly total: number;
  readonly pagina: number;
  readonly tamano: number;
  readonly totalPaginas: number;
  readonly tieneSiguiente: boolean;
  readonly tieneAnterior: boolean;
}

export const paginaVacia = <T>(): Pagina<T> => ({
  items: [],
  total: 0,
  pagina: 1,
  tamano: 25,
  totalPaginas: 0,
  tieneSiguiente: false,
  tieneAnterior: false,
});

export interface ParametrosPaginacion {
  readonly pagina?: number;
  readonly tamano?: number;
  readonly ordenarPor?: string;
  readonly descendente?: boolean;
}

/**
 * Error del backend, ya normalizado.
 *
 * El backend responde siempre con la misma forma, asi que el frontend tiene un
 * unico contrato de error que interpretar. `codigo` es estable y apto para
 * logica; `mensaje` es para mostrar.
 */
export interface ErrorApi {
  readonly codigo: string;
  readonly mensaje: string;
  readonly detalles: Record<string, unknown>;
  readonly requestId: string | null;
  readonly estado: number;
}

/** Un archivo descargado desde la API. */
export interface ArchivoDescarga {
  readonly nombre: string;
  readonly contenido: Blob;
  readonly tipoMime: string;
}
