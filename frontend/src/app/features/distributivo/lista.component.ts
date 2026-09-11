import { DecimalPipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { Subject, debounceTime, distinctUntilChanged } from 'rxjs';

import { NotificacionesService } from '@core/notificaciones.service';
import { SesionStore } from '@core/sesion.store';
import {
  CLAVES_HORAS,
  ETIQUETAS_BLOQUE,
  Permiso,
  TipoCatalogo,
  paginaVacia,
  type ErrorApi,
  type FilaDistributivo,
  type FiltroDistributivo,
  type Pagina,
  type ResumenDistributivo,
} from '@domain/modelos';
import { RepositorioDistributivo } from '@domain/puertos';
import { CargandoComponent } from '@shared/componentes/cargando.component';
import { ConfirmarComponent } from '@shared/componentes/confirmar.component';
import { InsigniaComponent } from '@shared/componentes/insignia.component';
import { PaginadorComponent } from '@shared/componentes/paginador.component';
import { VacioComponent } from '@shared/componentes/vacio.component';
import { PermisoDirective } from '@shared/directivas/permiso.directive';

import { CatalogosStore } from './catalogos.store';

@Component({
  selector: 'ute-lista-distributivo',
  standalone: true,
  imports: [
    DecimalPipe,
    FormsModule,
    RouterLink,
    CargandoComponent,
    ConfirmarComponent,
    InsigniaComponent,
    PaginadorComponent,
    VacioComponent,
    PermisoDirective,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './lista.component.html',
  styleUrl: './lista.component.scss',
})
export class ListaDistributivoComponent {
  private readonly repositorio = inject(RepositorioDistributivo);
  private readonly notificaciones = inject(NotificacionesService);
  private readonly ruta = inject(ActivatedRoute);
  protected readonly catalogos = inject(CatalogosStore);
  protected readonly sesion = inject(SesionStore);

  protected readonly Permiso = Permiso;
  protected readonly TipoCatalogo = TipoCatalogo;
  protected readonly CLAVES_HORAS = CLAVES_HORAS;
  protected readonly ETIQUETAS_BLOQUE = ETIQUETAS_BLOQUE;
  protected readonly bloques = Object.keys(CLAVES_HORAS) as (keyof typeof CLAVES_HORAS)[];

  protected readonly datos = signal<Pagina<FilaDistributivo>>(paginaVacia<FilaDistributivo>());
  protected readonly resumen = signal<ResumenDistributivo | null>(null);
  protected readonly cargando = signal(true);
  protected readonly texto = signal('');
  protected readonly filtro = signal<FiltroDistributivo>({});
  protected readonly pagina = signal(1);
  protected readonly tamano = signal(25);
  protected readonly ordenarPor = signal('docente');
  protected readonly descendente = signal(false);

  // --- Edicion ---
  protected readonly editando = signal<FilaDistributivo | null>(null);
  protected readonly guardando = signal(false);
  protected readonly asignatura = signal('');
  protected readonly observaciones = signal('');
  protected readonly horas = signal<Record<string, number>>({});
  protected readonly selecciones = signal<Record<string, string>>({});

  protected readonly aEliminar = signal<FilaDistributivo | null>(null);

  /** Total en vivo mientras se editan las horas. */
  protected readonly totalEditado = computed(() =>
    Math.round(
      Object.values(this.horas()).reduce((suma, v) => suma + (Number(v) || 0), 0) * 100,
    ) / 100,
  );

  protected readonly hayFiltros = computed(() =>
    Object.values(this.filtro()).some(
      (v) => v !== undefined && v !== '' && (!Array.isArray(v) || v.length > 0),
    ),
  );

  private readonly busqueda$ = new Subject<string>();

  constructor() {
    this.catalogos.cargar();

    this.busqueda$
      .pipe(debounceTime(320), distinctUntilChanged(), takeUntilDestroyed())
      .subscribe((valor) => {
        this.filtro.update((f) => ({ ...f, texto: valor || undefined }));
        this.pagina.set(1);
        this.cargar();
      });

    // El tablero y otros listados enlazan aquí ya filtrados.
    const p = this.ruta.snapshot.queryParamMap;
    this.filtro.set({
      paoId: p.get('paoId') ?? undefined,
      facultadId: p.get('facultadId') ?? undefined,
      carreraId: p.get('carreraId') ?? undefined,
      docenteId: p.get('docenteId') ?? undefined,
      sinAsignatura: p.get('sinAsignatura') === 'true' || undefined,
    });
    this.cargar();
  }

  protected buscar(valor: string): void {
    this.texto.set(valor);
    this.busqueda$.next(valor.trim());
  }

  protected aplicar(cambios: Partial<FiltroDistributivo>): void {
    this.filtro.update((f) => ({ ...f, ...cambios }));
    this.pagina.set(1);
    this.cargar();
  }

  protected limpiar(): void {
    this.texto.set('');
    this.filtro.set({});
    this.pagina.set(1);
    this.cargar();
  }

  protected ordenar(campo: string): void {
    if (this.ordenarPor() === campo) {
      this.descendente.update((v) => !v);
    } else {
      this.ordenarPor.set(campo);
      this.descendente.set(false);
    }
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

  protected cargar(): void {
    this.cargando.set(true);
    const filtro = this.filtro();

    this.repositorio
      .listar(filtro, {
        pagina: this.pagina(),
        tamano: this.tamano(),
        ordenarPor: this.ordenarPor(),
        descendente: this.descendente(),
      })
      .subscribe({
        next: (pagina) => {
          this.datos.set(pagina);
          this.cargando.set(false);
        },
        error: (error: ErrorApi) => {
          this.cargando.set(false);
          this.notificaciones.error('No fue posible cargar el distributivo', error.mensaje);
        },
      });

    this.repositorio.resumen(filtro).subscribe({
      next: (resumen) => this.resumen.set(resumen),
      error: () => this.resumen.set(null),
    });
  }

  // -------------------------------------------------------------- edicion
  protected abrirEdicion(fila: FilaDistributivo): void {
    this.editando.set(fila);
    this.asignatura.set(fila.asignatura ?? '');
    this.observaciones.set(fila.observaciones ?? '');
    this.horas.set({
      ...fila.horas.docencia,
      ...fila.horas.gestion,
      ...fila.horas.investigacion,
      ...fila.horas.vinculacion,
    });
    this.selecciones.set({
      facultadId: fila.facultadId,
      carreraId: fila.carreraId,
      programaId: fila.programaId ?? '',
      sedeId: fila.sedeId ?? '',
      nivelId: fila.nivelId ?? '',
      titularidadId: fila.titularidadId ?? '',
      dedicacionId: fila.dedicacionId ?? '',
      categoriaId: fila.categoriaId ?? '',
      tipoTituloId: fila.tipoTituloId ?? '',
    });
  }

  protected cerrarEdicion(): void {
    this.editando.set(null);
  }

  protected fijarHora(clave: string, valor: string): void {
    const numero = Number(valor);
    this.horas.update((h) => ({ ...h, [clave]: Number.isFinite(numero) ? numero : 0 }));
  }

  protected fijarSeleccion(campo: string, valor: string): void {
    this.selecciones.update((s) => ({ ...s, [campo]: valor }));
  }

  protected guardar(): void {
    const fila = this.editando();
    if (!fila) return;

    this.guardando.set(true);
    const s = this.selecciones();
    // Un selector vacío significa «sin valor»: viaja como null para que el
    // backend lo limpie, no como cadena vacía.
    const opcional = (clave: string): string | null => s[clave]?.trim() || null;

    this.repositorio
      .actualizar(fila.id, {
        facultadId: s['facultadId'] || undefined,
        carreraId: s['carreraId'] || undefined,
        programaId: opcional('programaId'),
        sedeId: opcional('sedeId'),
        nivelId: opcional('nivelId'),
        titularidadId: opcional('titularidadId'),
        dedicacionId: opcional('dedicacionId'),
        categoriaId: opcional('categoriaId'),
        tipoTituloId: opcional('tipoTituloId'),
        asignatura: this.asignatura().trim() || null,
        observaciones: this.observaciones().trim() || null,
        horas: this.horas(),
      })
      .subscribe({
        next: () => {
          this.guardando.set(false);
          this.cerrarEdicion();
          this.notificaciones.exito('Fila actualizada');
          this.cargar();
        },
        error: (error: ErrorApi) => {
          this.guardando.set(false);
          this.notificaciones.error('No fue posible guardar', error.mensaje);
        },
      });
  }

  protected eliminar(): void {
    const fila = this.aEliminar();
    if (!fila) return;
    this.repositorio.eliminar(fila.id).subscribe({
      next: () => {
        this.aEliminar.set(null);
        this.notificaciones.exito('Fila eliminada');
        this.cargar();
      },
      error: (error: ErrorApi) => {
        this.aEliminar.set(null);
        this.notificaciones.error('No fue posible eliminar', error.mensaje);
      },
    });
  }
}
