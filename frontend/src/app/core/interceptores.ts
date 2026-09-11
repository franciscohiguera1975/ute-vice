/**
 * Interceptores HTTP.
 *
 * Dos responsabilidades separadas en dos interceptores:
 *
 * 1. `interceptorAutenticacion` adjunta el token y renueva la sesion cuando
 *    expira, reintentando la peticion original de forma transparente.
 * 2. `interceptorErrores` normaliza cualquier fallo al contrato `ErrorApi`,
 *    para que los componentes tengan una sola forma de error que interpretar.
 */

import {
  HttpErrorResponse,
  type HttpEvent,
  type HttpHandlerFn,
  type HttpInterceptorFn,
  type HttpRequest,
} from '@angular/common/http';
import { inject } from '@angular/core';
import { type Observable, catchError, filter, switchMap, take, throwError } from 'rxjs';
import { BehaviorSubject } from 'rxjs';

import type { ErrorApi } from '@domain/modelos';
import { RepositorioAutenticacion } from '@domain/puertos';

import { SesionStore } from './sesion.store';

/** Rutas que no llevan token: son publicas o el token seria contraproducente. */
const RUTAS_PUBLICAS = ['/auth/login', '/auth/refrescar', '/auth/metodos', '/auth/google'];

const esRutaPublica = (url: string): boolean => RUTAS_PUBLICAS.some((r) => url.includes(r));

// ---------------------------------------------------------------------------
// Renovacion de sesion
// ---------------------------------------------------------------------------

/**
 * Estado compartido de la renovacion.
 *
 * Si varias peticiones reciben 401 a la vez, solo la primera dispara el
 * refresco; las demas esperan aqui al token nuevo. Sin esta coordinacion, N
 * peticiones concurrentes intentarian N refrescos, y la rotacion del token
 * invalidaria las sesiones entre si.
 */
let refrescando = false;
const tokenRenovado = new BehaviorSubject<string | null>(null);

export const interceptorAutenticacion: HttpInterceptorFn = (peticion, siguiente) => {
  // Las dependencias se resuelven aqui, en el cuerpo del interceptor, que es el
  // unico punto que corre dentro del contexto de inyeccion. Llamar a `inject()`
  // dentro de un `catchError` —que se ejecuta despues, de forma asincrona—
  // falla con NG0203 justo cuando mas falta hace: al renovar una sesion.
  const sesion = inject(SesionStore);
  const autenticacion = inject(RepositorioAutenticacion);

  if (esRutaPublica(peticion.url)) {
    return siguiente(peticion);
  }

  const token = sesion.tokenAcceso;
  const conToken = token ? adjuntar(peticion, token) : peticion;

  return siguiente(conToken).pipe(
    catchError((error: unknown) => {
      const es401 = error instanceof HttpErrorResponse && error.status === 401;
      if (!es401 || !sesion.tokenRefresco) {
        return throwError(() => error);
      }
      return renovarYReintentar(peticion, siguiente, sesion, autenticacion);
    }),
  );
};

function adjuntar(peticion: HttpRequest<unknown>, token: string): HttpRequest<unknown> {
  return peticion.clone({ setHeaders: { Authorization: `Bearer ${token}` } });
}

function renovarYReintentar(
  peticion: HttpRequest<unknown>,
  siguiente: HttpHandlerFn,
  sesion: SesionStore,
  autenticacion: RepositorioAutenticacion,
): Observable<HttpEvent<unknown>> {
  if (refrescando) {
    // Otra peticion ya esta renovando: se espera al token nuevo.
    return tokenRenovado.pipe(
      filter((t): t is string => t !== null),
      take(1),
      switchMap((token) => siguiente(adjuntar(peticion, token))),
    );
  }

  refrescando = true;
  tokenRenovado.next(null);

  const refresco = sesion.tokenRefresco;
  if (!refresco) {
    refrescando = false;
    sesion.expirar(location.pathname);
    return throwError(() => new Error('Sesion expirada'));
  }

  return autenticacion.refrescar(refresco).pipe(
    switchMap((nueva) => {
      sesion.establecer(nueva);
      refrescando = false;
      tokenRenovado.next(nueva.tokens.acceso);
      return siguiente(adjuntar(peticion, nueva.tokens.acceso));
    }),
    catchError((error: unknown) => {
      // El refresco fallo: la sesion es irrecuperable. Se envia al acceso
      // conservando la ruta para volver despues de reautenticar.
      refrescando = false;
      tokenRenovado.next(null);
      sesion.expirar(location.pathname + location.search);
      return throwError(() => error);
    }),
  );
}

// ---------------------------------------------------------------------------
// Normalizacion de errores
// ---------------------------------------------------------------------------

export const interceptorErrores: HttpInterceptorFn = (peticion, siguiente) =>
  siguiente(peticion).pipe(
    catchError((error: unknown) => throwError(() => normalizar(error))),
  );

function normalizar(error: unknown): ErrorApi {
  if (!(error instanceof HttpErrorResponse)) {
    return {
      codigo: 'error_desconocido',
      mensaje: 'Ocurrio un error inesperado',
      detalles: {},
      requestId: null,
      estado: 0,
    };
  }

  // Estado 0: el navegador no llego al servidor.
  if (error.status === 0) {
    return {
      codigo: 'sin_conexion',
      mensaje:
        'No fue posible contactar al servidor. Verifique su conexion e intente de nuevo.',
      detalles: {},
      requestId: null,
      estado: 0,
    };
  }

  const cuerpo = error.error as Partial<ErrorApi> | string | null;

  if (cuerpo && typeof cuerpo === 'object' && typeof cuerpo.codigo === 'string') {
    return {
      codigo: cuerpo.codigo,
      mensaje: cuerpo.mensaje ?? 'Error en la operacion',
      detalles: cuerpo.detalles ?? {},
      requestId: cuerpo.requestId ?? error.headers.get('X-Request-ID'),
      estado: error.status,
    };
  }

  return {
    codigo: `http_${error.status}`,
    mensaje: mensajePorEstado(error.status),
    detalles: {},
    requestId: error.headers.get('X-Request-ID'),
    estado: error.status,
  };
}

function mensajePorEstado(estado: number): string {
  const mensajes: Record<number, string> = {
    400: 'La solicitud no es valida.',
    401: 'Su sesion expiro. Vuelva a ingresar.',
    403: 'No tiene permiso para realizar esta operacion.',
    404: 'El recurso solicitado no existe.',
    409: 'La operacion entra en conflicto con datos existentes.',
    413: 'El resultado es demasiado grande. Aplique mas filtros.',
    422: 'Los datos enviados no son validos.',
    429: 'Demasiadas solicitudes. Espere un momento.',
    500: 'Error interno del servidor.',
    502: 'El servicio externo no respondio correctamente.',
    503: 'El servicio no esta disponible en este momento.',
  };
  return mensajes[estado] ?? `Error del servidor (${estado}).`;
}
