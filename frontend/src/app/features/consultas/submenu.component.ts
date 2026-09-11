import { ChangeDetectionStrategy, Component } from '@angular/core';
import { RouterLink, RouterLinkActive } from '@angular/router';

/** Navegacion entre las tres vistas del modulo de consultas. */
@Component({
  selector: 'ute-submenu-consultas',
  standalone: true,
  imports: [RouterLink, RouterLinkActive],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <nav class="submenu no-imprimir" aria-label="Secciones de consultas">
      <a routerLink="/consultas/jobs" routerLinkActive="submenu__enlace--activo" class="submenu__enlace">
        Campanas
      </a>
      <a routerLink="/consultas/logs" routerLinkActive="submenu__enlace--activo" class="submenu__enlace">
        Historico
      </a>
      <a
        routerLink="/consultas/planificador"
        routerLinkActive="submenu__enlace--activo"
        class="submenu__enlace"
      >
        Planificador
      </a>
    </nav>
  `,
  styles: [
    `
      .submenu {
        display: flex;
        gap: 0.25rem;
        margin-bottom: 1rem;
        border-bottom: 1px solid var(--borde);
      }
      .submenu__enlace {
        padding: 0.5rem 0.85rem;
        font-size: 0.85rem;
        font-weight: 500;
        color: var(--texto-suave);
        border-bottom: 2px solid transparent;
        text-decoration: none;
      }
      .submenu__enlace:hover { color: var(--texto); text-decoration: none; }
      .submenu__enlace--activo {
        color: var(--azul-800);
        font-weight: 600;
        border-bottom-color: var(--azul-800);
      }
    `,
  ],
})
export class SubmenuConsultasComponent {}
