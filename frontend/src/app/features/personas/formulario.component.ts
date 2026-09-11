import { ChangeDetectionStrategy, Component, computed, inject, input, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';

import { NotificacionesService } from '@core/notificaciones.service';
import {
  ETIQUETAS_VINCULACION,
  TipoVinculacion,
  type CambiosPersona,
  type DatosPersona,
  type ErrorApi,
} from '@domain/modelos';
import { RepositorioPersonas } from '@domain/puertos';
import { CargandoComponent } from '@shared/componentes/cargando.component';

import { validadorCedula } from './validador-cedula';

@Component({
  selector: 'ute-formulario-persona',
  standalone: true,
  imports: [ReactiveFormsModule, RouterLink, CargandoComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './formulario.component.html',
  styleUrl: './formulario.component.scss',
})
export class FormularioPersonaComponent {
  private readonly fb = inject(FormBuilder);
  private readonly repositorio = inject(RepositorioPersonas);
  private readonly notificaciones = inject(NotificacionesService);
  private readonly router = inject(Router);

  /** Presente solo en la ruta de edicion. */
  readonly id = input<string>();

  protected readonly ETIQUETAS_VINCULACION = ETIQUETAS_VINCULACION;
  protected readonly vinculaciones = Object.values(TipoVinculacion);

  protected readonly cargando = signal(false);
  protected readonly enviando = signal(false);
  protected readonly esEdicion = computed(() => Boolean(this.id()));

  protected readonly formulario = this.fb.nonNullable.group({
    cedula: ['', [Validators.required, validadorCedula]],
    nombres: ['', [Validators.required, Validators.maxLength(120)]],
    apellidos: ['', [Validators.required, Validators.maxLength(120)]],
    emailInstitucional: ['', [Validators.email]],
    emailPersonal: ['', [Validators.email]],
    telefono: ['', [Validators.maxLength(32)]],
    tipoVinculacion: [TipoVinculacion.OTRO as TipoVinculacion],
    unidad: ['', [Validators.maxLength(160)]],
    cargo: ['', [Validators.maxLength(160)]],
    codigoEmpleado: ['', [Validators.maxLength(40)]],
    fechaIngreso: [''],
    fechaNacimiento: [''],
    observaciones: [''],
    activo: [true],
  });

  constructor() {
    queueMicrotask(() => {
      if (this.esEdicion()) this.cargar();
    });
  }

  private cargar(): void {
    const id = this.id();
    if (!id) return;

    this.cargando.set(true);
    this.repositorio.obtener(id).subscribe({
      next: ({ persona }) => {
        this.formulario.patchValue({
          cedula: persona.cedula,
          nombres: persona.nombres,
          apellidos: persona.apellidos,
          emailInstitucional: persona.emailInstitucional ?? '',
          emailPersonal: persona.emailPersonal ?? '',
          telefono: persona.telefono ?? '',
          tipoVinculacion: persona.tipoVinculacion,
          unidad: persona.unidad ?? '',
          cargo: persona.cargo ?? '',
          codigoEmpleado: persona.codigoEmpleado ?? '',
          fechaIngreso: persona.fechaIngreso ?? '',
          activo: persona.activo,
        });

        // La cedula identifica a la persona ante el registro nacional:
        // cambiarla invalidaria todo su historico de consultas.
        this.formulario.controls.cedula.disable();
        this.cargando.set(false);
      },
      error: (error: ErrorApi) => {
        this.cargando.set(false);
        this.notificaciones.error('No fue posible cargar la persona', error.mensaje);
        void this.router.navigate(['/personas']);
      },
    });
  }

  protected enviar(): void {
    if (this.formulario.invalid || this.enviando()) {
      this.formulario.markAllAsTouched();
      this.notificaciones.aviso('Revise los campos marcados');
      return;
    }

    this.enviando.set(true);
    const valores = this.formulario.getRawValue();

    // Los campos vacios se envian como `null` para que el backend los limpie,
    // no como cadena vacia, que quedaria almacenada como un dato falso.
    const opcional = (texto: string): string | null => texto.trim() || null;

    if (this.esEdicion()) {
      const cambios: CambiosPersona = {
        nombres: valores.nombres.trim(),
        apellidos: valores.apellidos.trim(),
        emailInstitucional: opcional(valores.emailInstitucional),
        emailPersonal: opcional(valores.emailPersonal),
        telefono: opcional(valores.telefono),
        tipoVinculacion: valores.tipoVinculacion,
        unidad: opcional(valores.unidad),
        cargo: opcional(valores.cargo),
        codigoEmpleado: opcional(valores.codigoEmpleado),
        fechaIngreso: opcional(valores.fechaIngreso),
        observaciones: opcional(valores.observaciones),
        activo: valores.activo,
      };

      this.repositorio.actualizar(this.id()!, cambios).subscribe({
        next: (persona) => {
          this.notificaciones.exito('Persona actualizada');
          void this.router.navigate(['/personas', persona.id]);
        },
        error: (error: ErrorApi) => this.fallar(error),
      });
      return;
    }

    const datos: DatosPersona = {
      cedula: valores.cedula.trim(),
      nombres: valores.nombres.trim(),
      apellidos: valores.apellidos.trim(),
      emailInstitucional: opcional(valores.emailInstitucional),
      emailPersonal: opcional(valores.emailPersonal),
      telefono: opcional(valores.telefono),
      tipoVinculacion: valores.tipoVinculacion,
      unidad: opcional(valores.unidad),
      cargo: opcional(valores.cargo),
      codigoEmpleado: opcional(valores.codigoEmpleado),
      fechaIngreso: opcional(valores.fechaIngreso),
      fechaNacimiento: opcional(valores.fechaNacimiento),
      observaciones: opcional(valores.observaciones),
    };

    this.repositorio.crear(datos).subscribe({
      next: (persona) => {
        this.notificaciones.exito('Persona registrada');
        void this.router.navigate(['/personas', persona.id]);
      },
      error: (error: ErrorApi) => this.fallar(error),
    });
  }

  private fallar(error: ErrorApi): void {
    this.enviando.set(false);

    // El backend indica el campo exacto cuando la validacion es de dominio:
    // se marca ahi para que el usuario no tenga que adivinar.
    const campo = error.detalles['campo'];
    if (typeof campo === 'string' && campo in this.formulario.controls) {
      const control = this.formulario.get(campo);
      control?.setErrors({ servidor: error.mensaje });
      control?.markAsTouched();
    }
    this.notificaciones.error('No fue posible guardar', error.mensaje);
  }

  protected error(nombre: keyof typeof this.formulario.controls): string | null {
    const control = this.formulario.controls[nombre];
    if (!control.invalid || (!control.touched && !control.dirty)) return null;

    const errores = control.errors ?? {};
    if (errores['required']) return 'Este campo es obligatorio';
    if (errores['email']) return 'El correo no tiene un formato valido';
    if (errores['maxlength'])
      return `Maximo ${errores['maxlength'].requiredLength} caracteres`;
    if (errores['cedulaInvalida']) return errores['cedulaInvalida'] as string;
    if (errores['servidor']) return errores['servidor'] as string;
    return 'Valor no valido';
  }
}
