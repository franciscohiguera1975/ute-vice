import type { Routes } from '@angular/router';

import { guardaPermiso } from '@core/guardas';
import { Permiso } from '@domain/modelos';

export const rutas: Routes = [
  { path: '', pathMatch: 'full', redirectTo: 'usuarios' },
  {
    path: 'usuarios',
    loadComponent: () => import('./usuarios.component').then((m) => m.UsuariosComponent),
    title: 'Usuarios — UTE Vice',
  },
  {
    path: 'roles',
    canActivate: [guardaPermiso(Permiso.USUARIOS_LEER)],
    loadComponent: () => import('./roles.component').then((m) => m.RolesComponent),
    title: 'Roles y permisos — UTE Vice',
  },
];
