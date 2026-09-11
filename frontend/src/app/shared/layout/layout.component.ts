import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { Router, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';

import { NotificacionesService } from '@core/notificaciones.service';
import { SesionStore } from '@core/sesion.store';
import { RepositorioAutenticacion } from '@domain/puertos';
import { Permiso } from '@domain/modelos';
import { PermisoDirective } from '@shared/directivas/permiso.directive';

interface Seccion {
  readonly ruta: string;
  readonly etiqueta: string;
  readonly icono: string;
  /** Permisos que habilitan la seccion. Basta con tener uno. */
  readonly permisos: readonly Permiso[];
}

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
   * Secciones del menu.
   *
   * Cada una declara los permisos que la habilitan; la directiva `*utePermiso`
   * se encarga de ocultar las que no correspondan. Asi el menu de un usuario de
   * solo lectura no ofrece opciones que terminarian en un 403.
   */
  protected readonly secciones: readonly Seccion[] = [
    {
      ruta: '/tablero',
      etiqueta: 'Tablero',
      icono: '▤',
      permisos: [Permiso.DASHBOARD_VER],
    },
    {
      ruta: '/personas',
      etiqueta: 'Personas',
      icono: '☰',
      permisos: [Permiso.PERSONAS_LEER],
    },
    {
      ruta: '/titulos',
      etiqueta: 'Titulos',
      icono: '◈',
      permisos: [Permiso.TITULOS_LEER],
    },
    {
      ruta: '/consultas',
      etiqueta: 'Consultas',
      icono: '⟳',
      permisos: [Permiso.CONSULTAS_LEER],
    },
    {
      ruta: '/distributivo',
      etiqueta: 'Distributivo',
      icono: '▩',
      permisos: [Permiso.DISTRIBUTIVO_LEER],
    },
    {
      ruta: '/distributivo/asignaturas',
      etiqueta: 'Asignaturas',
      icono: '✎',
      permisos: [Permiso.DISTRIBUTIVO_ESCRIBIR],
    },
    {
      ruta: '/catalogos',
      etiqueta: 'Catalogos',
      icono: '⛁',
      permisos: [Permiso.CATALOGOS_LEER],
    },
    {
      ruta: '/reportes',
      etiqueta: 'Reportes',
      icono: '▦',
      permisos: [Permiso.REPORTES_GENERAR],
    },
    {
      ruta: '/administracion',
      etiqueta: 'Administracion',
      icono: '⚙',
      permisos: [Permiso.USUARIOS_LEER],
    },
  ];

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
