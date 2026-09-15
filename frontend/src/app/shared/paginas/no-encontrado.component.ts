import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { RouterLink } from '@angular/router';

import { rutaDeInicio } from '@core/secciones';
import { SesionStore } from '@core/sesion.store';

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
      <a [routerLink]="inicio" class="btn btn--primario">Volver al inicio</a>
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
export class NoEncontradoComponent {
  private readonly sesion = inject(SesionStore);

  /**
   * A donde vuelve el boton.
   *
   * No al tablero: quien no tiene `dashboard:ver` acabaria rebotando. Sin
   * sesion, al acceso.
   */
  protected readonly inicio = this.sesion.autenticado()
    ? rutaDeInicio(this.sesion)
    : '/acceso';
}
