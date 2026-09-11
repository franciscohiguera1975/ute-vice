import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { RouterLink, RouterLinkActive } from '@angular/router';

import { NotificacionesService } from '@core/notificaciones.service';
import { SesionStore } from '@core/sesion.store';
import {
  Permiso,
  RolCodigo,
  type ErrorApi,
  type PermisoCatalogo,
  type Rol,
} from '@domain/modelos';
import { RepositorioAdministracion } from '@domain/puertos';
import { CargandoComponent } from '@shared/componentes/cargando.component';

/**
 * Matriz de roles y permisos.
 *
 * El catalogo de permisos se pide al backend en lugar de mantenerlo aqui: una
 * copia en el frontend se desincronizaria en cuanto se agregue un permiso nuevo,
 * y nadie lo notaria hasta que alguien no pudiera hacer su trabajo.
 */
@Component({
  selector: 'ute-roles',
  standalone: true,
  imports: [RouterLink, RouterLinkActive, CargandoComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './roles.component.html',
  styleUrl: './administracion.scss',
})
export class RolesComponent {
  private readonly repositorio = inject(RepositorioAdministracion);
  private readonly notificaciones = inject(NotificacionesService);
  protected readonly sesion = inject(SesionStore);

  protected readonly Permiso = Permiso;
  protected readonly ADMIN = RolCodigo.ADMIN;

  protected readonly roles = signal<readonly Rol[]>([]);
  protected readonly permisos = signal<readonly PermisoCatalogo[]>([]);
  protected readonly cargando = signal(true);
  protected readonly guardando = signal<string | null>(null);

  /** Permisos agrupados por modulo, que es como se leen mejor. */
  protected readonly porModulo = computed(() => {
    const grupos = new Map<string, PermisoCatalogo[]>();
    for (const permiso of this.permisos()) {
      const lista = grupos.get(permiso.modulo) ?? [];
      lista.push(permiso);
      grupos.set(permiso.modulo, lista);
    }
    return [...grupos.entries()].map(([modulo, permisos]) => ({ modulo, permisos }));
  });

  constructor() {
    this.cargar();
  }

  private cargar(): void {
    this.cargando.set(true);
    this.repositorio.listarPermisos().subscribe({
      next: (permisos) => {
        this.permisos.set(permisos);
        this.repositorio.listarRoles().subscribe({
          next: (roles) => {
            this.roles.set(roles);
            this.cargando.set(false);
          },
          error: (error: ErrorApi) => {
            this.cargando.set(false);
            this.notificaciones.error('No fue posible cargar los roles', error.mensaje);
          },
        });
      },
      error: (error: ErrorApi) => {
        this.cargando.set(false);
        this.notificaciones.error('No fue posible cargar los permisos', error.mensaje);
      },
    });
  }

  protected tienePermiso(rol: Rol, codigo: string): boolean {
    return rol.permisos.includes(codigo as Permiso);
  }

  protected editable(rol: Rol): boolean {
    // El rol ADMIN no se toca: vaciarlo dejaria el sistema sin forma de
    // recuperar el control. El backend lo impide tambien.
    return rol.codigo !== RolCodigo.ADMIN && this.sesion.puede(Permiso.ROLES_ADMINISTRAR);
  }

  protected alternar(rol: Rol, codigo: string, marcado: boolean): void {
    const permisos = marcado
      ? [...new Set([...rol.permisos, codigo])]
      : rol.permisos.filter((p) => p !== codigo);

    this.guardando.set(rol.codigo);
    this.repositorio.actualizarRol(rol.codigo, { permisos }).subscribe({
      next: (actualizado) => {
        this.guardando.set(null);
        this.roles.update((lista) =>
          lista.map((r) => (r.codigo === actualizado.codigo ? actualizado : r)),
        );
        this.notificaciones.exito(`Permisos de ${actualizado.nombre} actualizados`);
      },
      error: (error: ErrorApi) => {
        this.guardando.set(null);
        this.notificaciones.error('No fue posible actualizar el rol', error.mensaje);
        this.cargar();
      },
    });
  }

  protected etiquetaModulo(modulo: string): string {
    return (
      {
        personas: 'Personas',
        titulos: 'Titulos',
        consultas: 'Consultas',
        reportes: 'Reportes',
        dashboard: 'Tablero',
        usuarios: 'Usuarios',
        roles: 'Roles',
        auditoria: 'Auditoria',
      }[modulo] ?? modulo
    );
  }
}
