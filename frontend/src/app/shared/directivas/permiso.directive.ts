import {
  Directive,
  TemplateRef,
  ViewContainerRef,
  type EmbeddedViewRef,
  effect,
  inject,
  input,
} from '@angular/core';

import { SesionStore } from '@core/sesion.store';
import type { Permiso } from '@domain/modelos';

/**
 * Muestra el contenido solo si el usuario tiene alguno de los permisos.
 *
 *     <button *utePermiso="Permiso.PERSONAS_ESCRIBIR">Nueva persona</button>
 *     <div *utePermiso="[Permiso.A, Permiso.B]">…</div>
 *
 * Ocultar un boton no protege nada: la autorizacion real la impone el backend.
 * Lo que evita es ofrecer una accion que terminaria en un 403.
 */
@Directive({
  selector: '[utePermiso]',
  standalone: true,
})
export class PermisoDirective {
  private readonly plantilla = inject<TemplateRef<unknown>>(TemplateRef);
  private readonly contenedor = inject(ViewContainerRef);
  private readonly sesion = inject(SesionStore);

  private vista: EmbeddedViewRef<unknown> | null = null;

  readonly utePermiso = input.required<Permiso | readonly Permiso[]>();

  constructor() {
    // Un `effect` mantiene la vista sincronizada si los permisos cambian en
    // caliente, p. ej. tras renovar el perfil.
    effect(() => {
      const requeridos = this.utePermiso();
      const lista = Array.isArray(requeridos) ? requeridos : [requeridos as Permiso];
      const autorizado = this.sesion.puedeAlguno(...lista);

      if (autorizado && !this.vista) {
        this.vista = this.contenedor.createEmbeddedView(this.plantilla);
      } else if (!autorizado && this.vista) {
        this.contenedor.clear();
        this.vista = null;
      }
    });
  }
}
