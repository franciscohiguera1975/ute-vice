import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink, RouterLinkActive } from '@angular/router';

import { NotificacionesService } from '@core/notificaciones.service';
import { SesionStore } from '@core/sesion.store';
import {
  Permiso,
  RolCodigo,
  type ErrorApi,
  type Pagina,
  type Rol,
  type Usuario,
  paginaVacia,
} from '@domain/modelos';
import { RepositorioAdministracion } from '@domain/puertos';
import { CargandoComponent } from '@shared/componentes/cargando.component';
import { ConfirmarComponent } from '@shared/componentes/confirmar.component';
import { InsigniaComponent } from '@shared/componentes/insignia.component';
import { PaginadorComponent } from '@shared/componentes/paginador.component';
import { VacioComponent } from '@shared/componentes/vacio.component';
import { PermisoDirective } from '@shared/directivas/permiso.directive';
import { DesdeHacePipe } from '@shared/pipes/formato.pipe';

@Component({
  selector: 'ute-usuarios',
  standalone: true,
  imports: [
    FormsModule,
    RouterLink,
    RouterLinkActive,
    CargandoComponent,
    ConfirmarComponent,
    InsigniaComponent,
    PaginadorComponent,
    VacioComponent,
    PermisoDirective,
    DesdeHacePipe,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './usuarios.component.html',
  styleUrl: './administracion.scss',
})
export class UsuariosComponent {
  private readonly repositorio = inject(RepositorioAdministracion);
  private readonly notificaciones = inject(NotificacionesService);
  protected readonly sesion = inject(SesionStore);

  protected readonly Permiso = Permiso;

  protected readonly datos = signal<Pagina<Usuario>>(paginaVacia<Usuario>());
  protected readonly roles = signal<readonly Rol[]>([]);
  protected readonly cargando = signal(true);
  protected readonly pagina = signal(1);
  protected readonly tamano = signal(25);
  protected readonly texto = signal('');
  protected readonly filtroRol = signal('');
  protected readonly filtroActivo = signal<'' | 'true' | 'false'>('');

  // --- Alta ---
  protected readonly mostrarFormulario = signal(false);
  protected readonly nuevoEmail = signal('');
  protected readonly nuevoNombre = signal('');
  protected readonly nuevaContrasena = signal('');
  protected readonly nuevosRoles = signal<string[]>([RolCodigo.CONSULTA]);
  protected readonly guardando = signal(false);

  // --- Restablecer contrasena ---
  protected readonly usuarioAResetear = signal<Usuario | null>(null);
  protected readonly contrasenaNueva = signal('');

  // --- Eliminar ---
  protected readonly usuarioAEliminar = signal<Usuario | null>(null);

  constructor() {
    this.repositorio.listarRoles().subscribe({
      next: (roles) => this.roles.set(roles),
      error: () => this.notificaciones.aviso('No fue posible cargar el catalogo de roles'),
    });
    this.cargar();
  }

  protected cargar(): void {
    this.cargando.set(true);
    this.repositorio
      .listarUsuarios(
        { pagina: this.pagina(), tamano: this.tamano() },
        this.texto().trim() || undefined,
        this.filtroActivo() === '' ? undefined : this.filtroActivo() === 'true',
        this.filtroRol() || undefined,
      )
      .subscribe({
        next: (pagina) => {
          this.datos.set(pagina);
          this.cargando.set(false);
        },
        error: (error: ErrorApi) => {
          this.cargando.set(false);
          this.notificaciones.error('No fue posible cargar los usuarios', error.mensaje);
        },
      });
  }

  protected buscar(): void {
    this.pagina.set(1);
    this.cargar();
  }

  protected irAPagina(pagina: number): void {
    this.pagina.set(pagina);
    this.cargar();
  }

  protected cambiarTamano(tamano: number): void {
    this.tamano.set(tamano);
    this.pagina.set(1);
    this.cargar();
  }

  protected alternarRolNuevo(codigo: string, marcado: boolean): void {
    this.nuevosRoles.update((lista) =>
      marcado ? [...new Set([...lista, codigo])] : lista.filter((r) => r !== codigo),
    );
  }

  protected crear(): void {
    if (this.nuevosRoles().length === 0) {
      this.notificaciones.aviso('Asigne al menos un rol');
      return;
    }

    this.guardando.set(true);
    this.repositorio
      .crearUsuario({
        email: this.nuevoEmail().trim(),
        nombreCompleto: this.nuevoNombre().trim(),
        contrasena: this.nuevaContrasena(),
        roles: this.nuevosRoles(),
        // La cuenta nace con una contrasena que conoce quien la creo: se exige
        // cambiarla en el primer acceso.
        debeCambiarContrasena: true,
      })
      .subscribe({
        next: () => {
          this.guardando.set(false);
          this.mostrarFormulario.set(false);
          this.nuevoEmail.set('');
          this.nuevoNombre.set('');
          this.nuevaContrasena.set('');
          this.nuevosRoles.set([RolCodigo.CONSULTA]);
          this.notificaciones.exito('Usuario creado', 'Debera cambiar la contrasena al ingresar');
          this.cargar();
        },
        error: (error: ErrorApi) => {
          this.guardando.set(false);
          this.notificaciones.error('No fue posible crear el usuario', error.mensaje);
        },
      });
  }

  protected alternarEstado(usuario: Usuario): void {
    this.repositorio.actualizarUsuario(usuario.id, { activo: !usuario.activo }).subscribe({
      next: () => {
        this.notificaciones.exito(
          usuario.activo ? 'Cuenta desactivada' : 'Cuenta activada',
          usuario.activo ? 'Se cerraron todas sus sesiones abiertas' : undefined,
        );
        this.cargar();
      },
      error: (error: ErrorApi) =>
        this.notificaciones.error('No fue posible cambiar el estado', error.mensaje),
    });
  }

  protected cambiarRoles(usuario: Usuario, codigo: string, marcado: boolean): void {
    const actuales = usuario.roles.map((r) => r.codigo);
    const nuevos = marcado
      ? [...new Set([...actuales, codigo])]
      : actuales.filter((r) => r !== codigo);

    if (nuevos.length === 0) {
      this.notificaciones.aviso('Un usuario debe conservar al menos un rol');
      this.cargar();
      return;
    }

    this.repositorio.actualizarUsuario(usuario.id, { roles: nuevos }).subscribe({
      next: () => {
        this.notificaciones.exito('Roles actualizados');
        this.cargar();
      },
      error: (error: ErrorApi) => {
        this.notificaciones.error('No fue posible cambiar los roles', error.mensaje);
        this.cargar();
      },
    });
  }

  protected restablecer(): void {
    const usuario = this.usuarioAResetear();
    if (!usuario) return;

    this.repositorio.restablecerContrasena(usuario.id, this.contrasenaNueva(), true).subscribe({
      next: () => {
        this.usuarioAResetear.set(null);
        this.contrasenaNueva.set('');
        this.notificaciones.exito(
          'Contrasena restablecida',
          'Se cerraron las sesiones del usuario y debera cambiarla al ingresar',
        );
      },
      error: (error: ErrorApi) =>
        this.notificaciones.error('No fue posible restablecer', error.mensaje),
    });
  }

  protected eliminar(): void {
    const usuario = this.usuarioAEliminar();
    if (!usuario) return;

    this.repositorio.eliminarUsuario(usuario.id).subscribe({
      next: () => {
        this.usuarioAEliminar.set(null);
        this.notificaciones.exito('Usuario eliminado');
        this.cargar();
      },
      error: (error: ErrorApi) => {
        this.usuarioAEliminar.set(null);
        this.notificaciones.error('No fue posible eliminar', error.mensaje);
      },
    });
  }

  protected tieneRol(usuario: Usuario, codigo: string): boolean {
    return usuario.roles.some((r) => r.codigo === codigo);
  }

  protected esUsuarioPropio(usuario: Usuario): boolean {
    return this.sesion.usuario()?.id === usuario.id;
  }
}
