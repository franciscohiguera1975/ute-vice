import { ChangeDetectionStrategy, Component, computed, input, output, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

/** Forma minima de una opcion: lo que ya expone `OpcionSelector` del backend. */
export interface OpcionBuscable {
  readonly id: string;
  readonly nombre: string;
}

/** Minusculas y sin tildes, para que buscar "investigacion" encuentre "Investigación". */
const normalizar = (texto: string): string =>
  texto
    .toLowerCase()
    .normalize('NFD')
    .replace(/\p{Diacritic}/gu, '');

/**
 * Selector de una opcion entre muchas, con busqueda por texto.
 *
 * Un `<select>` nativo se vuelve inutilizable pasadas unas pocas decenas de
 * opciones —una carrera entre 300 no se encuentra a ojo, y el tecleo de
 * busqueda del navegador solo empareja el inicio del texto—. Este componente
 * ordena las opciones alfabeticamente y deja filtrar por cualquier parte del
 * nombre.
 *
 * Uso:
 *
 *     <ute-selector-buscable
 *       [opciones]="catalogos.de(TipoCatalogo.FACULTAD)"
 *       [valorId]="formulario.value.facultadId"
 *       (cambio)="formulario.patchValue({ facultadId: $event })"
 *     />
 */
@Component({
  selector: 'ute-selector-buscable',
  standalone: true,
  imports: [FormsModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="selector-buscable">
      @if (!abierto()) {
        <button
          type="button"
          class="campo__control selector-buscable__valor"
          [id]="idCampo() || null"
          (click)="abrir()"
        >
          <span [class.selector-buscable__marcador]="!seleccionActual()">
            {{ seleccionActual()?.nombre ?? etiquetaVacio() }}
          </span>
        </button>
      } @else {
        <input
          type="text"
          class="campo__control"
          [id]="idCampo() || null"
          [placeholder]="placeholder()"
          [ngModel]="texto()"
          (ngModelChange)="texto.set($event)"
          (blur)="cerrar()"
          (keydown.escape)="cerrar()"
          (keydown.enter)="elegirPrimera(); $event.preventDefault()"
        />
        <ul class="selector-buscable__lista">
          <li>
            <button type="button" class="selector-buscable__opcion" (mousedown)="elegir(null)">
              {{ etiquetaVacio() }}
            </button>
          </li>
          @for (o of opcionesFiltradas(); track o.id) {
            <li>
              <button type="button" class="selector-buscable__opcion" (mousedown)="elegir(o)">
                {{ o.nombre }}
              </button>
            </li>
          }
          @if (opcionesFiltradas().length === 0) {
            <li class="selector-buscable__vacio">Sin resultados</li>
          }
        </ul>
      }
    </div>
  `,
  styles: [
    `
      .selector-buscable {
        position: relative;
      }

      .selector-buscable__valor {
        display: block;
        width: 100%;
        text-align: left;
        cursor: pointer;
        background: var(--superficie);
      }

      .selector-buscable__marcador {
        color: var(--texto-tenue);
      }

      .selector-buscable__lista {
        position: absolute;
        z-index: 20;
        top: calc(100% + 0.25rem);
        left: 0;
        right: 0;
        list-style: none;
        margin: 0;
        padding: 0;
        max-height: 16rem;
        overflow-y: auto;
        background: var(--superficie);
        border: 1px solid var(--borde);
        border-radius: var(--radio);
        box-shadow: var(--sombra-2);
      }

      .selector-buscable__opcion {
        display: block;
        width: 100%;
        text-align: left;
        padding: 0.45rem 0.7rem;
        font-size: 0.875rem;
        background: none;
        border: none;
        cursor: pointer;

        &:hover,
        &:focus-visible {
          background: var(--superficie-2);
        }
      }

      .selector-buscable__vacio {
        padding: 0.5rem 0.7rem;
        font-size: 0.8rem;
        color: var(--texto-tenue);
      }
    `,
  ],
})
export class SelectorBuscableComponent {
  readonly opciones = input.required<readonly OpcionBuscable[]>();
  readonly valorId = input<string | null>(null);
  readonly placeholder = input('Escriba para buscar…');
  readonly etiquetaVacio = input('Sin especificar');
  readonly idCampo = input('');

  readonly cambio = output<string | null>();

  protected readonly abierto = signal(false);
  protected readonly texto = signal('');

  private readonly opcionesOrdenadas = computed(() =>
    [...this.opciones()].sort((a, b) => a.nombre.localeCompare(b.nombre, 'es')),
  );

  protected readonly seleccionActual = computed(
    () => this.opcionesOrdenadas().find((o) => o.id === this.valorId()) ?? null,
  );

  protected readonly opcionesFiltradas = computed(() => {
    const patron = normalizar(this.texto().trim());
    const todas = this.opcionesOrdenadas();
    return patron ? todas.filter((o) => normalizar(o.nombre).includes(patron)) : todas;
  });

  protected abrir(): void {
    this.texto.set('');
    this.abierto.set(true);
  }

  protected cerrar(): void {
    this.abierto.set(false);
  }

  protected elegir(opcion: OpcionBuscable | null): void {
    this.abierto.set(false);
    this.texto.set('');
    this.cambio.emit(opcion?.id ?? null);
  }

  protected elegirPrimera(): void {
    const [primera] = this.opcionesFiltradas();
    if (primera) this.elegir(primera);
  }
}
