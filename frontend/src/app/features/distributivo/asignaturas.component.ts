import { DecimalPipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, RouterLink } from '@angular/router';

import { NotificacionesService } from '@core/notificaciones.service';
import {
  TipoCatalogo,
  type ErrorApi,
  type FilaDistributivo,
  type FiltroDistributivo,
} from '@domain/modelos';
import { RepositorioDistributivo } from '@domain/puertos';
import { CargandoComponent } from '@shared/componentes/cargando.component';

import { CatalogosStore } from '@core/catalogos.store';

/**
 * Las materias de una fila como una sola cadena.
 *
 * Es la forma en que se escriben y la misma con que salen en el reporte: una
 * celda con todas separadas por comas. Usar el mismo signo para entrar y para
 * salir evita tener que recordar dos convenciones.
 */
function textoDe(fila: FilaDistributivo): string {
  return fila.asignaturas.join(', ');
}

/** Cuántas filas se capturan de una vez. El backend admite hasta 500. */
const TAMANO_TANDA = 100;

/**
 * Captura de la asignatura que imparte cada docente.
 *
 * Es el unico dato del reporte institucional que no existe en el consolidado:
 * el distributivo reparte horas por tipo de actividad, no por materia. Hay que
 * escribirlo a mano para cientos de filas, asi que la pantalla esta pensada
 * para eso —una tabla editable, sin abrir un modal por registro— y guarda la
 * tanda entera de una vez.
 */
@Component({
  selector: 'ute-asignaturas',
  standalone: true,
  imports: [DecimalPipe, FormsModule, RouterLink, CargandoComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './asignaturas.component.html',
  styleUrl: './asignaturas.component.scss',
})
export class AsignaturasComponent {
  private readonly repositorio = inject(RepositorioDistributivo);
  private readonly notificaciones = inject(NotificacionesService);
  private readonly ruta = inject(ActivatedRoute);
  protected readonly catalogos = inject(CatalogosStore);

  protected readonly TipoCatalogo = TipoCatalogo;

  protected readonly paoId = signal('');
  protected readonly facultadId = signal('');
  protected readonly carreraId = signal('');
  protected readonly soloPendientes = signal(true);
  protected readonly texto = signal('');

  protected readonly filas = signal<readonly FilaDistributivo[]>([]);
  protected readonly total = signal(0);
  protected readonly cargando = signal(false);
  protected readonly guardando = signal(false);

  /** Lo escrito en pantalla, por id de fila. Solo lo que el usuario tocó. */
  private readonly editado = signal<Readonly<Record<string, string>>>({});

  protected readonly pendientes = computed(() => {
    const cambios = this.editado();
    return this.filas().filter((f) => {
      const valor = cambios[f.id];
      return valor !== undefined && valor !== textoDe(f);
    });
  });

  protected readonly hayCambios = computed(() => this.pendientes().length > 0);

  constructor() {
    this.catalogos.cargar();

    // La pantalla del reporte enlaza aquí con el periodo y la facultad que se
    // estaba exportando, para no hacer elegir dos veces lo mismo.
    const parametros = this.ruta.snapshot.queryParamMap;
    this.paoId.set(parametros.get('paoId') ?? '');
    this.facultadId.set(parametros.get('facultadId') ?? '');
    if (this.paoId()) this.buscar();
  }

  protected buscar(): void {
    if (!this.paoId()) {
      this.notificaciones.aviso('Seleccione un periodo académico');
      return;
    }
    if (this.hayCambios() && !this.confirmarDescarte()) return;

    const filtro: FiltroDistributivo = {
      paoId: this.paoId(),
      facultadId: this.facultadId() || undefined,
      carreraId: this.carreraId() || undefined,
      texto: this.texto().trim() || undefined,
      sinAsignatura: this.soloPendientes() || undefined,
    };

    this.cargando.set(true);
    this.repositorio
      .listar(filtro, { pagina: 1, tamano: TAMANO_TANDA, ordenarPor: 'docente' })
      .subscribe({
        next: (pagina) => {
          this.filas.set(pagina.items);
          this.total.set(pagina.total);
          this.editado.set({});
          this.cargando.set(false);
        },
        error: (error: ErrorApi) => {
          this.cargando.set(false);
          this.notificaciones.error('No fue posible consultar', error.mensaje);
        },
      });
  }

  protected escribir(filaId: string, valor: string): void {
    this.editado.update((actual) => ({ ...actual, [filaId]: valor }));
  }

  protected valorDe(fila: FilaDistributivo): string {
    return this.editado()[fila.id] ?? textoDe(fila);
  }

  protected estaEditada(fila: FilaDistributivo): boolean {
    const valor = this.editado()[fila.id];
    return valor !== undefined && valor !== textoDe(fila);
  }

  /**
   * Copia la asignatura de la fila anterior.
   *
   * Un docente suele aparecer varias veces seguidas con la misma materia; sin
   * esto la captura es reescribir el mismo texto decenas de veces.
   */
  protected copiarDeArriba(indice: number): void {
    if (indice === 0) return;
    const anterior = this.filas()[indice - 1];
    const actual = this.filas()[indice];
    this.escribir(actual.id, this.valorDe(anterior));
  }

  protected descartar(): void {
    if (!this.confirmarDescarte()) return;
    this.editado.set({});
  }

  protected guardar(): void {
    const cambios = this.pendientes();
    if (cambios.length === 0) return;

    this.guardando.set(true);
    this.repositorio
      .capturarAsignaturas(
        cambios.map((f) => ({ filaId: f.id, asignatura: this.valorDe(f) })),
      )
      .subscribe({
        next: (resultado) => {
          this.guardando.set(false);
          const nuevas = resultado.asignaturasCreadas;
          this.notificaciones.exito(
            'Asignaturas guardadas',
            `${resultado.actualizadas} registro(s) actualizado(s)` +
              (nuevas > 0 ? ` · ${nuevas} asignatura(s) nueva(s) en el catálogo.` : '.'),
          );
          // El catalogo crecio: se refresca para que la lista de sugerencias
          // incluya lo que se acaba de crear.
          if (nuevas > 0) this.catalogos.cargar(true);
          // Se recarga: con «solo pendientes» activo, lo guardado sale de la
          // lista y queda a la vista lo que falta.
          this.editado.set({});
          this.buscar();
        },
        error: (error: ErrorApi) => {
          this.guardando.set(false);
          this.notificaciones.error('No fue posible guardar', error.mensaje);
        },
      });
  }

  private confirmarDescarte(): boolean {
    return confirm(
      `Hay ${this.pendientes().length} cambio(s) sin guardar. ¿Descartarlos?`,
    );
  }
}
