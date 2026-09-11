import { Injectable, inject, signal } from '@angular/core';
import { forkJoin } from 'rxjs';

import { TipoCatalogo, type OpcionSelector } from '@domain/modelos';
import { RepositorioCatalogos } from '@domain/puertos';

/**
 * Cache de los catalogos para poblar los selectores.
 *
 * Se cargan una sola vez por sesion de navegacion: son doce listas que cambian
 * poco y que varias pantallas necesitan a la vez. Sin esta cache, abrir el
 * formulario del distributivo dispararia doce peticiones cada vez.
 */
@Injectable({ providedIn: 'root' })
export class CatalogosStore {
  private readonly repositorio = inject(RepositorioCatalogos);

  private readonly _opciones = signal<Record<string, readonly OpcionSelector[]>>({});
  private readonly _cargando = signal(false);
  private cargado = false;

  readonly opciones = this._opciones.asReadonly();
  readonly cargando = this._cargando.asReadonly();

  /** Devuelve un catálogo ya cargado. Vacío si aún no llegó. */
  de(tipo: TipoCatalogo): readonly OpcionSelector[] {
    return this._opciones()[tipo] ?? [];
  }

  nombreDe(tipo: TipoCatalogo, id: string | null | undefined): string {
    if (!id) return '';
    return this.de(tipo).find((o) => o.id === id)?.nombre ?? '';
  }

  cargar(forzar = false): void {
    if (this.cargado && !forzar) return;
    this.cargado = true;
    this._cargando.set(true);

    const tipos = Object.values(TipoCatalogo);
    forkJoin(
      Object.fromEntries(tipos.map((t) => [t, this.repositorio.opciones(t)])),
    ).subscribe({
      next: (resultado) => {
        this._opciones.set(resultado as Record<string, readonly OpcionSelector[]>);
        this._cargando.set(false);
      },
      error: () => {
        // Se permite reintentar: dejar `cargado` en true bloquearia la pantalla
        // si la primera carga falla por un corte momentáneo.
        this.cargado = false;
        this._cargando.set(false);
      },
    });
  }
}
