import {
  ChangeDetectionStrategy,
  Component,
  computed,
  effect,
  inject,
  input,
  signal,
  untracked,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink, RouterLinkActive } from '@angular/router';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { Subject, debounceTime, distinctUntilChanged } from 'rxjs';

import { NotificacionesService } from '@core/notificaciones.service';
import { SesionStore } from '@core/sesion.store';
import {
  Permiso,
  TipoCatalogo,
  paginaVacia,
  type DescriptorCatalogo,
  type ElementoCatalogo,
  type ErrorApi,
  type Pagina,
} from '@domain/modelos';
import { RepositorioCatalogos } from '@domain/puertos';
import { CargandoComponent } from '@shared/componentes/cargando.component';
import { ConfirmarComponent } from '@shared/componentes/confirmar.component';
import { InsigniaComponent } from '@shared/componentes/insignia.component';
import { PaginadorComponent } from '@shared/componentes/paginador.component';
import { VacioComponent } from '@shared/componentes/vacio.component';
import { PermisoDirective } from '@shared/directivas/permiso.directive';

/**
 * CRUD de los doce catalogos.
 *
 * Un solo componente los atiende a todos: el tipo llega por la ruta. Duplicarlo
 * doce veces produciria doce pantallas que se desincronizarian en cuanto
 * cambiara cualquier detalle del comportamiento.
 */
@Component({
  selector: 'ute-catalogo',
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
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './catalogo.component.html',
  styleUrl: './catalogo.component.scss',
})
export class CatalogoComponent {
  private readonly repositorio = inject(RepositorioCatalogos);
  private readonly notificaciones = inject(NotificacionesService);
  protected readonly sesion = inject(SesionStore);

  /** Llega de la ruta `/catalogos/:tipo`. */
  readonly tipo = input.required<TipoCatalogo>();

  protected readonly Permiso = Permiso;

  protected readonly tipos = signal<readonly DescriptorCatalogo[]>([]);
  protected readonly datos = signal<Pagina<ElementoCatalogo>>(paginaVacia<ElementoCatalogo>());
  protected readonly cargando = signal(true);
  protected readonly texto = signal('');
  protected readonly soloActivos = signal<'' | 'true' | 'false'>('');
  protected readonly pagina = signal(1);
  protected readonly tamano = signal(25);

  // --- Formulario de alta y edicion ---
  protected readonly editando = signal<ElementoCatalogo | null>(null);
  protected readonly creando = signal(false);
  protected readonly codigo = signal('');
  protected readonly nombre = signal('');
  protected readonly descripcion = signal('');
  protected readonly activo = signal(true);
  protected readonly orden = signal(0);
  protected readonly codigoErp = signal('');
  protected readonly guardando = signal(false);

  protected readonly aEliminar = signal<ElementoCatalogo | null>(null);

  protected readonly descriptor = computed(() =>
    this.tipos().find((t) => t.tipo === this.tipo()),
  );
  protected readonly etiqueta = computed(() => this.descriptor()?.etiqueta ?? 'Catálogo');
  protected readonly singular = computed(() => this.descriptor()?.singular ?? 'elemento');
  protected readonly formularioAbierto = computed(
    () => this.creando() || this.editando() !== null,
  );

  private readonly busqueda$ = new Subject<string>();
  private tipoCargado: TipoCatalogo | null = null;

  constructor() {
    this.repositorio.tiposDisponibles().subscribe({
      next: (tipos) => this.tipos.set(tipos),
      error: () => this.notificaciones.aviso('No fue posible cargar la lista de catálogos'),
    });

    this.busqueda$
      .pipe(debounceTime(320), distinctUntilChanged(), takeUntilDestroyed())
      .subscribe(() => {
        this.pagina.set(1);
        this.cargar();
      });

    // El componente se reutiliza al navegar entre catalogos —la ruta solo
    // cambia el `:tipo`—, asi que hay que recargar cuando ese valor cambie.
    //
    // Va en un efecto y no en el `(click)` de la pestana: el manejador del
    // clic corre **antes** de que el router actualice la ruta, de modo que
    // alli `tipo()` es todavia el catalogo anterior. Esa era la causa de que
    // hiciera falta pulsar dos veces para ver los datos correctos.
    effect(() => {
      const tipo = this.tipo();
      // Solo `tipo` debe disparar esto. Sin `untracked`, las señales que lee
      // `cargar()` —texto, pagina, filtro— quedarian como dependencias y
      // buscar reiniciaria la pantalla en bucle.
      untracked(() => this.sincronizar(tipo));
    });
  }

  private sincronizar(tipo: TipoCatalogo): void {
    if (this.tipoCargado === tipo) return;
    this.tipoCargado = tipo;
    this.cerrarFormulario();
    this.texto.set('');
    this.pagina.set(1);
    this.cargar();
  }

  protected buscar(valor: string): void {
    this.texto.set(valor);
    this.busqueda$.next(valor.trim());
  }

  protected cargar(): void {
    this.cargando.set(true);
    this.repositorio
      .listar(
        this.tipo(),
        {
          texto: this.texto().trim() || undefined,
          activo: this.soloActivos() === '' ? undefined : this.soloActivos() === 'true',
        },
        { pagina: this.pagina(), tamano: this.tamano(), ordenarPor: 'orden' },
      )
      .subscribe({
        next: (pagina) => {
          this.datos.set(pagina);
          this.cargando.set(false);
        },
        error: (error: ErrorApi) => {
          this.cargando.set(false);
          this.notificaciones.error('No fue posible cargar el catálogo', error.mensaje);
        },
      });
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

  // ------------------------------------------------------------ formulario
  protected abrirCreacion(): void {
    this.editando.set(null);
    this.creando.set(true);
    this.codigo.set('');
    this.nombre.set('');
    this.descripcion.set('');
    this.activo.set(true);
    this.orden.set(this.datos().total);
    this.codigoErp.set('');
  }

  protected abrirEdicion(elemento: ElementoCatalogo): void {
    this.creando.set(false);
    this.editando.set(elemento);
    this.codigo.set(elemento.codigo);
    this.nombre.set(elemento.nombre);
    this.descripcion.set(elemento.descripcion);
    this.activo.set(elemento.activo);
    this.orden.set(elemento.orden);
    this.codigoErp.set(elemento.codigoErp ?? '');
  }

  protected cerrarFormulario(): void {
    this.creando.set(false);
    this.editando.set(null);
  }

  protected guardar(): void {
    if (!this.nombre().trim()) {
      this.notificaciones.aviso('El nombre es obligatorio');
      return;
    }

    this.guardando.set(true);
    const alTerminar = {
      next: () => {
        this.guardando.set(false);
        this.cerrarFormulario();
        this.notificaciones.exito(
          this.editando() ? 'Elemento actualizado' : 'Elemento agregado',
        );
        this.cargar();
      },
      error: (error: ErrorApi) => {
        this.guardando.set(false);
        this.notificaciones.error('No fue posible guardar', error.mensaje);
      },
    };

    const enEdicion = this.editando();
    if (enEdicion) {
      this.repositorio
        .actualizar(this.tipo(), enEdicion.id, {
          nombre: this.nombre().trim(),
          descripcion: this.descripcion().trim(),
          activo: this.activo(),
          orden: this.orden(),
          codigoErp: this.codigoErp().trim(),
        })
        .subscribe(alTerminar);
      return;
    }

    if (!this.codigo().trim()) {
      this.guardando.set(false);
      this.notificaciones.aviso('El código es obligatorio');
      return;
    }
    this.repositorio
      .crear(this.tipo(), {
        codigo: this.codigo().trim(),
        nombre: this.nombre().trim(),
        descripcion: this.descripcion().trim(),
        activo: this.activo(),
        orden: this.orden(),
        codigoErp: this.codigoErp().trim(),
      })
      .subscribe(alTerminar);
  }

  protected alternarEstado(elemento: ElementoCatalogo): void {
    this.repositorio
      .actualizar(this.tipo(), elemento.id, { activo: !elemento.activo })
      .subscribe({
        next: () => {
          this.notificaciones.exito(
            elemento.activo ? 'Elemento desactivado' : 'Elemento activado',
          );
          this.cargar();
        },
        error: (error: ErrorApi) =>
          this.notificaciones.error('No fue posible cambiar el estado', error.mensaje),
      });
  }

  protected eliminar(): void {
    const elemento = this.aEliminar();
    if (!elemento) return;

    this.repositorio.eliminar(this.tipo(), elemento.id).subscribe({
      next: () => {
        this.aEliminar.set(null);
        this.notificaciones.exito('Elemento eliminado');
        this.cargar();
      },
      error: (error: ErrorApi) => {
        this.aEliminar.set(null);
        // 422 significa que hay filas del distributivo apuntando a el.
        if (error.estado === 422) {
          this.notificaciones.aviso('No se puede eliminar', error.mensaje);
          return;
        }
        this.notificaciones.error('No fue posible eliminar', error.mensaje);
      },
    });
  }

  /** Muestra los atributos propios del catálogo (año/periodo del PAO, alias…). */
  protected atributosLegibles(elemento: ElementoCatalogo): string {
    const entradas = Object.entries(elemento.atributos ?? {});
    if (entradas.length === 0) return '';
    return entradas.map(([k, v]) => `${k}: ${String(v)}`).join(' · ');
  }
}
