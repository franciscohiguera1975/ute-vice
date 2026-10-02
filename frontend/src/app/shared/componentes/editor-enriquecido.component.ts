import { ChangeDetectionStrategy, Component, inject, input, output } from '@angular/core';
import { FormsModule } from '@angular/forms';
import type Quill from 'quill';
import { QuillEditorComponent, type QuillModules } from 'ngx-quill';

import { NotificacionesService } from '@core/notificaciones.service';
import { RepositorioTickets } from '@domain/puertos';
import { environment } from '@env/environment';

const TIPOS_IMAGEN_ACEPTADOS = 'image/png,image/jpeg,image/webp,image/gif';

/**
 * Editor de texto enriquecido para descripciones y comentarios de ticket.
 *
 * Bloque de codigo con el formato nativo de Quill —sin resaltado de
 * sintaxis real, para no sumar `highlight.js` solo por esto— e insercion de
 * imagenes: el boton sube el archivo y, a diferencia del comportamiento por
 * defecto de Quill, nunca incrusta el resultado como base64 en el HTML
 * guardado.
 */
@Component({
  selector: 'ute-editor-enriquecido',
  standalone: true,
  imports: [FormsModule, QuillEditorComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <quill-editor
      [ngModel]="valor()"
      (ngModelChange)="valorCambio.emit($event)"
      [modules]="modulos"
      format="html"
      [placeholder]="placeholder()"
      (onEditorCreated)="alCrear($event)"
    />
  `,
})
export class EditorEnriquecidoComponent {
  private readonly tickets = inject(RepositorioTickets);
  private readonly notificaciones = inject(NotificacionesService);

  readonly valor = input('');
  readonly placeholder = input('Escriba aqui…');
  readonly valorCambio = output<string>();

  private instancia: Quill | null = null;

  protected readonly modulos: QuillModules = {
    toolbar: {
      container: [
        [{ header: [2, 3, false] }],
        ['bold', 'italic', 'strike'],
        [{ list: 'ordered' }, { list: 'bullet' }],
        ['code-block', 'link', 'image'],
        ['clean'],
      ],
      handlers: {
        image: () => this.insertarImagen(),
      },
    },
  };

  protected alCrear(instancia: Quill): void {
    this.instancia = instancia;
  }

  private insertarImagen(): void {
    const campo = document.createElement('input');
    campo.type = 'file';
    campo.accept = TIPOS_IMAGEN_ACEPTADOS;
    campo.onchange = () => this.subirArchivoSeleccionado(campo.files?.[0] ?? null);
    campo.click();
  }

  private subirArchivoSeleccionado(archivo: File | null): void {
    if (!archivo) return;

    this.tickets.subirImagen(archivo).subscribe({
      next: ({ url }) => this.insertarEnCursor(`${environment.apiUrl}${url}`),
      error: () => this.notificaciones.error('No fue posible subir la imagen'),
    });
  }

  private insertarEnCursor(url: string): void {
    const quill = this.instancia;
    if (!quill) return;

    const seleccion = quill.getSelection(true);
    const indice = seleccion ? seleccion.index : quill.getLength();
    quill.insertEmbed(indice, 'image', url, 'user');
    quill.setSelection(indice + 1, 0, 'user');
  }
}
