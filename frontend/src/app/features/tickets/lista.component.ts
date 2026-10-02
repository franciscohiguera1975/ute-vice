import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { Subject, debounceTime, distinctUntilChanged } from 'rxjs';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';

import { NotificacionesService } from '@core/notificaciones.service';
import { SesionStore } from '@core/sesion.store';
import {
  ESTADOS_TICKET,
  ETIQUETAS_ESTADO_TICKET,
  ETIQUETAS_PRIORIDAD_TICKET,
  Permiso,
  PRIORIDADES_TICKET,
  TONO_ESTADO_TICKET,
  TONO_PRIORIDAD_TICKET,
  type ErrorApi,
  type FiltroTickets,
  type Pagina,
  type Ticket,
  paginaVacia,
} from '@domain/modelos';
import { RepositorioTickets } from '@domain/puertos';
import { CargandoComponent } from '@shared/componentes/cargando.component';
import { InsigniaComponent } from '@shared/componentes/insignia.component';
import { PaginadorComponent } from '@shared/componentes/paginador.component';
import { VacioComponent } from '@shared/componentes/vacio.component';
import { PermisoDirective } from '@shared/directivas/permiso.directive';
import { DesdeHacePipe } from '@shared/pipes/formato.pipe';

@Component({
  selector: 'ute-lista-tickets',
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
export class ListaTicketsComponent {
  private readonly repositorio = inject(RepositorioTickets);
  private readonly notificaciones = inject(NotificacionesService);
  private readonly router = inject(Router);
  protected readonly sesion = inject(SesionStore);

  protected readonly Permiso = Permiso;
  protected readonly ETIQUETAS_ESTADO_TICKET = ETIQUETAS_ESTADO_TICKET;
  protected readonly TONO_ESTADO_TICKET = TONO_ESTADO_TICKET;
  protected readonly ETIQUETAS_PRIORIDAD_TICKET = ETIQUETAS_PRIORIDAD_TICKET;
  protected readonly TONO_PRIORIDAD_TICKET = TONO_PRIORIDAD_TICKET;
  protected readonly estados = ESTADOS_TICKET;
  protected readonly prioridades = PRIORIDADES_TICKET;

  protected readonly datos = signal<Pagina<Ticket>>(paginaVacia<Ticket>());
  protected readonly cargando = signal(true);

  protected readonly texto = signal('');
  protected readonly filtro = signal<FiltroTickets>({});
  protected readonly pagina = signal(1);
  protected readonly tamano = signal(25);

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

    this.cargar();
  }

  protected buscar(valor: string): void {
    this.texto.set(valor);
    this.busqueda$.next(valor.trim());
  }

  protected aplicarFiltro(cambios: Partial<FiltroTickets>): void {
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

  protected irAPagina(pagina: number): void {
    this.pagina.set(pagina);
    this.cargar();
  }

  protected cambiarTamano(tamano: number): void {
    this.tamano.set(tamano);
    this.pagina.set(1);
    this.cargar();
  }

  protected abrir(ticket: Ticket): void {
    void this.router.navigate(['/tickets', ticket.id]);
  }

  protected cargar(): void {
    this.cargando.set(true);
    this.repositorio
      .listar(this.filtro(), { pagina: this.pagina(), tamano: this.tamano() })
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

  protected get hayFiltrosActivos(): boolean {
    const f = this.filtro();
    return Object.values(f).some((v) => v !== undefined && v !== '');
  }
}
