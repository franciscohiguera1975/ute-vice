import { ChangeDetectionStrategy, Component, computed, inject } from '@angular/core';
import { RouterLink } from '@angular/router';

import { SesionStore } from '@core/sesion.store';
import { InsigniaComponent } from '@shared/componentes/insignia.component';
import { FechaLocalPipe } from '@shared/pipes/formato.pipe';

@Component({
  selector: 'ute-perfil',
  standalone: true,
  imports: [RouterLink, InsigniaComponent, FechaLocalPipe],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <header class="encabezado">
      <h1>Mi perfil</h1>
      <p class="texto-sm texto-suave">Datos de su cuenta y permisos efectivos</p>
    </header>

    @if (sesion.usuario(); as usuario) {
      <div class="rejilla disposicion">
        <section class="tarjeta">
          <div class="tarjeta__cabecera">
            <h2 class="tarjeta__titulo">Cuenta</h2>
          </div>
          <dl class="datos">
            <div class="datos__par"><dt>Nombre</dt><dd>{{ usuario.nombreCompleto }}</dd></div>
            <div class="datos__par"><dt>Correo</dt><dd>{{ usuario.email }}</dd></div>
            <div class="datos__par">
              <dt>Metodo de acceso</dt>
              <dd><ute-insignia [texto]="usuario.proveedor" tono="neutro" /></dd>
            </div>
            <div class="datos__par">
              <dt>Ultimo acceso</dt>
              <dd>{{ usuario.ultimoAcceso | fechaLocal: true }}</dd>
            </div>
            <div class="datos__par">
              <dt>Cuenta creada</dt>
              <dd>{{ usuario.creadoEn | fechaLocal }}</dd>
            </div>
            <div class="datos__par">
              <dt>Roles</dt>
              <dd class="fila hueco-xs envolver">
                @for (rol of usuario.roles; track rol.codigo) {
                  <ute-insignia [texto]="rol.nombre" tono="info" [titulo]="rol.descripcion" />
                }
              </dd>
            </div>
          </dl>

          @if (usuario.proveedor === 'LOCAL') {
            <div class="tarjeta__cuerpo">
              <a routerLink="/perfil/contrasena" class="btn btn--secundario btn--bloque">
                Cambiar contrasena
              </a>
            </div>
          } @else {
            <div class="tarjeta__cuerpo">
              <p class="texto-sm texto-suave">
                Su cuenta se autentica mediante {{ usuario.proveedor }}. La
                contrasena se gestiona en ese sistema, no aqui.
              </p>
            </div>
          }
        </section>

        <section class="tarjeta">
          <div class="tarjeta__cabecera">
            <h2 class="tarjeta__titulo">Permisos efectivos</h2>
            <span class="texto-xs texto-tenue">{{ usuario.permisos.length }}</span>
          </div>
          <div class="tarjeta__cuerpo">
            <p class="texto-sm texto-suave">
              Es la union de los permisos de todos sus roles. La interfaz oculta
              lo que no puede usar, y el servidor lo verifica en cada operacion.
            </p>
            <ul class="permisos">
              @for (grupo of porModulo(); track grupo.modulo) {
                <li class="permisos__grupo">
                  <span class="permisos__modulo">{{ grupo.modulo }}</span>
                  <span class="fila hueco-xs envolver">
                    @for (accion of grupo.acciones; track accion) {
                      <code class="permisos__accion">{{ accion }}</code>
                    }
                  </span>
                </li>
              }
            </ul>
          </div>
        </section>
      </div>
    }
  `,
  styles: [
    `
      .encabezado { margin-bottom: 1.25rem; }
      .disposicion { grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); align-items: start; }

      .datos { margin: 0; padding: 0.5rem 0; }
      .datos__par {
        display: grid;
        grid-template-columns: 9rem 1fr;
        gap: 0.75rem;
        padding: 0.4rem 1.15rem;
        font-size: 0.85rem;
      }
      .datos dt { color: var(--texto-tenue); }
      .datos dd { margin: 0; overflow-wrap: anywhere; }

      .permisos { list-style: none; margin: 0.75rem 0 0; padding: 0; }
      .permisos__grupo {
        display: grid;
        grid-template-columns: 7rem 1fr;
        gap: 0.5rem;
        padding: 0.35rem 0;
        border-bottom: 1px solid var(--borde);
      }
      .permisos__grupo:last-child { border-bottom: none; }
      .permisos__modulo {
        font-size: 0.75rem;
        font-weight: 600;
        text-transform: capitalize;
        color: var(--texto-suave);
      }
      .permisos__accion {
        padding: 0.1rem 0.35rem;
        font-size: 0.72rem;
        background: var(--superficie-2);
        border: 1px solid var(--borde);
        border-radius: var(--radio-sm);
      }

      @media (width <= 640px) {
        .datos__par,
        .permisos__grupo { grid-template-columns: 1fr; gap: 0.15rem; }
      }
    `,
  ],
})
export class PerfilComponent {
  protected readonly sesion = inject(SesionStore);

  /** Permisos agrupados por modulo, para leerlos de un vistazo. */
  protected readonly porModulo = computed(() => {
    const grupos = new Map<string, string[]>();
    for (const permiso of this.sesion.usuario()?.permisos ?? []) {
      const [modulo, accion] = permiso.split(':');
      const lista = grupos.get(modulo ?? '') ?? [];
      lista.push(accion ?? permiso);
      grupos.set(modulo ?? '', lista);
    }
    return [...grupos.entries()].map(([modulo, acciones]) => ({ modulo, acciones }));
  });
}
