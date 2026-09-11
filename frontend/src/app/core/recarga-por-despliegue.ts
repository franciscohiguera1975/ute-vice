/**
 * Recuperacion ante un despliegue con la aplicacion abierta.
 *
 * Angular divide la aplicacion en fragmentos que descarga cuando hace falta, y
 * cada compilacion les cambia el nombre. Si alguien tiene la pestana abierta
 * cuando se publica una version nueva, los fragmentos que todavia no habia
 * descargado dejan de existir: al pulsar una seccion a la que no habia entrado,
 * la navegacion **falla en silencio** y da la impresion de que el enlace no
 * funciona.
 *
 * Aqui se detecta ese fallo concreto y se recarga la pagina una sola vez, que
 * es lo unico que puede arreglarlo: hay que volver a pedir el `index.html` para
 * conocer los nombres nuevos.
 *
 * El cerrojo en `sessionStorage` evita el bucle. Si tras recargar el fragmento
 * sigue sin aparecer —un despliegue a medias, por ejemplo— el error se propaga
 * en lugar de recargar sin fin.
 */

import { ErrorHandler, Injectable, inject } from '@angular/core';

import { NotificacionesService } from './notificaciones.service';

const CERROJO = 'ute_vice_recarga_despliegue';

/** Lo que dicen los navegadores cuando un fragmento ya no esta. */
const SENALES = [
  'failed to fetch dynamically imported module',
  'error loading dynamically imported module',
  'importing a module script failed',
  'chunkloaderror',
  'loading chunk',
];

export function esFragmentoPerdido(error: unknown): boolean {
  const texto = `${(error as Error)?.name ?? ''} ${(error as Error)?.message ?? error}`.toLowerCase();
  return SENALES.some((senal) => texto.includes(senal));
}

@Injectable()
export class ManejadorDeErrores implements ErrorHandler {
  private readonly notificaciones = inject(NotificacionesService);

  handleError(error: unknown): void {
    if (esFragmentoPerdido(error) && this.puedeRecargar()) {
      this.marcarRecarga();
      this.notificaciones.info('Actualizando a la versión nueva…');
      // Un respiro para que el aviso alcance a pintarse.
      setTimeout(() => location.reload(), 400);
      return;
    }

    console.error(error);
  }

  private puedeRecargar(): boolean {
    try {
      return sessionStorage.getItem(CERROJO) === null;
    } catch {
      // Sin almacenamiento no hay cerrojo posible: se prefiere no recargar
      // antes que arriesgar un bucle.
      return false;
    }
  }

  private marcarRecarga(): void {
    try {
      sessionStorage.setItem(CERROJO, String(Date.now()));
    } catch {
      /* sin almacenamiento: ya se decidio no recargar */
    }
  }
}

/** Limpia el cerrojo cuando la aplicacion arranca sin problemas. */
export function limpiarCerrojoDeRecarga(): void {
  try {
    sessionStorage.removeItem(CERROJO);
  } catch {
    /* sin almacenamiento: no hay nada que limpiar */
  }
}
