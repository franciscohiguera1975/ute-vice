/** Modelos de la carga de matricula estudiantil. */

// ---------------------------------------------------------------------------
// Carga de un reporte de matricula
// ---------------------------------------------------------------------------

/** Lo que el usuario elige antes de subir el archivo.
 *
 * A diferencia de la carga del PAO, no hace falta pedir el periodo: el
 * reporte de Banner trae el padron completo vigente, con el periodo como una
 * columna mas de cada fila.
 */
export interface PeticionCargaEstudiantes {
  readonly archivo: File;
}

export interface FilaRechazadaEstudiante {
  readonly numeroFila: number;
  readonly cedula: string;
  readonly motivo: string;
}

export interface ResultadoCargaEstudiantes {
  readonly totalFilasLeidas: number;
  readonly estudiantesCreados: number;
  readonly estudiantesExistentes: number;
  readonly matriculasCreadas: number;
  readonly matriculasActualizadas: number;
  readonly becasCreadas: number;
  readonly generosCreados: number;
  /** Filas cuya carrera no coincidio por igualdad exacta con ningun elemento
   *  del catalogo de carreras. No se rechazaron ni se creo una carrera nueva:
   *  solo quedaron sin resolver. */
  readonly sinCarreraReconocida: number;
  /** Filas que repetian la clave natural de una matricula ya vista en el
   *  mismo archivo -casi siempre una beca adicional sin concatenar en la
   *  misma celda- y se fusionaron con ella en vez de contarse aparte. */
  readonly filasCombinadasPorDuplicado: number;
  readonly rechazadas: readonly FilaRechazadaEstudiante[];
  readonly exitosa: boolean;
  readonly resumen: string;
}
