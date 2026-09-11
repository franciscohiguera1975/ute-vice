import { ChangeDetectionStrategy, Component, input } from '@angular/core';

import type { Tono } from '@domain/modelos';

/** Etiqueta compacta de estado. Un solo componente para toda la aplicacion. */
@Component({
  selector: 'ute-insignia',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <span class="insignia" [class]="'insignia--' + tono()" [title]="titulo() || texto()">
      {{ texto() }}
    </span>
  `,
  styles: [
    `
      .insignia {
        display: inline-flex;
        align-items: center;
        padding: 0.15rem 0.5rem;
        font-size: 0.72rem;
        font-weight: 600;
        letter-spacing: 0.01em;
        border-radius: 99px;
        white-space: nowrap;
      }
      .insignia--exito { color: var(--exito); background: var(--exito-suave); }
      .insignia--error { color: var(--error); background: var(--error-suave); }
      .insignia--aviso { color: var(--aviso); background: var(--aviso-suave); }
      .insignia--info { color: var(--info); background: var(--info-suave); }
      .insignia--neutro { color: var(--texto-suave); background: var(--borde); }
    `,
  ],
})
export class InsigniaComponent {
  readonly texto = input.required<string>();
  readonly tono = input<Tono>('neutro');
  readonly titulo = input<string>('');
}
