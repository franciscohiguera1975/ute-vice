import { ChangeDetectionStrategy, Component, input } from '@angular/core';

/** Indicador de carga. */
@Component({
  selector: 'ute-cargando',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="cargando" [class.cargando--compacto]="compacto()" role="status">
      <span class="cargando__giro" aria-hidden="true"></span>
      <span [class.sr-solo]="compacto()">{{ mensaje() }}</span>
    </div>
  `,
  styles: [
    `
      .cargando {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        gap: 0.75rem;
        padding: 2.5rem 1rem;
        color: var(--texto-suave);
        font-size: 0.85rem;
      }
      .cargando--compacto { flex-direction: row; padding: 0.5rem; }

      .cargando__giro {
        width: 22px;
        height: 22px;
        border: 2.5px solid var(--borde);
        border-top-color: var(--azul-700);
        border-radius: 50%;
        animation: girar 700ms linear infinite;
      }
      .cargando--compacto .cargando__giro { width: 15px; height: 15px; border-width: 2px; }

      @keyframes girar { to { transform: rotate(360deg); } }
    `,
  ],
})
export class CargandoComponent {
  readonly mensaje = input('Cargando…');
  readonly compacto = input(false);
}
