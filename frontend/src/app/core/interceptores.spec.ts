/**
 * Pruebas de los interceptores HTTP.
 *
 * Existen por un fallo concreto: registrados en el orden equivocado, el
 * interceptor de autenticacion recibia el error ya normalizado, `instanceof
 * HttpErrorResponse` era falso y **ni la renovacion de sesion ni el redirigir
 * al acceso llegaban a ejecutarse**. Nada fallaba de forma visible; el usuario
 * solo veia pantallas vacias con avisos tecnicos.
 *
 * Por eso se prueba a traves de `INTERCEPTORES` —la lista real, en su orden
 * real— y no montando los interceptores a mano: un orden mal puesto tiene que
 * hacer fallar estas pruebas.
 */

import { HttpClient, provideHttpClient, withInterceptors } from '@angular/common/http';
import {
  HttpTestingController,
  provideHttpClientTesting,
} from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { Router } from '@angular/router';
import { Observable, of, throwError } from 'rxjs';

import type { ErrorApi, Sesion, Usuario } from '@domain/modelos';
import { RepositorioAutenticacion } from '@domain/puertos';

import { INTERCEPTORES } from './interceptores';
import { NotificacionesService } from './notificaciones.service';
import { SesionStore } from './sesion.store';

const USUARIO = {
  id: 'u-1',
  email: 'admin@ute.edu.ec',
  nombreCompleto: 'Administrador del Sistema',
  proveedor: 'local',
  activo: true,
  esSuperusuario: true,
  debeCambiarContrasena: false,
  roles: [],
  permisos: [],
  facultadesIds: [],
  carrerasIds: [],
  alcanceTotal: true,
  ultimoAcceso: null,
  creadoEn: '2026-01-01T00:00:00Z',
} as unknown as Usuario;

const sesionCon = (acceso: string, refresco: string): Sesion => ({
  tokens: { acceso, refresco, tipo: 'Bearer', expiraEnSegundos: 7200 },
  usuario: USUARIO,
  debeCambiarContrasena: false,
});

/** Doble del repositorio: solo `refrescar` interviene en estas pruebas. */
class AutenticacionFalsa {
  refrescos = 0;
  respuesta: () => Observable<Sesion> = () => of(sesionCon('acceso-2', 'refresco-2'));

  refrescar(_token: string): Observable<Sesion> {
    this.refrescos++;
    return this.respuesta();
  }
}

describe('interceptores', () => {
  let http: HttpClient;
  let backend: HttpTestingController;
  let sesion: SesionStore;
  let router: jasmine.SpyObj<Router>;
  let autenticacion: AutenticacionFalsa;

  beforeEach(() => {
    localStorage.clear();
    autenticacion = new AutenticacionFalsa();
    router = jasmine.createSpyObj<Router>('Router', ['navigate']);
    router.navigate.and.resolveTo(true);

    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(withInterceptors([...INTERCEPTORES])),
        provideHttpClientTesting(),
        { provide: Router, useValue: router },
        { provide: RepositorioAutenticacion, useValue: autenticacion },
      ],
    });

    http = TestBed.inject(HttpClient);
    backend = TestBed.inject(HttpTestingController);
    sesion = TestBed.inject(SesionStore);
  });

  afterEach(() => {
    backend.verify();
    localStorage.clear();
  });

  it('adjunta el token de acceso a las rutas protegidas', () => {
    sesion.establecer(sesionCon('acceso-1', 'refresco-1'));
    http.get('/api/v1/catalogos/facultades').subscribe();

    const peticion = backend.expectOne('/api/v1/catalogos/facultades');
    expect(peticion.request.headers.get('Authorization')).toBe('Bearer acceso-1');
    peticion.flush({});
  });

  it('no adjunta el token al iniciar sesion', () => {
    sesion.establecer(sesionCon('acceso-1', 'refresco-1'));
    http.post('/api/v1/auth/login', {}).subscribe();

    const peticion = backend.expectOne('/api/v1/auth/login');
    expect(peticion.request.headers.has('Authorization')).toBeFalse();
    peticion.flush({});
  });

  it('normaliza el error al contrato ErrorApi', (listo) => {
    sesion.establecer(sesionCon('acceso-1', 'refresco-1'));
    http.get('/api/v1/personas').subscribe({
      error: (error: ErrorApi) => {
        expect(error.codigo).toBe('validacion');
        expect(error.estado).toBe(422);
        listo();
      },
    });

    backend
      .expectOne('/api/v1/personas')
      .flush(
        { codigo: 'validacion', mensaje: 'Los datos no son validos', detalles: {} },
        { status: 422, statusText: 'Unprocessable Content' },
      );
  });

  // -------------------------------------------------------------- el fallo
  it('ante un 401 sin token de refresco, envia al acceso', (listo) => {
    sesion.establecer(sesionCon('acceso-1', ''));

    http.get('/api/v1/catalogos/facultades').subscribe({
      error: () => {
        expect(router.navigate).toHaveBeenCalledOnceWith(
          ['/acceso'],
          jasmine.objectContaining({ queryParams: jasmine.anything() }),
        );
        expect(sesion.tokenAcceso).withContext('la sesion se limpia').toBeNull();
        listo();
      },
    });

    backend
      .expectOne('/api/v1/catalogos/facultades')
      .flush(
        { codigo: 'token_invalido', mensaje: 'El token es invalido o ha expirado' },
        { status: 401, statusText: 'Unauthorized' },
      );
  });

  it('ante un 401 con token de refresco, renueva y reintenta', (listo) => {
    sesion.establecer(sesionCon('acceso-1', 'refresco-1'));

    http.get('/api/v1/catalogos/facultades').subscribe({
      next: () => {
        expect(autenticacion.refrescos).toBe(1);
        expect(sesion.tokenAcceso).toBe('acceso-2');
        expect(router.navigate).not.toHaveBeenCalled();
        listo();
      },
    });

    backend
      .expectOne('/api/v1/catalogos/facultades')
      .flush({ codigo: 'token_invalido', mensaje: 'expirado' }, { status: 401, statusText: '' });

    // El reintento lleva ya el token nuevo.
    const reintento = backend.expectOne('/api/v1/catalogos/facultades');
    expect(reintento.request.headers.get('Authorization')).toBe('Bearer acceso-2');
    reintento.flush({ items: [] });
  });

  it('si la renovacion tambien falla, envia al acceso', (listo) => {
    sesion.establecer(sesionCon('acceso-1', 'refresco-vencido'));
    autenticacion.respuesta = () => throwError(() => new Error('refresco invalido'));

    http.get('/api/v1/catalogos/facultades').subscribe({
      error: () => {
        expect(router.navigate).toHaveBeenCalledTimes(1);
        expect(sesion.tokenRefresco).toBeNull();
        listo();
      },
    });

    backend
      .expectOne('/api/v1/catalogos/facultades')
      .flush({ codigo: 'token_invalido', mensaje: 'expirado' }, { status: 401, statusText: '' });
  });

  it('deja un solo aviso aunque fallen varias peticiones a la vez', (listo) => {
    sesion.establecer(sesionCon('acceso-1', ''));
    const notificaciones = TestBed.inject(NotificacionesService);

    let fallidas = 0;
    const alFallar = (): void => {
      if (++fallidas < 3) return;
      // Las tres peticiones caducan por la misma causa: un aviso, no tres.
      expect(notificaciones.avisos().length).toBe(1);
      expect(notificaciones.avisos()[0]!.mensaje).toBe('Su sesión expiró');
      expect(router.navigate).toHaveBeenCalledTimes(1);
      listo();
    };

    for (const ruta of ['/api/v1/catalogos/facultades', '/api/v1/personas', '/api/v1/titulos']) {
      http.get(ruta).subscribe({ error: alFallar });
    }

    for (const ruta of ['/api/v1/catalogos/facultades', '/api/v1/personas', '/api/v1/titulos']) {
      backend
        .expectOne(ruta)
        .flush({ codigo: 'token_invalido', mensaje: 'expirado' }, { status: 401, statusText: '' });
    }

    // Y el aviso que cada pantalla intentaria mostrar queda descartado.
    notificaciones.error('No fue posible cargar el catálogo', 'Signature has expired');
    expect(notificaciones.avisos().length).toBe(1);
  });
});
