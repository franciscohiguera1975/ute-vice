import type { Routes } from '@angular/router';

import { Permiso } from '@domain/modelos';
import { guardaPermiso } from '@core/guardas';

export const rutas: Routes = [
  {
    path: '',
    loadComponent: () => import('./lista.component').then((m) => m.ListaPersonasComponent),
    title: 'Personas — UTE Vice',
  },
  {
    path: 'nueva',
    canActivate: [guardaPermiso(Permiso.PERSONAS_ESCRIBIR)],
    loadComponent: () => import('./formulario.component').then((m) => m.FormularioPersonaComponent),
    title: 'Nueva persona — UTE Vice',
  },
  {
    path: ':id',
    loadComponent: () => import('./detalle.component').then((m) => m.DetallePersonaComponent),
    title: 'Detalle de persona — UTE Vice',
  },
  {
    path: ':id/editar',
    canActivate: [guardaPermiso(Permiso.PERSONAS_ESCRIBIR)],
    loadComponent: () => import('./formulario.component').then((m) => m.FormularioPersonaComponent),
    title: 'Editar persona — UTE Vice',
  },
];
