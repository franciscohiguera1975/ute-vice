import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';

import { NotificacionesService } from '@core/notificaciones.service';
import { SesionStore } from '@core/sesion.store';
import type { ErrorApi, MetodosAcceso } from '@domain/modelos';
import { RepositorioAutenticacion } from '@domain/puertos';
import { CargandoComponent } from '@shared/componentes/cargando.component';

type Modo = 'local' | 'ldap';

@Component({
  selector: 'ute-acceso',
  standalone: true,
  imports: [ReactiveFormsModule, CargandoComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './acceso.component.html',
  styleUrl: './acceso.component.scss',
})
export class AccesoComponent {
  private readonly fb = inject(FormBuilder);
  private readonly autenticacion = inject(RepositorioAutenticacion);
  private readonly sesion = inject(SesionStore);
  private readonly router = inject(Router);
  private readonly ruta = inject(ActivatedRoute);
  private readonly notificaciones = inject(NotificacionesService);

  protected readonly enviando = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly modo = signal<Modo>('local');
  protected readonly metodos = signal<MetodosAcceso | null>(null);
  protected readonly cargandoMetodos = signal(true);

  protected readonly hayFederados = computed(() => {
    const m = this.metodos();
    return m !== null && (m.google || m.ldap);
  });

  protected readonly formulario = this.fb.nonNullable.group({
    identificador: ['', [Validators.required]],
    contrasena: ['', [Validators.required]],
  });

  constructor() {
    // Se consulta que vias de acceso estan activas para no ofrecer un boton
    // que no funciona. Si la llamada falla, se asume solo acceso local: es el
    // unico que siempre existe.
    this.autenticacion.metodosDisponibles().subscribe({
      next: (metodos) => {
        this.metodos.set(metodos);
        this.cargandoMetodos.set(false);
      },
      error: () => {
        this.metodos.set({ local: true, google: false, ldap: false, urlGoogle: null });
        this.cargandoMetodos.set(false);
      },
    });
  }

  protected cambiarModo(modo: Modo): void {
    this.modo.set(modo);
    this.error.set(null);
    this.formulario.reset();
  }

  protected enviar(): void {
    if (this.formulario.invalid || this.enviando()) {
      this.formulario.markAllAsTouched();
      return;
    }

    this.enviando.set(true);
    this.error.set(null);

    const { identificador, contrasena } = this.formulario.getRawValue();
    const peticion =
      this.modo() === 'ldap'
        ? this.autenticacion.iniciarSesionLdap(identificador, contrasena)
        : this.autenticacion.iniciarSesion(identificador, contrasena);

    peticion.subscribe({
      next: (sesion) => {
        this.sesion.establecer(sesion);
        this.enviando.set(false);
        this.notificaciones.exito(`Bienvenido, ${sesion.usuario.nombreCompleto}`);
        void this.router.navigateByUrl(this.rutaDeRetorno());
      },
      error: (error: ErrorApi) => {
        this.enviando.set(false);
        this.error.set(error.mensaje);
        this.formulario.patchValue({ contrasena: '' });
      },
    });
  }

  protected accederConGoogle(): void {
    const url = this.metodos()?.urlGoogle;
    if (url) {
      // Se sale de la aplicacion: el canje del codigo ocurre en el backend,
      // que es quien custodia el secreto de cliente.
      window.location.href = url;
    }
  }

  /**
   * Ruta a la que volver tras acceder.
   *
   * Solo se aceptan rutas internas: un `retorno` con URL absoluta permitiria
   * usar la pantalla de acceso como redirector hacia un sitio externo.
   */
  private rutaDeRetorno(): string {
    const retorno = this.ruta.snapshot.queryParamMap.get('retorno');
    if (!retorno || !retorno.startsWith('/') || retorno.startsWith('//')) {
      return '/tablero';
    }
    return retorno;
  }

  protected campoInvalido(nombre: 'identificador' | 'contrasena'): boolean {
    const control = this.formulario.controls[nombre];
    return control.invalid && (control.touched || control.dirty);
  }
}
