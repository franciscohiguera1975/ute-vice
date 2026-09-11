import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { Subject, debounceTime, distinctUntilChanged } from 'rxjs';

import { NotificacionesService } from '@core/notificaciones.service';
import {
  ETIQUETAS_ESTADO_TITULO,
  ETIQUETAS_NIVEL,
  ETIQUETAS_ORIGEN,
  EstadoTitulo,
  NivelTitulo,
  Permiso,
  TONO_ESTADO_TITULO,
  type ErrorApi,
  type FiltroTitulos,
  type Pagina,
  type Titulo,
  paginaVacia,
} from '@domain/modelos';
import { RepositorioTitulos } from '@domain/puertos';
import { CargandoComponent } from '@shared/componentes/cargando.component';
import { InsigniaComponent } from '@shared/componentes/insignia.component';
import { PaginadorComponent } from '@shared/componentes/paginador.component';
import { VacioComponent } from '@shared/componentes/vacio.component';
import { PermisoDirective } from '@shared/directivas/permiso.directive';
import { FechaLocalPipe } from '@shared/pipes/formato.pipe';

@Component({
  selector: 'ute-titulos',
  standalone: true,
  imports: [
    FormsModule,
    RouterLink,
    CargandoComponent,
    InsigniaComponent,
    PaginadorComponent,
    VacioComponent,
    PermisoDirective,
    FechaLocalPipe,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './titulos.component.html',
  styleUrl: './titulos.component.scss',
})
export class TitulosComponent {
  private readonly repositorio = inject(RepositorioTitulos);
  private readonly notificaciones = inject(NotificacionesService);
  private readonly ruta = inject(ActivatedRoute);

  protected readonly Permiso = Permiso;
  protected readonly ETIQUETAS_NIVEL = ETIQUETAS_NIVEL;
  protected readonly ETIQUETAS_ESTADO_TITULO = ETIQUETAS_ESTADO_TITULO;
  protected readonly ETIQUETAS_ORIGEN = ETIQUETAS_ORIGEN;
  protected readonly TONO_ESTADO_TITULO = TONO_ESTADO_TITULO;
  protected readonly niveles = Object.values(NivelTitulo);
  protected readonly estados = Object.values(EstadoTitulo);

  protected readonly datos = signal<Pagina<Titulo>>(paginaVacia<Titulo>());
  protected readonly cargando = signal(true);
  protected readonly texto = signal('');
  protected readonly filtro = signal<FiltroTitulos>({});
  protected readonly pagina = signal(1);
  protected readonly tamano = signal(25);
  protected readonly ordenarPor = signal('denominacion');
  protected readonly descendente = signal(false);

  private readonly busqueda$ = new Subject<string>();

  constructor() {
    this.busqueda$
      .pipe(debounceTime(320), distinctUntilChanged(), takeUntilDestroyed())
      .subscribe((valor) => {
        this.filtro.update((f) => ({ ...f, texto: valor || undefined }));
        this.pagina.set(1);
        this.cargar();
      });

    // El tablero enlaza aqui con un estado ya seleccionado.
    const parametros = this.ruta.snapshot.queryParamMap;
    const estado = parametros.get('estado');
    this.filtro.set({
      estado: estado ? (estado as EstadoTitulo) : undefined,
      requiereAtencion: parametros.get('requiereAtencion') === 'true' || undefined,
      personaId: parametros.get('personaId') ?? undefined,
    });
    this.cargar();
  }

  protected buscar(valor: string): void {
    this.texto.set(valor);
    this.busqueda$.next(valor.trim());
  }

  protected aplicarFiltro(cambios: Partial<FiltroTitulos>): void {
    this.filtro.update((f) => ({ ...f, ...cambios }));
    this.pagina.set(1);
    this.cargar();
  }

  protected limpiarFiltros(): void {
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

  protected verificar(titulo: Titulo, evento: Event): void {
    evento.stopPropagation();
    this.repositorio.verificar(titulo.id).subscribe({
      next: () => {
        this.notificaciones.exito('Titulo verificado');
        this.cargar();
      },
      error: (error: ErrorApi) =>
        this.notificaciones.error('No fue posible verificar', error.mensaje),
    });
  }

  protected cargar(): void {
    this.cargando.set(true);
    this.repositorio
      .listar(this.filtro(), {
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
          this.notificaciones.error('No fue posible cargar los titulos', error.mensaje);
        },
      });
  }

  protected get hayFiltrosActivos(): boolean {
    return Object.values(this.filtro()).some((v) => v !== undefined && v !== '');
  }
}
