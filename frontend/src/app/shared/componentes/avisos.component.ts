import { ChangeDetectionStrategy, Component, inject } from '@angular/core';

import { NotificacionesService } from '@core/notificaciones.service';

/**
 * Pila de avisos efimeros.
 *
 * `role="status"` con `aria-live="polite"` hace que un lector de pantalla
 * anuncie los avisos sin interrumpir lo que el usuario este haciendo.
 */
@Component({
  selector: 'ute-avisos',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="avisos" role="status" aria-live="polite" aria-atomic="false">
      @for (aviso of notificaciones.avisos(); track aviso.id) {
        <div class="aviso" [class]="'aviso--' + aviso.tipo">
          <span class="aviso__icono" aria-hidden="true">{{ icono(aviso.tipo) }}</span>
          <div class="aviso__texto">
            <p class="aviso__mensaje">{{ aviso.mensaje }}</p>
            @if (aviso.detalle) {
              <p class="aviso__detalle">{{ aviso.detalle }}</p>
            }
          </div>
          <button
            type="button"
            class="aviso__cerrar"
            (click)="notificaciones.descartar(aviso.id)"
            aria-label="Descartar aviso"
          >
            ×
          </button>
        </div>
      }
    </div>
  `,
  styles: [
    `
      .avisos {
        position: fixed;
        right: 1rem;
        bottom: 1rem;
        z-index: 1000;
        display: flex;
        flex-direction: column;
        gap: 0.6rem;
        max-width: min(26rem, calc(100vw - 2rem));
        pointer-events: none;
      }

      .aviso {
        display: flex;
        align-items: flex-start;
        gap: 0.65rem;
        padding: 0.75rem 0.9rem;
        background: var(--superficie);
        border: 1px solid var(--borde);
        border-left: 4px solid var(--texto-tenue);
        border-radius: var(--radio);
        box-shadow: var(--sombra-3);
        pointer-events: auto;
        animation: entrar 200ms ease-out;
      }

      .aviso--exito { border-left-color: var(--exito); }
      .aviso--error { border-left-color: var(--error); }
      .aviso--aviso { border-left-color: var(--aviso); }
      .aviso--info { border-left-color: var(--azul-700); }

      .aviso__icono { flex-shrink: 0; font-size: 1rem; line-height: 1.35; }
      .aviso__texto { flex: 1; min-width: 0; }

      .aviso__mensaje {
        margin: 0;
        font-size: 0.85rem;
        font-weight: 500;
        overflow-wrap: anywhere;
      }

      .aviso__detalle {
        margin: 0.2rem 0 0;
        font-size: 0.775rem;
        color: var(--texto-suave);
        overflow-wrap: anywhere;
      }

      .aviso__cerrar {
        flex-shrink: 0;
        padding: 0 0.15rem;
        font-size: 1.15rem;
        line-height: 1;
        color: var(--texto-tenue);
        background: none;
        border: none;
        cursor: pointer;
      }
      .aviso__cerrar:hover { color: var(--texto); }

      @keyframes entrar {
        from { opacity: 0; transform: translateY(8px); }
        to { opacity: 1; transform: translateY(0); }
      }
    `,
  ],
})
export class AvisosComponent {
  protected readonly notificaciones = inject(NotificacionesService);

  protected icono(tipo: string): string {
    return { exito: '✓', error: '✕', aviso: '!', info: 'i' }[tipo] ?? 'i';
  }
}
