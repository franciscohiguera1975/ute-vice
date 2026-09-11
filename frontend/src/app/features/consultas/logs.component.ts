import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, RouterLink } from '@angular/router';

import { NotificacionesService } from '@core/notificaciones.service';
import {
  ETIQUETAS_ESTADO_CONSULTA,
  EstadoConsulta,
  TONO_ESTADO_CONSULTA,
  type ConsultaLog,
  type ErrorApi,
  type FiltroLogs,
  type Pagina,
  paginaVacia,
} from '@domain/modelos';
import { RepositorioConsultas } from '@domain/puertos';
import { SesionStore } from '@core/sesion.store';
import { Permiso } from '@domain/modelos';
import { PermisoDirective } from '@shared/directivas/permiso.directive';
import { CargandoComponent } from '@shared/componentes/cargando.component';
import { InsigniaComponent } from '@shared/componentes/insignia.component';
import { PaginadorComponent } from '@shared/componentes/paginador.component';
import { VacioComponent } from '@shared/componentes/vacio.component';
import { DuracionPipe, FechaLocalPipe } from '@shared/pipes/formato.pipe';

import { SubmenuConsultasComponent } from './submenu.component';

@Component({
  selector: 'ute-logs',
  standalone: true,
  imports: [
    FormsModule,
    RouterLink,
    CargandoComponent,
    InsigniaComponent,
    PaginadorComponent,
    VacioComponent,
    FechaLocalPipe,
    DuracionPipe,
    SubmenuConsultasComponent,
    PermisoDirective,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './logs.component.html',
  styleUrl: './consultas.scss',
})
export class LogsComponent {
  private readonly repositorio = inject(RepositorioConsultas);
  private readonly notificaciones = inject(NotificacionesService);
  private readonly ruta = inject(ActivatedRoute);

  protected readonly sesion = inject(SesionStore);
  protected readonly Permiso = Permiso;
  protected readonly ETIQUETAS_ESTADO_CONSULTA = ETIQUETAS_ESTADO_CONSULTA;
  protected readonly TONO_ESTADO_CONSULTA = TONO_ESTADO_CONSULTA;
  protected readonly estados = Object.values(EstadoConsulta);

  protected readonly datos = signal<Pagina<ConsultaLog>>(paginaVacia<ConsultaLog>());
  protected readonly cargando = signal(true);
  protected readonly filtro = signal<FiltroLogs>({});
  protected readonly pagina = signal(1);
  protected readonly tamano = signal(25);
  /** Registro cuyo detalle de cambios esta desplegado. */
  protected readonly expandido = signal<string | null>(null);

  // --- Resolucion de desafios ---
  /** Desafio que el operador esta atendiendo, y su respuesta. */
  protected readonly desafioActivo = signal<ConsultaLog | null>(null);
  protected readonly respuestaDesafio = signal('');
  protected readonly resolviendo = signal(false);

  constructor() {
    const parametros = this.ruta.snapshot.queryParamMap;
    this.filtro.set({
      personaId: parametros.get('personaId') ?? undefined,
      jobId: parametros.get('jobId') ?? undefined,
      soloErrores: parametros.get('soloErrores') === 'true' || undefined,
      soloConCambios: parametros.get('soloConCambios') === 'true' || undefined,
    });
    this.cargar();
  }

  protected aplicarFiltro(cambios: Partial<FiltroLogs>): void {
    this.filtro.update((f) => ({ ...f, ...cambios }));
    this.pagina.set(1);
    this.cargar();
  }

  protected limpiarFiltros(): void {
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

  protected alternarDetalle(registro: ConsultaLog): void {
    this.expandido.update((actual) => (actual === registro.id ? null : registro.id));
  }

  protected cargar(): void {
    this.cargando.set(true);
    this.repositorio
      .listarLogs(this.filtro(), { pagina: this.pagina(), tamano: this.tamano() })
      .subscribe({
        next: (pagina) => {
          this.datos.set(pagina);
          this.cargando.set(false);
        },
        error: (error: ErrorApi) => {
          this.cargando.set(false);
          this.notificaciones.error('No fue posible cargar el historico', error.mensaje);
        },
      });
  }

  /** Campos modificados de un cambio, para mostrarlos como pares. */
  protected camposDe(detalle: Record<string, unknown>): { campo: string; anterior: string; nuevo: string }[] {
    const campos = detalle['campos'];
    if (!campos || typeof campos !== 'object') return [];
    return Object.entries(campos as Record<string, { anterior?: string; nuevo?: string }>).map(
      ([campo, valores]) => ({
        campo,
        anterior: valores.anterior ?? '—',
        nuevo: valores.nuevo ?? '—',
      }),
    );
  }

  protected abrirDesafio(registro: ConsultaLog): void {
    this.desafioActivo.set(registro);
    this.respuestaDesafio.set('');
  }

  /**
   * Envia la respuesta que escribio una persona.
   *
   * El sistema no resuelve el desafio por su cuenta: lo muestra y un operador
   * con el permiso `consultas:resolver` lo transcribe. Es una decision de
   * diseno explicita, documentada en `docs/SENESCYT.md`.
   */
  protected resolverDesafio(): void {
    const registro = this.desafioActivo();
    const respuesta = this.respuestaDesafio().trim();
    if (!registro?.desafioId || !respuesta) return;

    this.resolviendo.set(true);
    this.repositorio.resolverDesafio(registro.desafioId, respuesta).subscribe({
      next: (resultado) => {
        this.resolviendo.set(false);
        this.desafioActivo.set(null);

        if (resultado.requiereIntervencion) {
          this.notificaciones.aviso(
            'La respuesta no fue aceptada',
            'El proveedor emitio un desafio nuevo. Vuelva a intentarlo.',
          );
        } else {
          this.notificaciones.exito('Consulta completada', resultado.log.resumen);
        }
        this.cargar();
      },
      error: (error: ErrorApi) => {
        this.resolviendo.set(false);
        this.notificaciones.error('No fue posible resolver el desafio', error.mensaje);
      },
    });
  }

  protected get hayFiltrosActivos(): boolean {
    return Object.values(this.filtro()).some((v) => v !== undefined && v !== '');
  }
}
