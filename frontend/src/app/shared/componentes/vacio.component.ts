import { ChangeDetectionStrategy, Component, input } from '@angular/core';

/**
 * Estado vacio.
 *
 * Distingue "no hay datos todavia" de "el filtro no encontro nada", que son
 * situaciones distintas y requieren acciones distintas del usuario.
 */
@Component({
  selector: 'ute-vacio',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="vacio">
      <div class="vacio__icono" aria-hidden="true">{{ icono() }}</div>
      <p class="vacio__titulo">{{ titulo() }}</p>
      @if (descripcion()) {
        <p class="vacio__descripcion">{{ descripcion() }}</p>
      }
      <ng-content />
    </div>
  `,
  styles: [
    `
      .vacio {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 0.4rem;
        padding: 3rem 1.5rem;
        text-align: center;
      }
      .vacio__icono { font-size: 2rem; opacity: 0.35; }
      .vacio__titulo { margin: 0; font-weight: 600; color: var(--texto); }
      .vacio__descripcion {
        margin: 0;
        max-width: 30rem;
        font-size: 0.85rem;
        color: var(--texto-suave);
      }
    `,
  ],
})
export class VacioComponent {
  readonly titulo = input.required<string>();
  readonly descripcion = input('');
  readonly icono = input('◎');
}
