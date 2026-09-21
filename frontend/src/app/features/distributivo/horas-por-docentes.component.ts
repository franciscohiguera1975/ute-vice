import { DatePipe, DecimalPipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';

import { CatalogosStore } from '@core/catalogos.store';
import { DescargaService } from '@core/descarga.service';
import { NotificacionesService } from '@core/notificaciones.service';
import {
  FormatoReporte,
  Permiso,
  TipoCatalogo,
  type ErrorApi,
  type PeriodoConFilas,
  type ResumenDeHoras,
  type TablaDeHoras,
} from '@domain/modelos';
import { RepositorioDistributivo } from '@domain/puertos';
import { CargandoComponent } from '@shared/componentes/cargando.component';
import { PermisoDirective } from '@shared/directivas/permiso.directive';
import { VacioComponent } from '@shared/componentes/vacio.component';

/** Un semestre con todos sus periodos: lo que se marca de un clic. */
interface Semestre {
  readonly clave: string;
  readonly periodos: readonly PeriodoConFilas[];
  readonly filas: number;
}

/**
 * Horas por docentes: horas de `Da` por carrera y facultad, en un PAO.
 *
 * Examina **un** grupo de periodos, no dos: a diferencia de los resumenes, no
 * hay nada que comparar aqui, solo un corte del distributivo. Sigue siendo un
 * grupo y no un periodo suelto porque un semestre son varios —tecnologia,
 * grado y posgrado, mas sus interciclos—.
 *
 * Se puede acotar a una dedicacion —tiempo parcial, tiempo completo, medio
 * tiempo…— o dejarlas todas.
 */
@Component({
  selector: 'ute-horas-por-docentes-distributivo',
  standalone: true,
  imports: [DatePipe, DecimalPipe, CargandoComponent, VacioComponent, PermisoDirective],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './horas-por-docentes.component.html',
  styleUrl: './horas-por-docentes.component.scss',
})
export class HorasPorDocentesDistributivoComponent {
  private readonly repositorio = inject(RepositorioDistributivo);
  private readonly notificaciones = inject(NotificacionesService);
  private readonly catalogos = inject(CatalogosStore);
  private readonly descarga = inject(DescargaService);

  protected readonly Permiso = Permiso;

  protected readonly datos = signal<ResumenDeHoras | null>(null);
  protected readonly cargando = signal(true);

  /** Formato en curso, o `null`. Evita disparar dos descargas a la vez. */
  protected readonly descargando = signal<FormatoReporte | null>(null);
  /** Que tabla se esta descargando, para saber cual botonera deshabilitar. */
  protected readonly tablaDescargando = signal<TablaDeHoras | null>(null);

  protected readonly formatos = [
    { valor: FormatoReporte.XLSX, etiqueta: 'Excel' },
    { valor: FormatoReporte.CSV, etiqueta: 'CSV' },
    { valor: FormatoReporte.PDF, etiqueta: 'PDF' },
  ];

  /** Ids elegidos. Vacio: el backend propone el semestre mas reciente. */
  protected readonly grupo = signal<readonly string[]>([]);

  /** `null` es «Todas»: no se filtra por dedicacion. */
  protected readonly dedicacionId = signal<string | null>(null);
  protected readonly dedicaciones = computed(() => this.catalogos.de(TipoCatalogo.DEDICACION));

  /** Umbral del reporte de docentes con pocas horas de Da. */
  protected readonly menosDe = signal(5);

  protected readonly semestres = computed<readonly Semestre[]>(() => {
    const por = new Map<string, PeriodoConFilas[]>();
    for (const p of this.datos()?.periodos ?? []) {
      // Sin semestre en los atributos, se deriva del codigo: `2026-2` sale de
      // `262651` como `20` + `26` + `-` + `2`.
      const clave = p.semestre || `20${p.codigo.slice(0, 2)}-${p.codigo.slice(2, 3)}`;
      por.set(clave, [...(por.get(clave) ?? []), p]);
    }
    return [...por.entries()]
      .map(([clave, periodos]) => ({
        clave,
        periodos,
        filas: periodos.reduce((suma, p) => suma + p.filas, 0),
      }))
      .sort((x, y) => y.clave.localeCompare(x.clave));
  });

  constructor() {
    this.catalogos.cargar();
    this.cargar();
  }

  protected cargar(): void {
    this.cargando.set(true);
    this.repositorio
      .horasPorDocentes(this.grupo(), this.dedicacionId() ?? undefined, this.menosDe())
      .subscribe({
        next: (datos) => {
          this.datos.set(datos);
          // El backend propone el semestre mas reciente cuando no se pide nada;
          // se refleja en los chips para que la pantalla diga que examina.
          if (this.grupo().length === 0) {
            const buscados = new Set(datos.grupo?.codigos ?? []);
            this.grupo.set(datos.periodos.filter((p) => buscados.has(p.codigo)).map((p) => p.id));
          }
          this.cargando.set(false);
        },
        error: (error: ErrorApi) => {
          this.notificaciones.error(error.mensaje ?? 'No se pudo calcular las horas por docentes');
          this.cargando.set(false);
        },
      });
  }

  protected seleccionado(id: string): boolean {
    return this.grupo().includes(id);
  }

  protected semestreCompleto(semestre: Semestre): boolean {
    return semestre.periodos.every((p) => this.seleccionado(p.id));
  }

  protected alternarSemestre(semestre: Semestre): void {
    const ids = semestre.periodos.map((p) => p.id);
    const quitar = this.semestreCompleto(semestre);
    this.grupo.update((actual) =>
      quitar ? actual.filter((id) => !ids.includes(id)) : [...new Set([...actual, ...ids])],
    );
  }

  protected alternarPeriodo(id: string): void {
    this.grupo.update((actual) =>
      actual.includes(id) ? actual.filter((x) => x !== id) : [...actual, id],
    );
  }

  protected limpiar(): void {
    this.grupo.set([]);
  }

  protected elegirDedicacion(id: string | null): void {
    this.dedicacionId.set(id);
  }

  protected actualizarMenosDe(evento: Event): void {
    const valor = Number((evento.target as HTMLInputElement).value);
    if (Number.isFinite(valor) && valor >= 0) this.menosDe.set(valor);
  }

  protected codigosDelGrupo(): string {
    return this.datos()?.grupo?.codigos.join(' · ') || 'sin periodos';
  }

  // ------------------------------------------------------------- descarga
  /**
   * Descarga la tabla elegida, en el formato indicado.
   *
   * Sale del mismo caso de uso que alimenta la pantalla: el archivo no puede
   * decir otra cosa que lo que se esta viendo.
   */
  protected descargar(resumen: TablaDeHoras, formato: FormatoReporte): void {
    if (this.descargando()) return;
    this.descargando.set(formato);
    this.tablaDescargando.set(resumen);

    this.repositorio
      .exportarHorasPorDocentes(
        {
          resumen,
          grupo: this.grupo(),
          dedicacionId: this.dedicacionId() ?? undefined,
          menosDe: resumen === 'bajo_horas' ? this.menosDe() : undefined,
        },
        formato,
      )
      .subscribe({
        next: (archivo) => {
          this.descarga.guardar(archivo);
          this.descargando.set(null);
          this.tablaDescargando.set(null);
        },
        error: (error: ErrorApi) => {
          this.descargando.set(null);
          this.tablaDescargando.set(null);
          this.notificaciones.error(error.mensaje ?? 'No se pudo generar el archivo');
        },
      });
  }
}
