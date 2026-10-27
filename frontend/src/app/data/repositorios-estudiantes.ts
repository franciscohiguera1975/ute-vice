/** Implementacion HTTP del puerto de la matricula estudiantil. */

import { Injectable, inject } from '@angular/core';
import type { Observable } from 'rxjs';

import type { PeticionCargaEstudiantes, ResultadoCargaEstudiantes } from '@domain/modelos';
import { RepositorioEstudiantes } from '@domain/puertos';

import { ApiService } from './api.service';

@Injectable()
export class EstudiantesHttp extends RepositorioEstudiantes {
  private readonly api = inject(ApiService);

  cargar(peticion: PeticionCargaEstudiantes): Observable<ResultadoCargaEstudiantes> {
    return this.api.subir<ResultadoCargaEstudiantes>(
      '/estudiantes/importaciones',
      peticion.archivo,
      {},
    );
  }
}

/** Enlaza el puerto de la matricula estudiantil con su implementacion HTTP. */
export const PROVEEDORES_ESTUDIANTES = [
  { provide: RepositorioEstudiantes, useClass: EstudiantesHttp },
];
