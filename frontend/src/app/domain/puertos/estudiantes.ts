/** Puerto de la carga de matricula estudiantil. */

import type { Observable } from 'rxjs';

import type { PeticionCargaEstudiantes, ResultadoCargaEstudiantes } from '../modelos';

export abstract class RepositorioEstudiantes {
  /** Sube un reporte de matricula estudiantil de Banner. */
  abstract cargar(peticion: PeticionCargaEstudiantes): Observable<ResultadoCargaEstudiantes>;
}
