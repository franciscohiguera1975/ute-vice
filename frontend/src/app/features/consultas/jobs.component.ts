import { DecimalPipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';

import { NotificacionesService } from '@core/notificaciones.service';
import {
  ETIQUETAS_ESTADO_JOB,
  EstadoJob,
  Permiso,
  TONO_ESTADO_JOB,
  type AccionJob,
  type ErrorApi,
  type JobCobertura,
  type Pagina,
  paginaVacia,
} from '@domain/modelos';
import { RepositorioConsultas } from '@domain/puertos';
import { CargandoComponent } from '@shared/componentes/cargando.component';
import { ConfirmarComponent } from '@shared/componentes/confirmar.component';
import { InsigniaComponent } from '@shared/componentes/insignia.component';
import { VacioComponent } from '@shared/componentes/vacio.component';
import { PermisoDirective } from '@shared/directivas/permiso.directive';
import { DesdeHacePipe, FechaLocalPipe } from '@shared/pipes/formato.pipe';

import { SubmenuConsultasComponent } from './submenu.component';

@Component({
  selector: 'ute-jobs',
  standalone: true,
  imports: [
    DecimalPipe,
    FormsModule,
    RouterLink,
    CargandoComponent,
    ConfirmarComponent,
    InsigniaComponent,
    VacioComponent,
    PermisoDirective,
    FechaLocalPipe,
    DesdeHacePipe,
    SubmenuConsultasComponent,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './jobs.component.html',
  styleUrl: './jobs.component.scss',
})
export class JobsComponent {
  private readonly repositorio = inject(RepositorioConsultas);
  private readonly notificaciones = inject(NotificacionesService);

  protected readonly Permiso = Permiso;
  protected readonly ETIQUETAS_ESTADO_JOB = ETIQUETAS_ESTADO_JOB;
  protected readonly TONO_ESTADO_JOB = TONO_ESTADO_JOB;

  protected readonly datos = signal<Pagina<JobCobertura>>(paginaVacia<JobCobertura>());
  protected readonly cargando = signal(true);
  protected readonly avanzando = signal(false);

  // --- Formulario de creacion ---
  protected readonly mostrarFormulario = signal(false);
  protected readonly nombre = signal('');
  protected readonly periodoDias = signal<number | null>(null);
  protected readonly limitePersonas = signal<number | null>(null);
  protected readonly iniciarYa = signal(true);
  protected readonly distribuir = signal(false);
  protected readonly creando = signal(false);

  // --- Confirmacion de cancelacion ---
  protected readonly jobACancelar = signal<JobCobertura | null>(null);

  /** Solo puede haber un job activo: dos romperian la garantia de cobertura. */
  private static readonly ESTADOS_ACTIVOS: readonly EstadoJob[] = [
    EstadoJob.PROGRAMADO,
    EstadoJob.EN_CURSO,
    EstadoJob.PAUSADO,
  ];

  protected readonly jobActivo = computed(() =>
    this.datos().items.find((j) => JobsComponent.ESTADOS_ACTIVOS.includes(j.estado)),
  );

  constructor() {
    this.cargar();
  }

  protected cargar(): void {
    this.cargando.set(true);
    this.repositorio.listarJobs({ pagina: 1, tamano: 25 }).subscribe({
      next: (pagina) => {
        this.datos.set(pagina);
        this.cargando.set(false);
      },
      error: (error: ErrorApi) => {
        this.cargando.set(false);
        this.notificaciones.error('No fue posible cargar las campanas', error.mensaje);
      },
    });
  }

  protected crear(): void {
    const nombre = this.nombre().trim();
    if (nombre.length < 3) {
      this.notificaciones.aviso('El nombre debe tener al menos 3 caracteres');
      return;
    }

    this.creando.set(true);
    this.repositorio
      .crearJob({
        nombre,
        periodoDias: this.periodoDias(),
        limitePersonas: this.limitePersonas(),
        iniciarInmediatamente: this.iniciarYa(),
        distribuirEnPeriodo: this.distribuir(),
      })
      .subscribe({
        next: (creado) => {
          this.creando.set(false);
          this.mostrarFormulario.set(false);
          this.nombre.set('');

          this.notificaciones.exito(
            `Campana creada con ${creado.job.totalItems} persona(s)`,
            `Capacidad estimada: ${creado.consultasDiariasEstimadas} consultas por dia`,
          );

          // Si el periodo no alcanza, la respuesta correcta es ampliarlo, no
          // acelerar el ritmo. El aviso lo dice explicitamente.
          if (creado.advertencia) {
            this.notificaciones.aviso('El periodo podria no alcanzar', creado.advertencia);
          }
          this.cargar();
        },
        error: (error: ErrorApi) => {
          this.creando.set(false);
          this.notificaciones.error('No fue posible crear la campana', error.mensaje);
        },
      });
  }

  protected controlar(job: JobCobertura, accion: AccionJob, motivo?: string): void {
    this.jobACancelar.set(null);
    this.repositorio.controlarJob(job.id, accion, motivo).subscribe({
      next: (actualizado) => {
        this.notificaciones.exito(
          `Campana ${ETIQUETAS_ESTADO_JOB[actualizado.estado].toLowerCase()}`,
        );
        this.cargar();
      },
      error: (error: ErrorApi) =>
        this.notificaciones.error('No fue posible cambiar el estado', error.mensaje),
    });
  }

  /**
   * Ejecuta un paso a mano.
   *
   * Es la via de operacion cuando el planificador automatico esta apagado, y
   * tambien una herramienta de diagnostico: la respuesta explica por que se
   * consulto o por que no.
   */
  protected avanzar(job: JobCobertura): void {
    this.avanzando.set(true);
    this.repositorio.avanzarJob(job.id).subscribe({
      next: (paso) => {
        this.avanzando.set(false);

        if (paso.jobCompletado) {
          this.notificaciones.exito('Cobertura completa del periodo');
        } else if (paso.huboConsulta && paso.resultado) {
          this.notificaciones.info(
            `Consulta procesada: ${paso.resultado.log.resumen}`,
            `Siguiente en ${paso.esperarSegundos} s · ${paso.motivo}`,
          );
        } else {
          this.notificaciones.aviso('No se ejecuto ninguna consulta', paso.motivo);
        }
        this.cargar();
      },
      error: (error: ErrorApi) => {
        this.avanzando.set(false);
        this.notificaciones.error('No fue posible avanzar la campana', error.mensaje);
      },
    });
  }

  protected duracionPeriodo(job: JobCobertura): number {
    const inicio = new Date(job.periodoInicio).getTime();
    const fin = new Date(job.periodoFin).getTime();
    return Math.round((fin - inicio) / 86_400_000);
  }

  protected configuracionLegible(job: JobCobertura): { clave: string; valor: string }[] {
    return Object.entries(job.configuracion).map(([clave, valor]) => ({
      clave: clave.replace(/([A-Z])/g, ' $1').toLowerCase(),
      valor: Array.isArray(valor) ? valor.join(' – ') : String(valor),
    }));
  }
}
