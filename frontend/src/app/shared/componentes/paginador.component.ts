import { DecimalPipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, input, output } from '@angular/core';

/** Navegacion entre paginas de un listado. */
@Component({
  selector: 'ute-paginador',
  standalone: true,
  imports: [DecimalPipe],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <nav class="paginador" aria-label="Paginacion de resultados">
      <p class="paginador__resumen texto-sm texto-suave">
        @if (total() === 0) {
          Sin resultados
        } @else {
          {{ desde() }}–{{ hasta() }} de {{ total() | number }}
        }
      </p>

      <div class="fila hueco-sm">
        <label class="fila hueco-xs texto-sm texto-suave">
          <span>Por pagina</span>
          <select
            class="paginador__tamano"
            [value]="tamano()"
            (change)="cambiarTamano($event)"
            aria-label="Registros por pagina"
          >
            @for (opcion of opcionesTamano; track opcion) {
              <option [value]="opcion">{{ opcion }}</option>
            }
          </select>
        </label>

        <div class="fila hueco-xs">
          <button
            type="button"
            class="btn btn--secundario btn--sm"
            [disabled]="pagina() <= 1"
            (click)="ir(pagina() - 1)"
          >
            Anterior
          </button>
          <span class="texto-sm texto-suave paginador__posicion">
            {{ pagina() }} / {{ totalPaginas() || 1 }}
          </span>
          <button
            type="button"
            class="btn btn--secundario btn--sm"
            [disabled]="pagina() >= totalPaginas()"
            (click)="ir(pagina() + 1)"
          >
            Siguiente
          </button>
        </div>
      </div>
    </nav>
  `,
  styles: [
    `
      .paginador {
        display: flex;
        align-items: center;
        justify-content: space-between;
        flex-wrap: wrap;
        gap: 0.75rem;
        padding: 0.7rem 1rem;
        border-top: 1px solid var(--borde);
      }
      .paginador__resumen { margin: 0; }
      .paginador__tamano { width: auto; padding: 0.2rem 0.4rem; font-size: 0.8rem; }
      .paginador__posicion { min-width: 3.5rem; text-align: center; }
    `,
  ],
})
export class PaginadorComponent {
  readonly pagina = input.required<number>();
  readonly tamano = input.required<number>();
  readonly total = input.required<number>();
  readonly totalPaginas = input.required<number>();

  readonly paginaCambiada = output<number>();
  readonly tamanoCambiado = output<number>();

  protected readonly opcionesTamano = [10, 25, 50, 100];

  protected readonly desde = computed(() =>
    this.total() === 0 ? 0 : (this.pagina() - 1) * this.tamano() + 1,
  );
  protected readonly hasta = computed(() =>
    Math.min(this.pagina() * this.tamano(), this.total()),
  );

  protected ir(pagina: number): void {
    if (pagina >= 1 && pagina <= this.totalPaginas()) {
      this.paginaCambiada.emit(pagina);
    }
  }

  protected cambiarTamano(evento: Event): void {
    this.tamanoCambiado.emit(Number((evento.target as HTMLSelectElement).value));
  }
}
