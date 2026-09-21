import { DatePipe, DecimalPipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';

import { NotificacionesService } from '@core/notificaciones.service';
import {
  type ErrorApi,
  type PeriodoConFilas,
  type ResumenTiempoParcial,
} from '@domain/modelos';
import { RepositorioDistributivo } from '@domain/puertos';
import { CargandoComponent } from '@shared/componentes/cargando.component';
import { VacioComponent } from '@shared/componentes/vacio.component';

/** Un semestre con todos sus periodos: lo que se marca de un clic. */
interface Semestre {
  readonly clave: string;
  readonly periodos: readonly PeriodoConFilas[];
  readonly filas: number;
}

/**
 * Docentes a tiempo parcial de un PAO, con sus horas de `Da` por carrera y
 * facultad.
 *
 * Examina **un** grupo de periodos, no dos: a diferencia de los resumenes, no
 * hay nada que comparar aqui, solo un corte del distributivo. Sigue siendo un
 * grupo y no un periodo suelto porque un semestre son varios —tecnologia,
 * grado y posgrado, mas sus interciclos—.
 */
@Component({
  selector: 'ute-tiempo-parcial-distributivo',
  standalone: true,
  imports: [DatePipe, DecimalPipe, CargandoComponent, VacioComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './tiempo-parcial.component.html',
  styleUrl: './tiempo-parcial.component.scss',
})
export class TiempoParcialDistributivoComponent {
  private readonly repositorio = inject(RepositorioDistributivo);
  private readonly notificaciones = inject(NotificacionesService);

  protected readonly datos = signal<ResumenTiempoParcial | null>(null);
  protected readonly cargando = signal(true);

  /** Ids elegidos. Vacio: el backend propone el semestre mas reciente. */
  protected readonly grupo = signal<readonly string[]>([]);

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
    this.cargar();
  }

  protected cargar(): void {
    this.cargando.set(true);
    this.repositorio.tiempoParcial(this.grupo()).subscribe({
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
        this.notificaciones.error(error.mensaje ?? 'No se pudo calcular el tiempo parcial');
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

  protected codigosDelGrupo(): string {
    return this.datos()?.grupo?.codigos.join(' · ') || 'sin periodos';
  }
}
