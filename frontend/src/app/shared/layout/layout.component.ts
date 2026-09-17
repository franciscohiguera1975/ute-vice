import { ChangeDetectionStrategy, Component, HostListener, inject, signal } from '@angular/core';
import { NavigationEnd, Router, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { filter } from 'rxjs';

import { NotificacionesService } from '@core/notificaciones.service';
import { SesionStore } from '@core/sesion.store';
import { RepositorioAutenticacion } from '@domain/puertos';
import { SECCIONES, type Seccion } from '@core/secciones';
import { PermisoDirective } from '@shared/directivas/permiso.directive';


@Component({
  selector: 'ute-layout',
  standalone: true,
  imports: [RouterOutlet, RouterLink, RouterLinkActive, PermisoDirective],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './layout.component.html',
  styleUrl: './layout.component.scss',
})
export class LayoutComponent {
  protected readonly sesion = inject(SesionStore);
  private readonly autenticacion = inject(RepositorioAutenticacion);
  private readonly notificaciones = inject(NotificacionesService);
  private readonly router = inject(Router);

  protected readonly lateralAbierto = signal(false);
  protected readonly menuAbierto = signal(false);
  protected readonly temaOscuro = signal(this.leerTema());

  /**
   * Secciones del menu, con los permisos que habilitan cada una; la directiva
   * `*utePermiso` oculta las que no correspondan.
   *
   * La lista vive en `@core/secciones` y no aqui: de ella sale tambien la ruta
   * a la que aterriza cada usuario, y tenerla duplicada fue lo que dejo la
   * aplicacion en bucle para el primer rol sin `dashboard:ver`.
   */
  protected readonly secciones = SECCIONES;

  /** Ruta del grupo desplegado en la barra horizontal; vacia si ninguno. */
  protected readonly grupoAbierto = signal('');

  constructor() {
    // Al navegar se cierra el desplegable: si no, queda abierto encima de la
    // pantalla a la que se acaba de llegar.
    this.router.events
      .pipe(
        filter((e) => e instanceof NavigationEnd),
        takeUntilDestroyed(),
      )
      .subscribe(() => this.grupoAbierto.set(''));
  }

  protected alternarGrupo(ruta: string): void {
    this.grupoAbierto.update((actual) => (actual === ruta ? '' : ruta));
  }

  protected cerrarGrupo(): void {
    this.grupoAbierto.set('');
  }

  /** Un grupo se marca activo cuando la ruta actual es la de alguno de sus hijos. */
  protected enGrupo(seccion: Seccion): boolean {
    return (seccion.hijos ?? []).some((h) => this.router.url.startsWith(h.ruta));
  }

  /** Un clic fuera cierra el desplegable, como cualquier menu del sistema. */
  @HostListener('document:click', ['$event'])
  protected clicFuera(evento: MouseEvent): void {
    if (!this.grupoAbierto()) return;
    const destino = evento.target as HTMLElement | null;
    if (!destino?.closest('.nav-h__item')) this.grupoAbierto.set('');
  }

  @HostListener('document:keydown.escape')
  protected escape(): void {
    this.grupoAbierto.set('');
  }

  protected alternarLateral(): void {
    this.lateralAbierto.update((v) => !v);
  }

  protected cerrarLateral(): void {
    this.lateralAbierto.set(false);
  }

  protected alternarMenu(): void {
    this.menuAbierto.update((v) => !v);
  }

  protected alternarTema(): void {
    const oscuro = !this.temaOscuro();
    this.temaOscuro.set(oscuro);
    document.documentElement.setAttribute('data-tema', oscuro ? 'oscuro' : 'claro');
    try {
      localStorage.setItem('ute_vice_tema', oscuro ? 'oscuro' : 'claro');
    } catch {
      // Sin persistencia: el tema dura lo que la pestana.
    }
  }

  protected salir(): void {
    const refresco = this.sesion.tokenRefresco;
    this.menuAbierto.set(false);

    // La sesion local se limpia pase lo que pase: si la llamada falla, el
    // usuario igual queda fuera en este navegador, que es lo que pidio.
    const finalizar = (): void => {
      this.sesion.limpiar();
      void this.router.navigate(['/acceso']);
      this.notificaciones.info('Sesion cerrada');
    };

    if (!refresco) {
      finalizar();
      return;
    }
    this.autenticacion.cerrarSesion(refresco).subscribe({
      next: finalizar,
      error: finalizar,
    });
  }

  private leerTema(): boolean {
    return document.documentElement.getAttribute('data-tema') === 'oscuro';
  }
}
