import { DecimalPipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, input, model, output } from '@angular/core';

import type { OpcionSelector, PeriodoConFilas } from '@domain/modelos';

/** Un semestre con todos sus periodos: lo que se marca de un clic. */
interface Semestre {
  readonly clave: string;
  readonly periodos: readonly PeriodoConFilas[];
  readonly filas: number;
}

/** Cual de los dos grupos se esta editando. */
export type Grupo = 'a' | 'b';

/**
 * Elige los dos grupos de periodos que se comparan.
 *
 * Vive aparte porque lo usan el tablero y los resumenes, y tienen que
 * comportarse igual: si una pantalla propusiera «2026-2 POSGRADO» y la otra
 * «2026-2 completo», sus cifras no cuadrarian y nadie sabria cual creer.
 *
 * Se eligen **grupos** y no periodos sueltos porque un semestre son varios:
 * `2026-1` es tecnologia, grado y posgrado, mas sus interciclos. Marcar el
 * semestre entero es un clic; el detalle permite afinar periodo a periodo.
 */
@Component({
  selector: 'ute-selector-grupos',
  standalone: true,
  imports: [DecimalPipe],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './selector-grupos.component.html',
  styleUrl: './selector-grupos.component.scss',
})
export class SelectorGruposComponent {
  readonly periodos = input.required<readonly PeriodoConFilas[]>();

  /** Etiquetas de cada grupo. El tablero y los resumenes los nombran distinto. */
  readonly etiquetaA = input('Grupo 1 · referencia');
  readonly etiquetaB = input('Grupo 2 · comparado');

  readonly grupoA = model<readonly string[]>([]);
  readonly grupoB = model<readonly string[]>([]);

  /**
   * Catalogo de dedicaciones para filtrar, o vacio para no ofrecer el filtro.
   *
   * Es un filtro sobre las dos comparaciones a la vez, no por grupo: comparar
   * «Grupo 1 · TIEMPO COMPLETO» contra «Grupo 2 · MEDIO TIEMPO» no tiene
   * sentido, asi que hay una sola lista de dedicaciones marcadas.
   */
  readonly dedicaciones = input<readonly OpcionSelector[]>([]);
  readonly dedicacionIds = model<readonly string[]>([]);

  /** Se emite al pulsar «Comparar»; la pantalla decide que hacer. */
  readonly comparar = output<void>();

  protected readonly GRUPOS: readonly Grupo[] = ['a', 'b'];

  protected readonly semestres = computed<readonly Semestre[]>(() => {
    const por = new Map<string, PeriodoConFilas[]>();
    for (const p of this.periodos()) {
      // Sin semestre en los atributos, se deriva del codigo: `2026-2` sale de
      // `262651` como `20` + `26` + `-` + `2`.
      const clave = p.semestre || `20${p.codigo.slice(0, 2)}-${p.codigo.slice(2, 3)}`;
      por.set(clave, [...(por.get(clave) ?? []), p]);
    }
    return [...por.entries()]
      .map(([clave, periodos]) => ({
        clave,
        periodos,
        filas: periodos.reduce((suma, p) => suma + p.filas, 0),
      }))
      .sort((x, y) => y.clave.localeCompare(x.clave));
  });

  protected etiqueta(grupo: Grupo): string {
    return grupo === 'a' ? this.etiquetaA() : this.etiquetaB();
  }

  private senal(grupo: Grupo) {
    return grupo === 'a' ? this.grupoA : this.grupoB;
  }

  protected seleccionado(grupo: Grupo, id: string): boolean {
    return this.senal(grupo)().includes(id);
  }

  protected semestreCompleto(grupo: Grupo, semestre: Semestre): boolean {
    return semestre.periodos.every((p) => this.seleccionado(grupo, p.id));
  }

  protected alternarSemestre(grupo: Grupo, semestre: Semestre): void {
    const ids = semestre.periodos.map((p) => p.id);
    const quitar = this.semestreCompleto(grupo, semestre);
    this.senal(grupo).update((actual) =>
      quitar ? actual.filter((id) => !ids.includes(id)) : [...new Set([...actual, ...ids])],
    );
  }

  protected alternarPeriodo(grupo: Grupo, id: string): void {
    this.senal(grupo).update((actual) =>
      actual.includes(id) ? actual.filter((x) => x !== id) : [...actual, id],
    );
  }

  protected limpiar(grupo: Grupo): void {
    this.senal(grupo).set([]);
  }

  protected dedicacionSeleccionada(id: string): boolean {
    return this.dedicacionIds().includes(id);
  }

  protected alternarDedicacion(id: string): void {
    this.dedicacionIds.update((actual) =>
      actual.includes(id) ? actual.filter((x) => x !== id) : [...actual, id],
    );
  }

  protected readonly puedeComparar = computed(
    () => this.grupoA().length > 0 || this.grupoB().length > 0,
  );
}
