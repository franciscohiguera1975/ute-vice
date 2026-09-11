import type { Routes } from '@angular/router';

import { guardaPermiso } from '@core/guardas';
import { Permiso } from '@domain/modelos';

export const rutas: Routes = [
  {
    path: '',
    loadComponent: () => import('./lista.component').then((m) => m.ListaDistributivoComponent),
    title: 'Distributivo docente — UTE Vice',
  },
  {
    path: 'asignaturas',
    canActivate: [guardaPermiso(Permiso.DISTRIBUTIVO_ESCRIBIR)],
    loadComponent: () =>
      import('./asignaturas.component').then((m) => m.AsignaturasComponent),
    title: 'Asignaturas que imparte — UTE Vice',
  },
  {
    path: 'reporte',
    canActivate: [guardaPermiso(Permiso.REPORTES_GENERAR)],
    loadComponent: () =>
      import('./reporte.component').then((m) => m.ReporteDistributivoComponent),
    title: 'Exportar el distributivo — UTE Vice',
  },
];
