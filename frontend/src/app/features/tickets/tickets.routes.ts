import type { Routes } from '@angular/router';

import { Permiso } from '@domain/modelos';
import { guardaPermiso } from '@core/guardas';

export const rutas: Routes = [
  {
    path: '',
    loadComponent: () => import('./lista.component').then((m) => m.ListaTicketsComponent),
    title: 'Tickets — UTE Vice',
  },
  {
    path: 'nuevo',
    canActivate: [guardaPermiso(Permiso.TICKETS_ESCRIBIR)],
    loadComponent: () => import('./formulario.component').then((m) => m.FormularioTicketComponent),
    title: 'Nuevo ticket — UTE Vice',
  },
  {
    path: ':id',
    loadComponent: () => import('./detalle.component').then((m) => m.DetalleTicketComponent),
    title: 'Detalle de ticket — UTE Vice',
  },
];
