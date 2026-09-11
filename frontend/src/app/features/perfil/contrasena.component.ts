import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';

import { NotificacionesService } from '@core/notificaciones.service';
import { SesionStore } from '@core/sesion.store';
import type { ErrorApi } from '@domain/modelos';
import { RepositorioAutenticacion } from '@domain/puertos';

/** Reglas de complejidad. Replican exactamente las que aplica el backend. */
const REGLAS: readonly { texto: string; cumple: (v: string) => boolean }[] = [
  { texto: 'Al menos 10 caracteres', cumple: (v) => v.length >= 10 },
  { texto: 'Una letra mayuscula', cumple: (v) => /[A-Z]/.test(v) },
  { texto: 'Una letra minuscula', cumple: (v) => /[a-z]/.test(v) },
  { texto: 'Un digito', cumple: (v) => /\d/.test(v) },
  { texto: 'Un caracter especial', cumple: (v) => /[^A-Za-z0-9]/.test(v) },
];

@Component({
  selector: 'ute-contrasena',
  standalone: true,
  imports: [ReactiveFormsModule, RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <header class="encabezado">
      <h1>Cambiar contrasena</h1>
      @if (obligatorio()) {
        <div class="alerta-obligatorio" role="alert">
          <p class="negrita">Debe cambiar su contrasena antes de continuar</p>
          <p class="texto-sm">
            Su cuenta se creo o se restablecio con una contrasena provisional que
            conoce otra persona. Hasta que la cambie, no podra usar el resto del
            sistema.
          </p>
        </div>
      } @else {
        <p class="texto-sm texto-suave">
          Al cambiarla se cerraran sus demas sesiones abiertas.
        </p>
      }
    </header>

    <form [formGroup]="formulario" (ngSubmit)="enviar()" novalidate class="tarjeta formulario">
      <div class="tarjeta__cuerpo">
        <div class="campo">
          <label class="campo__etiqueta" for="actual">Contrasena actual</label>
          <input id="actual" type="password" formControlName="actual" autocomplete="current-password" />
        </div>

        <div class="campo">
          <label class="campo__etiqueta" for="nueva">Contrasena nueva</label>
          <input id="nueva" type="password" formControlName="nueva" autocomplete="new-password" />

          <ul class="reglas">
            @for (regla of estadoReglas(); track regla.texto) {
              <li class="regla" [class.regla--ok]="regla.ok">
                <span aria-hidden="true">{{ regla.ok ? '✓' : '○' }}</span>
                {{ regla.texto }}
              </li>
            }
          </ul>
        </div>

        <div class="campo">
          <label class="campo__etiqueta" for="repetir">Repetir contrasena nueva</label>
          <input id="repetir" type="password" formControlName="repetir" autocomplete="new-password" />
          @if (noCoinciden()) {
            <p class="campo__error">Las contrasenas no coinciden</p>
          }
        </div>

        <div class="fila hueco-sm" style="justify-content: flex-end">
          @if (!obligatorio()) {
            <a routerLink="/perfil" class="btn btn--secundario">Cancelar</a>
          }
          <button type="submit" class="btn btn--primario" [disabled]="!puedeEnviar()">
            {{ enviando() ? 'Guardando…' : 'Cambiar contrasena' }}
          </button>
        </div>
      </div>
    </form>
  `,
  styles: [
    `
      .encabezado { margin-bottom: 1.25rem; }
      .formulario { max-width: 32rem; }

      .alerta-obligatorio {
        padding: 0.75rem 0.9rem;
        margin-top: 0.5rem;
        color: var(--aviso);
        background: var(--aviso-suave);
        border-radius: var(--radio);
      }
      .alerta-obligatorio p { margin: 0 0 0.25rem; }
      .alerta-obligatorio p:last-child { margin: 0; }

      .reglas { list-style: none; margin: 0.6rem 0 0; padding: 0; }
      .regla {
        display: flex;
        gap: 0.45rem;
        font-size: 0.78rem;
        color: var(--texto-tenue);
        padding: 0.1rem 0;
      }
      .regla--ok { color: var(--exito); }
    `,
  ],
})
export class ContrasenaComponent {
  private readonly fb = inject(FormBuilder);
  private readonly autenticacion = inject(RepositorioAutenticacion);
  private readonly sesion = inject(SesionStore);
  private readonly router = inject(Router);
  private readonly ruta = inject(ActivatedRoute);
  private readonly notificaciones = inject(NotificacionesService);

  protected readonly enviando = signal(false);
  protected readonly obligatorio = signal(
    this.ruta.snapshot.queryParamMap.get('obligatorio') === '1' ||
      this.sesion.debeCambiarContrasena(),
  );

  protected readonly formulario = this.fb.nonNullable.group({
    actual: ['', [Validators.required]],
    nueva: ['', [Validators.required, Validators.minLength(10)]],
    repetir: ['', [Validators.required]],
  });

  private readonly valores = signal({ nueva: '', repetir: '' });

  protected readonly estadoReglas = computed(() =>
    REGLAS.map((r) => ({ texto: r.texto, ok: r.cumple(this.valores().nueva) })),
  );

  protected readonly noCoinciden = computed(() => {
    const { nueva, repetir } = this.valores();
    return repetir.length > 0 && nueva !== repetir;
  });

  protected readonly puedeEnviar = computed(
    () =>
      !this.enviando() &&
      this.estadoReglas().every((r) => r.ok) &&
      !this.noCoinciden() &&
      this.valores().repetir.length > 0,
  );

  constructor() {
    this.formulario.valueChanges.subscribe((v) =>
      this.valores.set({ nueva: v.nueva ?? '', repetir: v.repetir ?? '' }),
    );
  }

  protected enviar(): void {
    if (!this.puedeEnviar() || this.formulario.invalid) {
      this.formulario.markAllAsTouched();
      return;
    }

    this.enviando.set(true);
    const { actual, nueva } = this.formulario.getRawValue();

    this.autenticacion.cambiarContrasena(actual, nueva).subscribe({
      next: () => {
        this.enviando.set(false);
        this.notificaciones.exito(
          'Contrasena actualizada',
          'Sus demas sesiones se cerraron. Vuelva a ingresar.',
        );
        // El backend revoco todos los tokens, incluido el de esta sesion: hay
        // que volver a autenticarse.
        this.sesion.limpiar();
        void this.router.navigate(['/acceso']);
      },
      error: (error: ErrorApi) => {
        this.enviando.set(false);
        this.notificaciones.error('No fue posible cambiar la contrasena', error.mensaje);
      },
    });
  }
}
