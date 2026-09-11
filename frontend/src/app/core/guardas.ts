/**
 * Guardas de rutas.
 *
 * Son una comodidad de la interfaz, no un control de seguridad: quien conozca
 * la URL de la API puede llamarla directamente. La autorizacion real la impone
 * el backend en cada caso de uso. Lo que estas guardas evitan es que el usuario
 * llegue a una pantalla que no podra usar.
 */

import { inject } from '@angular/core';
import type { CanActivateFn } from '@angular/router';
import { Router } from '@angular/router';

import type { Permiso } from '@domain/modelos';

import { NotificacionesService } from './notificaciones.service';
import { SesionStore } from './sesion.store';

/** Exige sesion iniciada. Conserva la ruta pedida para volver tras acceder. */
export const guardaAutenticado: CanActivateFn = (_ruta, estado) => {
  const sesion = inject(SesionStore);
  const router = inject(Router);

  if (sesion.autenticado()) return true;

  return router.createUrlTree(['/acceso'], {
    queryParams: { retorno: estado.url },
  });
};

/** Impide volver al acceso con una sesion ya iniciada. */
export const guardaAnonimo: CanActivateFn = () => {
  const sesion = inject(SesionStore);
  const router = inject(Router);
  return sesion.autenticado() ? router.createUrlTree(['/tablero']) : true;
};

/**
 * Exige uno o mas permisos. Basta con tener alguno de los indicados.
 *
 * Se usa asi en las rutas:
 *
 *     canActivate: [guardaAutenticado, guardaPermiso(Permiso.PERSONAS_LEER)]
 */
export function guardaPermiso(...permisos: readonly Permiso[]): CanActivateFn {
  return () => {
    const sesion = inject(SesionStore);
    const router = inject(Router);
    const avisos = inject(NotificacionesService);

    if (!sesion.autenticado()) {
      return router.createUrlTree(['/acceso']);
    }
    if (sesion.puedeAlguno(...permisos)) {
      return true;
    }

    avisos.error(
      'No tiene permiso para acceder a esa seccion',
      `Se requiere: ${permisos.join(' o ')}`,
    );
    return router.createUrlTree(['/tablero']);
  };
}

/**
 * Obliga a cambiar la contrasena antes de usar el sistema.
 *
 * Una cuenta recien creada o restablecida entra con una contrasena que conoce
 * un tercero —quien la creo—. Dejar navegar antes del cambio anularia el
 * proposito de marcarla como provisional.
 */
export const guardaContrasenaVigente: CanActivateFn = (_ruta, estado) => {
  const sesion = inject(SesionStore);
  const router = inject(Router);

  if (!sesion.debeCambiarContrasena()) return true;
  if (estado.url.startsWith('/perfil')) return true;

  return router.createUrlTree(['/perfil/contrasena'], {
    queryParams: { obligatorio: '1' },
  });
};
