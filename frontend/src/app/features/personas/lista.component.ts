import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { Subject, debounceTime, distinctUntilChanged } from 'rxjs';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';

import { NotificacionesService } from '@core/notificaciones.service';
import { SesionStore } from '@core/sesion.store';
import {
  ETIQUETAS_ESTADO_CONSULTA,
  ETIQUETAS_VINCULACION,
  Permiso,
  TONO_ESTADO_CONSULTA,
  TipoVinculacion,
  type ErrorApi,
  type FiltroPersonas,
  type Pagina,
  type Persona,
  paginaVacia,
} from '@domain/modelos';
import { RepositorioPersonas } from '@domain/puertos';
import { CargandoComponent } from '@shared/componentes/cargando.component';
import { InsigniaComponent } from '@shared/componentes/insignia.component';
import { PaginadorComponent } from '@shared/componentes/paginador.component';
import { VacioComponent } from '@shared/componentes/vacio.component';
import { PermisoDirective } from '@shared/directivas/permiso.directive';
import { DesdeHacePipe } from '@shared/pipes/formato.pipe';

@Component({
  selector: 'ute-lista-personas',
  standalone: true,
  imports: [
    FormsModule,
    RouterLink,
    CargandoComponent,
    InsigniaComponent,
    PaginadorComponent,
    VacioComponent,
    PermisoDirective,
    DesdeHacePipe,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './lista.component.html',
  styleUrl: './lista.component.scss',
})
export class ListaPersonasComponent {
  private readonly repositorio = inject(RepositorioPersonas);
  private readonly notificaciones = inject(NotificacionesService);
  private readonly router = inject(Router);
  private readonly ruta = inject(ActivatedRoute);
  protected readonly sesion = inject(SesionStore);

  protected readonly Permiso = Permiso;
  protected readonly ETIQUETAS_VINCULACION = ETIQUETAS_VINCULACION;
  protected readonly vinculaciones = Object.values(TipoVinculacion);

  protected readonly datos = signal<Pagina<Persona>>(paginaVacia<Persona>());
  protected readonly cargando = signal(true);

  protected readonly texto = signal('');
  protected readonly filtro = signal<FiltroPersonas>({});
  protected readonly pagina = signal(1);
  protected readonly tamano = signal(25);
  protected readonly ordenarPor = signal<string>('apellidos');
  protected readonly descendente = signal(false);

  /** La busqueda se retrasa para no lanzar una peticion por cada tecla. */
  private readonly busqueda$ = new Subject<string>();

  constructor() {
    this.busqueda$
      .pipe(debounceTime(320), distinctUntilChanged(), takeUntilDestroyed())
      .subscribe((valor) => {
        this.filtro.update((f) => ({ ...f, texto: valor || undefined }));
        this.pagina.set(1);
        this.cargar();
      });

    // Los filtros llegan por query string: el tablero enlaza aqui con
    // `nuncaConsultadas=true`, y asi el enlace es compartible y recargable.
    const parametros = this.ruta.snapshot.queryParamMap;
    const inicial: FiltroPersonas = {
      nuncaConsultadas: parametros.get('nuncaConsultadas') === 'true' || undefined,
      conTitulos: parametros.has('conTitulos')
        ? parametros.get('conTitulos') === 'true'
        : undefined,
      activo: parametros.has('activo') ? parametros.get('activo') === 'true' : undefined,
    };
    this.filtro.set(inicial);
    this.cargar();
  }

  protected buscar(valor: string): void {
    this.texto.set(valor);
    this.busqueda$.next(valor.trim());
  }

  protected aplicarFiltro(cambios: Partial<FiltroPersonas>): void {
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

  protected abrir(persona: Persona): void {
    void this.router.navigate(['/personas', persona.id]);
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
          this.notificaciones.error('No fue posible cargar el listado', error.mensaje);
        },
      });
  }

  protected etiquetaEstado(persona: Persona): string {
    return persona.ultimaConsultaEstado
      ? ETIQUETAS_ESTADO_CONSULTA[persona.ultimaConsultaEstado]
      : 'Sin consultar';
  }

  protected tonoEstado(persona: Persona): 'exito' | 'aviso' | 'error' | 'neutro' | 'info' {
    return persona.ultimaConsultaEstado
      ? TONO_ESTADO_CONSULTA[persona.ultimaConsultaEstado]
      : 'neutro';
  }

  protected get hayFiltrosActivos(): boolean {
    const f = this.filtro();
    return Object.values(f).some((v) => v !== undefined && v !== '');
  }
}
