import { ChangeDetectionStrategy, Component } from '@angular/core';
import { RouterLink } from '@angular/router';

@Component({
  selector: 'ute-no-encontrado',
  standalone: true,
  imports: [RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="pagina">
      <p class="codigo">404</p>
      <h1>Pagina no encontrada</h1>
      <p class="texto-suave">
        La direccion que intenta abrir no existe o fue movida.
      </p>
      <a routerLink="/tablero" class="btn btn--primario">Ir al tablero</a>
    </div>
  `,
  styles: [
    `
      .pagina {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        gap: 0.5rem;
        min-height: 100vh;
        padding: 2rem;
        text-align: center;
      }
      .codigo {
        margin: 0;
        font-size: 3.5rem;
        font-weight: 700;
        color: var(--azul-100);
        line-height: 1;
      }
      .btn { margin-top: 1rem; }
    `,
  ],
})
export class NoEncontradoComponent {}
