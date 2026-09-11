import type { Routes } from '@angular/router';

export const rutas: Routes = [
  {
    path: '',
    pathMatch: 'full',
    redirectTo: 'paos',
  },
  {
    path: ':tipo',
    loadComponent: () => import('./catalogo.component').then((m) => m.CatalogoComponent),
    title: 'Catálogos — UTE Vice',
  },
];
