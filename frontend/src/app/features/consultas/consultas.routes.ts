import type { Routes } from '@angular/router';

import { guardaPermiso } from '@core/guardas';
import { Permiso } from '@domain/modelos';

export const rutas: Routes = [
  { path: '', pathMatch: 'full', redirectTo: 'jobs' },
  {
    path: 'jobs',
    loadComponent: () => import('./jobs.component').then((m) => m.JobsComponent),
    title: 'Campanas de consulta — UTE Vice',
  },
  {
    path: 'logs',
    loadComponent: () => import('./logs.component').then((m) => m.LogsComponent),
    title: 'Historico de consultas — UTE Vice',
  },
  {
    path: 'planificador',
    canActivate: [guardaPermiso(Permiso.CONSULTAS_LEER)],
    loadComponent: () =>
      import('./planificador.component').then((m) => m.PlanificadorComponent),
    title: 'Planificador — UTE Vice',
  },
];
