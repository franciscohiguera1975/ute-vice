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

  private emitir(tipo: TipoAviso, mensaje: string, detalle?: string): void {
    const aviso: Aviso = { id: this.siguienteId++, tipo, mensaje, detalle };
    this._avisos.update((lista) => [...lista, aviso]);
    setTimeout(() => this.descartar(aviso.id), DURACION_MS[tipo]);
  }
}
