import { ChangeDetectionStrategy, Component, ElementRef, HostListener, inject, input, model, signal } from '@angular/core';

import type { PeriodoConFilas } from '@domain/modelos';

/**
 * Selector de periodos como desplegable con chips, no como rejilla de
 * botones por semestre.
 *
 * Vive aparte de `SelectorGruposComponent` —que usan `/distributivo/tablero`
 * y `/distributivo/resumenes`— porque el Tablero Docente pidió explícitamente
 * este otro aspecto visual; cambiar el componente compartido habría alterado
 * esas dos pantallas sin que nadie lo pidiera.
 */
@Component({
  selector: 'ute-selector-periodos-combo',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './selector-periodos-combo.component.html',
  styleUrl: './selector-periodos-combo.component.scss',
})
export class SelectorPeriodosComboComponent {
  private readonly elementRef = inject(ElementRef<HTMLElement>);

  readonly etiqueta = input('Período(s)');
  readonly periodos = input.required<readonly PeriodoConFilas[]>();
  readonly seleccion = model<readonly string[]>([]);

  protected readonly abierto = signal(false);

  protected alternarPanel(): void {
    this.abierto.update((a) => !a);
  }

  /** Cierra al clicar fuera del componente, como cualquier desplegable. */
  @HostListener('document:click', ['$event'])
  protected clicFuera(evento: MouseEvent): void {
    if (!this.elementRef.nativeElement.contains(evento.target as Node)) {
      this.abierto.set(false);
    }
  }

  @HostListener('document:keydown.escape')
  protected teclaEscape(): void {
    this.abierto.set(false);
  }

  protected estaSeleccionado(id: string): boolean {
    return this.seleccion().includes(id);
  }

  protected alternarPeriodo(id: string): void {
    this.seleccion.update((actual) =>
      actual.includes(id) ? actual.filter((x) => x !== id) : [...actual, id],
    );
  }

  /** Quita un periodo desde el chip, sin que el clic tambien abra/cierre el panel. */
  protected quitar(id: string, evento: Event): void {
    evento.stopPropagation();
    this.seleccion.update((actual) => actual.filter((x) => x !== id));
  }

  protected limpiar(evento: Event): void {
    evento.stopPropagation();
    this.seleccion.set([]);
  }

  protected etiquetaDe(id: string): string {
    const p = this.periodos().find((x) => x.id === id);
    return p ? `${p.codigo} - ${p.nombre}` : id;
  }
}
