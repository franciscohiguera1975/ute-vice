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
    // El tablero pide `distributivo:leer`, no `dashboard:ver`: el rol de
    // consulta no tiene el tablero general y aun asi debe poder verlo.
    path: 'tablero',
    loadComponent: () =>
      import('./tablero.component').then((m) => m.TableroDistributivoComponent),
    title: 'Tablero del distributivo — UTE Vice',
  },
  {
    path: 'resumenes',
    loadComponent: () =>
      import('./resumenes.component').then((m) => m.ResumenesDistributivoComponent),
    title: 'Resumenes del distributivo — UTE Vice',
  },
  {
    path: 'importar',
    canActivate: [guardaPermiso(Permiso.DISTRIBUTIVO_IMPORTAR)],
    loadComponent: () => import('./importar.component').then((m) => m.ImportarPaoComponent),
    title: 'Cargar un PAO — UTE Vice',
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
