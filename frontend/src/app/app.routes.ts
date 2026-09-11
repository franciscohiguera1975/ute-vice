/**
 * Mapa de rutas.
 *
 * Cada seccion se carga de forma diferida: quien solo consulta el tablero no
 * descarga el codigo de administracion de usuarios.
 *
 * Las guardas de permiso son una comodidad de la interfaz, no el control de
 * seguridad —ese lo impone el backend en cada caso de uso—. Lo que evitan es
 * que alguien llegue a una pantalla que no va a poder usar.
 */

import type { Routes } from '@angular/router';

import { Permiso } from '@domain/modelos';

import {
  guardaAnonimo,
  guardaAutenticado,
  guardaContrasenaVigente,
  guardaPermiso,
} from './core/guardas';

export const rutas: Routes = [
  {
    path: 'acceso',
    canActivate: [guardaAnonimo],
    loadComponent: () =>
      import('@features/acceso/acceso.component').then((m) => m.AccesoComponent),
    title: 'Acceso — UTE Vice',
  },
  {
    path: 'acceso/google',
    loadComponent: () =>
      import('@features/acceso/retorno-google.component').then(
        (m) => m.RetornoGoogleComponent,
      ),
    title: 'Ingresando…',
  },

  {
    path: '',
    canActivate: [guardaAutenticado],
    canActivateChild: [guardaContrasenaVigente],
    loadComponent: () =>
      import('@shared/layout/layout.component').then((m) => m.LayoutComponent),
    children: [
      { path: '', pathMatch: 'full', redirectTo: 'tablero' },

      {
        path: 'tablero',
        canActivate: [guardaPermiso(Permiso.DASHBOARD_VER)],
        loadComponent: () =>
          import('@features/tablero/tablero.component').then((m) => m.TableroComponent),
        title: 'Tablero — UTE Vice',
      },

      {
        path: 'personas',
        canActivate: [guardaPermiso(Permiso.PERSONAS_LEER)],
        loadChildren: () => import('@features/personas/personas.routes').then((m) => m.rutas),
      },

      {
        path: 'titulos',
        canActivate: [guardaPermiso(Permiso.TITULOS_LEER)],
        loadComponent: () =>
          import('@features/titulos/titulos.component').then((m) => m.TitulosComponent),
        title: 'Titulos — UTE Vice',
      },

      {
        path: 'consultas',
        canActivate: [guardaPermiso(Permiso.CONSULTAS_LEER)],
        loadChildren: () => import('@features/consultas/consultas.routes').then((m) => m.rutas),
      },

      {
        path: 'distributivo',
        canActivate: [guardaPermiso(Permiso.DISTRIBUTIVO_LEER)],
        loadChildren: () =>
          import('@features/distributivo/distributivo.routes').then((m) => m.rutas),
      },

      {
        path: 'catalogos',
        canActivate: [guardaPermiso(Permiso.CATALOGOS_LEER)],
        loadChildren: () =>
          import('@features/catalogos/catalogos.routes').then((m) => m.rutas),
      },

      {
        path: 'reportes',
        canActivate: [guardaPermiso(Permiso.REPORTES_GENERAR)],
        loadComponent: () =>
          import('@features/reportes/reportes.component').then((m) => m.ReportesComponent),
        title: 'Reportes — UTE Vice',
      },

      {
        path: 'administracion',
        canActivate: [guardaPermiso(Permiso.USUARIOS_LEER)],
        loadChildren: () =>
          import('@features/administracion/administracion.routes').then((m) => m.rutas),
      },

      {
        path: 'perfil',
        loadChildren: () => import('@features/perfil/perfil.routes').then((m) => m.rutas),
      },
    ],
  },

  {
    path: '**',
    loadComponent: () =>
      import('@shared/paginas/no-encontrado.component').then((m) => m.NoEncontradoComponent),
    title: 'Pagina no encontrada',
  },
];
