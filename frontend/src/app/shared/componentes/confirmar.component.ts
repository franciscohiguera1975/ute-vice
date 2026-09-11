import { ChangeDetectionStrategy, Component, input, output } from '@angular/core';

/**
 * Dialogo de confirmacion para acciones irreversibles.
 *
 * Se usa el elemento nativo `<dialog>`: aporta gratis el foco atrapado, el
 * cierre con Escape y el rol de dialogo modal, que replicar a mano rara vez
 * sale bien.
 */
@Component({
  selector: 'ute-confirmar',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (abierto()) {
      <div class="velo" (click)="cancelar.emit()">
        <div
          class="dialogo"
          role="alertdialog"
          aria-modal="true"
          [attr.aria-label]="titulo()"
          (click)="$event.stopPropagation()"
        >
          <h2 class="dialogo__titulo">{{ titulo() }}</h2>
          <p class="dialogo__mensaje">{{ mensaje() }}</p>
          @if (advertencia()) {
            <p class="dialogo__advertencia">{{ advertencia() }}</p>
          }
          <div class="dialogo__acciones">
            <button type="button" class="btn btn--secundario" (click)="cancelar.emit()">
              {{ textoCancelar() }}
            </button>
            <button
              type="button"
              class="btn"
              [class.btn--peligro]="peligroso()"
              [class.btn--primario]="!peligroso()"
              (click)="confirmar.emit()"
            >
              {{ textoConfirmar() }}
            </button>
          </div>
        </div>
      </div>
    }
  `,
  styles: [
    `
      .velo {
        position: fixed;
        inset: 0;
        z-index: 900;
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 1rem;
        background: rgb(12 16 26 / 55%);
        animation: aparecer 120ms ease-out;
      }

      .dialogo {
        width: min(28rem, 100%);
        padding: 1.35rem;
        background: var(--superficie);
        border-radius: var(--radio-lg);
        box-shadow: var(--sombra-3);
      }

      .dialogo__titulo { margin: 0 0 0.5rem; font-size: 1.05rem; }
      .dialogo__mensaje { margin: 0 0 0.75rem; color: var(--texto-suave); font-size: 0.875rem; }

      .dialogo__advertencia {
        margin: 0 0 1rem;
        padding: 0.55rem 0.7rem;
        font-size: 0.8rem;
        color: var(--aviso);
        background: var(--aviso-suave);
        border-radius: var(--radio);
      }

      .dialogo__acciones {
        display: flex;
        justify-content: flex-end;
        gap: 0.6rem;
        margin-top: 1.25rem;
      }

      @keyframes aparecer { from { opacity: 0; } to { opacity: 1; } }
    `,
  ],
})
export class ConfirmarComponent {
  readonly abierto = input(false);
  readonly titulo = input('Confirmar operacion');
  readonly mensaje = input.required<string>();
  readonly advertencia = input('');
  readonly textoConfirmar = input('Confirmar');
  readonly textoCancelar = input('Cancelar');
  readonly peligroso = input(false);

  readonly confirmar = output<void>();
  readonly cancelar = output<void>();
}
