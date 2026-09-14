/**
 * Avisos efimeros al usuario.
 *
 * Se implementa con signals y un identificador incremental para que la lista
 * sea inmutable y el renderizado con `@for` pueda seguir cada aviso por su
 * clave.
 */

import { Injectable, signal } from '@angular/core';

export type TipoAviso = 'exito' | 'error' | 'aviso' | 'info';

export interface Aviso {
  readonly id: number;
  readonly tipo: TipoAviso;
  readonly mensaje: string;
  readonly detalle?: string;
}

/** Los errores permanecen mas tiempo: suelen requerir leer y actuar. */
const DURACION_MS: Record<TipoAviso, number> = {
  exito: 4000,
  info: 5000,
  aviso: 7000,
  error: 10000,
};

@Injectable({ providedIn: 'root' })
export class NotificacionesService {
  private siguienteId = 1;
  /** Momento hasta el que se descartan errores y avisos. */
  private silencioHasta = 0;
  private readonly _avisos = signal<readonly Aviso[]>([]);
  readonly avisos = this._avisos.asReadonly();

  exito(mensaje: string, detalle?: string): void {
    this.emitir('exito', mensaje, detalle);
  }

  error(mensaje: string, detalle?: string): void {
    this.emitir('error', mensaje, detalle);
  }

  aviso(mensaje: string, detalle?: string): void {
    this.emitir('aviso', mensaje, detalle);
  }

  info(mensaje: string, detalle?: string): void {
    this.emitir('info', mensaje, detalle);
  }

  descartar(id: number): void {
    this._avisos.update((lista) => lista.filter((a) => a.id !== id));
  }

  limpiar(): void {
    this._avisos.set([]);
  }

  /**
   * Deja un unico aviso en pantalla y descarta los fallos que lleguen despues.
   *
   * Hace falta cuando una sola causa —la sesion que caduca— tumba a la vez
   * todas las peticiones en vuelo: sin esto el usuario veia un aviso por cada
   * pantalla abierta, cada uno con su texto tecnico, y ninguno le decia que
   * hacer.
   */
  anunciarYSilenciar(
    tipo: TipoAviso,
    mensaje: string,
    detalle?: string,
    ms = 4000,
  ): void {
    this.limpiar();
    this.silencioHasta = Date.now() + ms;
    this.emitir(tipo, mensaje, detalle, true);
  }

  private emitir(
    tipo: TipoAviso,
    mensaje: string,
    detalle?: string,
    forzar = false,
  ): void {
    // Solo se callan los fallos: un «guardado» o un «listo» que ocurra en esa
    // ventana sigue siendo informacion util y no ruido derivado del mismo
    // problema.
    const esFallo = tipo === 'error' || tipo === 'aviso';
    if (!forzar && esFallo && Date.now() < this.silencioHasta) {
      return;
    }
    const aviso: Aviso = { id: this.siguienteId++, tipo, mensaje, detalle };
    this._avisos.update((lista) => [...lista, aviso]);
    setTimeout(() => this.descartar(aviso.id), DURACION_MS[tipo]);
  }
}
