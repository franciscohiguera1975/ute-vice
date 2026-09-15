import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';

import { NotificacionesService } from '@core/notificaciones.service';
import { SesionStore } from '@core/sesion.store';
import { rutaDeInicio } from '@core/secciones';
import type { ErrorApi } from '@domain/modelos';
import { RepositorioAutenticacion } from '@domain/puertos';
import { CargandoComponent } from '@shared/componentes/cargando.component';

/**
 * Punto de retorno del flujo de Google.
 *
 * Google devuelve el navegador aqui con un codigo de un solo uso. El canje por
 * un token ocurre en el backend, no aqui: exige el secreto de cliente, que
 * nunca debe llegar al navegador.
 */
@Component({
  selector: 'ute-retorno-google',
  standalone: true,
  imports: [CargandoComponent, RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="retorno">
      @if (error()) {
        <h1>No fue posible completar el acceso</h1>
        <p class="texto-suave">{{ error() }}</p>
        <a routerLink="/acceso" class="btn btn--primario">Volver al acceso</a>
      } @else {
        <ute-cargando mensaje="Validando su identidad con Google…" />
      }
    </div>
  `,
  styles: [
    `
      .retorno {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        gap: 0.75rem;
        min-height: 100vh;
        padding: 2rem;
        text-align: center;
      }
    `,
  ],
})
export class RetornoGoogleComponent {
  private readonly ruta = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly autenticacion = inject(RepositorioAutenticacion);
  private readonly sesion = inject(SesionStore);
  private readonly notificaciones = inject(NotificacionesService);

  protected readonly error = signal<string | null>(null);

  constructor() {
    const parametros = this.ruta.snapshot.queryParamMap;
    const codigo = parametros.get('code');
    const rechazo = parametros.get('error');

    if (rechazo) {
      this.error.set(
        rechazo === 'access_denied'
          ? 'Se cancelo el acceso con Google.'
          : `Google devolvio un error: ${rechazo}`,
      );
      return;
    }

    if (!codigo) {
      this.error.set('Google no devolvio un codigo de autorizacion.');
      return;
    }

    this.autenticacion.completarAccesoGoogle(codigo).subscribe({
      next: (sesion) => {
        this.sesion.establecer(sesion);
        this.notificaciones.exito(`Bienvenido, ${sesion.usuario.nombreCompleto}`);
        void this.router.navigate([rutaDeInicio(this.sesion)]);
      },
      error: (fallo: ErrorApi) => this.error.set(fallo.mensaje),
    });
  }
}
