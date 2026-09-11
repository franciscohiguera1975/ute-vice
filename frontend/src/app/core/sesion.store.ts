/**
 * Estado de la sesion.
 *
 * Se construye con signals y no con un `BehaviorSubject`: los componentes leen
 * `usuario()` o `puede(...)` directamente en la plantilla, sin `async` y sin
 * suscripciones que recordar cancelar.
 *
 * Sobre la persistencia: los tokens se guardan en `localStorage`. Es una
 * decision con un compromiso conocido —quedan expuestos a un XSS, a diferencia
 * de una cookie `HttpOnly`— que se toma porque el backend es un servicio
 * separado y la alternativa exigiria un proxy de sesion. Se compensa con tokens
 * de acceso cortos (30 min), rotacion del token de refresco con deteccion de
 * reutilizacion, y una politica de contenido restrictiva.
 */

import { Injectable, computed, inject, signal } from '@angular/core';
import { Router } from '@angular/router';
import { type Observable, tap } from 'rxjs';

import type { Permiso, Sesion, Usuario } from '@domain/modelos';

const CLAVE_ACCESO = 'ute_vice_acceso';
const CLAVE_REFRESCO = 'ute_vice_refresco';
const CLAVE_USUARIO = 'ute_vice_usuario';

@Injectable({ providedIn: 'root' })
export class SesionStore {
  private readonly router = inject(Router);

  private readonly _usuario = signal<Usuario | null>(this.leerUsuarioGuardado());
  private readonly _tokenAcceso = signal<string | null>(this.leer(CLAVE_ACCESO));
  private readonly _tokenRefresco = signal<string | null>(this.leer(CLAVE_REFRESCO));
  private readonly _cargando = signal(false);

  /** Usuario autenticado, o `null`. */
  readonly usuario = this._usuario.asReadonly();
  readonly cargando = this._cargando.asReadonly();

  readonly autenticado = computed(() => this._usuario() !== null && this._tokenAcceso() !== null);
  readonly permisos = computed(() => new Set<string>(this._usuario()?.permisos ?? []));
  readonly nombre = computed(() => this._usuario()?.nombreCompleto ?? '');
  readonly debeCambiarContrasena = computed(
    () => this._usuario()?.debeCambiarContrasena ?? false,
  );

  /** Iniciales para el avatar, p. ej. "Ana Maria Yepez" -> "AY". */
  readonly iniciales = computed(() => {
    const partes = this.nombre().trim().split(/\s+/).filter(Boolean);
    if (partes.length === 0) return '?';
    if (partes.length === 1) return partes[0]!.slice(0, 2).toUpperCase();
    return (partes[0]![0]! + partes[partes.length - 1]![0]!).toUpperCase();
  });

  get tokenAcceso(): string | null {
    return this._tokenAcceso();
  }

  get tokenRefresco(): string | null {
    return this._tokenRefresco();
  }

  // ------------------------------------------------------------- consultas
  /**
   * Unico predicado de autorizacion de la interfaz.
   *
   * Se pregunta por permiso, nunca por rol —la misma regla que aplica el
   * backend—. Asi, agregar un rol no obliga a tocar ninguna plantilla.
   */
  puede(permiso: Permiso): boolean {
    return this._usuario()?.esSuperusuario === true || this.permisos().has(permiso);
  }

  puedeAlguno(...permisos: readonly Permiso[]): boolean {
    return permisos.some((p) => this.puede(p));
  }

  puedeTodo(...permisos: readonly Permiso[]): boolean {
    return permisos.every((p) => this.puede(p));
  }

  // ------------------------------------------------------------- mutaciones
  /** Operador para encadenar tras una llamada de acceso. */
  guardarSesion() {
    return (fuente: Observable<Sesion>): Observable<Sesion> =>
      fuente.pipe(tap((sesion) => this.establecer(sesion)));
  }

  establecer(sesion: Sesion): void {
    this._usuario.set(sesion.usuario);
    this._tokenAcceso.set(sesion.tokens.acceso);
    this._tokenRefresco.set(sesion.tokens.refresco);

    this.escribir(CLAVE_ACCESO, sesion.tokens.acceso);
    this.escribir(CLAVE_REFRESCO, sesion.tokens.refresco);
    this.escribir(CLAVE_USUARIO, JSON.stringify(sesion.usuario));
  }

  /** Refresca los datos del usuario sin tocar los tokens. */
  actualizarUsuario(usuario: Usuario): void {
    this._usuario.set(usuario);
    this.escribir(CLAVE_USUARIO, JSON.stringify(usuario));
  }

  marcarCargando(valor: boolean): void {
    this._cargando.set(valor);
  }

  /** Borra la sesion local. No llama a la API. */
  limpiar(): void {
    this._usuario.set(null);
    this._tokenAcceso.set(null);
    this._tokenRefresco.set(null);
    for (const clave of [CLAVE_ACCESO, CLAVE_REFRESCO, CLAVE_USUARIO]) {
      this.borrar(clave);
    }
  }

  /** Cierra la sesion y envia al acceso, recordando a donde volver. */
  expirar(rutaDeRetorno?: string): void {
    this.limpiar();
    void this.router.navigate(['/acceso'], {
      queryParams: rutaDeRetorno ? { retorno: rutaDeRetorno } : undefined,
    });
  }

  // ------------------------------------------------------- almacenamiento
  private leerUsuarioGuardado(): Usuario | null {
    const crudo = this.leer(CLAVE_USUARIO);
    if (!crudo) return null;
    try {
      return JSON.parse(crudo) as Usuario;
    } catch {
      // Dato corrupto: se descarta en silencio y se pedira acceso de nuevo.
      this.borrar(CLAVE_USUARIO);
      return null;
    }
  }

  private leer(clave: string): string | null {
    try {
      return localStorage.getItem(clave);
    } catch {
      // Modo privado o almacenamiento bloqueado: la sesion vive solo en memoria.
      return null;
    }
  }

  private escribir(clave: string, valor: string): void {
    try {
      localStorage.setItem(clave, valor);
    } catch {
      // Sin persistencia; la sesion sigue siendo valida en esta pestana.
    }
  }

  private borrar(clave: string): void {
    try {
      localStorage.removeItem(clave);
    } catch {
      // Nada que hacer.
    }
  }
}
