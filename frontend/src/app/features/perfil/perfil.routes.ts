import type { Routes } from '@angular/router';

export const rutas: Routes = [
  {
    path: '',
    pathMatch: 'full',
    loadComponent: () => import('./perfil.component').then((m) => m.PerfilComponent),
    title: 'Mi perfil — UTE Vice',
  },
  {
    path: 'contrasena',
    loadComponent: () => import('./contrasena.component').then((m) => m.ContrasenaComponent),
    title: 'Cambiar contrasena — UTE Vice',
  },
];
