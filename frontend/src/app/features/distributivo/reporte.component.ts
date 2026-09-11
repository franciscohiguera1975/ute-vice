import { DecimalPipe } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  computed,
  effect,
  inject,
  signal,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';

import { DescargaService } from '@core/descarga.service';
import { NotificacionesService } from '@core/notificaciones.service';
import {
  FormatoReporte,
  TipoCatalogo,
  type ColumnaReporte,
  type ErrorApi,
  type OpcionSelector,
  type PlantillaReporte,
  type VistaPreviaReporte,
} from '@domain/modelos';
import { RepositorioDistributivo } from '@domain/puertos';
import { CargandoComponent } from '@shared/componentes/cargando.component';

import { CatalogosStore } from '@core/catalogos.store';

/**
 * Exportacion del distributivo.
 *
 * Se elige el periodo, una facultad y **varias carreras a la vez**, que es como
 * se emite: una facultad con el conjunto de sus programas.
 *
 * Las plantillas y sus columnas las pide al backend en lugar de tenerlas fijas:
 * un formato nuevo alla aparece solo aqui, sin tocar esta pantalla.
 */
@Component({
  selector: 'ute-reporte-distributivo',
  standalone: true,
  imports: [DecimalPipe, FormsModule, RouterLink, CargandoComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './reporte.component.html',
  styleUrl: './reporte.component.scss',
})
export class ReporteDistributivoComponent {
  private readonly repositorio = inject(RepositorioDistributivo);
  private readonly descarga = inject(DescargaService);
  private readonly notificaciones = inject(NotificacionesService);
  protected readonly catalogos = inject(CatalogosStore);

  protected readonly TipoCatalogo = TipoCatalogo;
  protected readonly formatos = [
    { valor: FormatoReporte.XLSX, etiqueta: 'Excel', nota: 'Con el formato de la plantilla' },
    { valor: FormatoReporte.CSV, etiqueta: 'CSV', nota: 'Para cargar en otro sistema' },
    { valor: FormatoReporte.PDF, etiqueta: 'PDF', nota: 'Para imprimir o adjuntar' },
  ];

  protected readonly plantillas = signal<readonly PlantillaReporte[]>([]);
  protected readonly plantilla = signal('');
  protected readonly paoId = signal('');
  protected readonly facultadId = signal('');
  protected readonly carrerasSeleccionadas = signal<readonly string[]>([]);
  protected readonly formato = signal<FormatoReporte>(FormatoReporte.XLSX);
  protected readonly incluirAuditoria = signal(false);
  protected readonly filtroCarrera = signal('');

  protected readonly vista = signal<VistaPreviaReporte | null>(null);
  protected readonly cargandoVista = signal(false);
  protected readonly generando = signal(false);

  protected readonly plantillaActual = computed(() =>
    this.plantillas().find((p) => p.codigo === this.plantilla()),
  );

  /**
   * Carreras que se pueden elegir.
   *
   * Se listan todas y no solo las de la facultad: el backend acota igual, y asi
   * quien lo necesite puede mezclar carreras de varias facultades.
   */
  protected readonly carrerasDisponibles = computed<readonly OpcionSelector[]>(() => {
    const patron = this.filtroCarrera().trim().toLowerCase();
    const todas = this.catalogos.de(TipoCatalogo.CARRERA);
    if (!patron) return todas;
    return todas.filter((c) => c.nombre.toLowerCase().includes(patron));
  });

  protected readonly puedeGenerar = computed(() => this.paoId() !== '' && !this.generando());

  protected readonly resumenSeleccion = computed(() => {
    const seleccion = this.carrerasSeleccionadas();
    if (seleccion.length === 0) return 'Todas las carreras';
    if (seleccion.length === 1) {
      return this.catalogos.nombreDe(TipoCatalogo.CARRERA, seleccion[0]);
    }
    return `${seleccion.length} carreras seleccionadas`;
  });

  constructor() {
    this.catalogos.cargar();
    this.cargarPlantillas();

    // Los catalogos llegan de forma asincrona: se espera a que esten para
    // elegir el periodo, en lugar de intentarlo una vez y fallar la carrera.
    effect(() => {
      const paos = this.catalogos.de(TipoCatalogo.PAO);
      if (paos.length > 0 && !this.paoId()) {
        const ultimo = [...paos].sort((a, b) => b.codigo.localeCompare(a.codigo))[0];
        this.paoId.set(ultimo.id);
      }
    });
  }

  private cargarPlantillas(): void {
    this.repositorio.plantillasReporte().subscribe({
      next: (plantillas) => {
        this.plantillas.set(plantillas);
        if (!this.plantilla() && plantillas.length > 0) {
          this.plantilla.set(plantillas[0].codigo);
        }
      },
      error: (error: ErrorApi) =>
        this.notificaciones.error('No fue posible cargar las plantillas', error.mensaje),
    });
  }

  protected cambiarPlantilla(codigo: string): void {
    this.plantilla.set(codigo);
    if (!this.plantillaActual()?.admiteAuditoria) this.incluirAuditoria.set(false);
    this.vista.set(null);
  }

  protected cambiarPao(valor: string): void {
    this.paoId.set(valor);
    this.vista.set(null);
  }

  protected cambiarFacultad(valor: string): void {
    this.facultadId.set(valor);
    this.vista.set(null);
  }

  protected alternarCarrera(id: string, marcada: boolean): void {
    this.carrerasSeleccionadas.update((lista) =>
      marcada ? [...new Set([...lista, id])] : lista.filter((c) => c !== id),
    );
    this.vista.set(null);
  }

  protected estaSeleccionada(id: string): boolean {
    return this.carrerasSeleccionadas().includes(id);
  }

  protected seleccionarTodas(): void {
    this.carrerasSeleccionadas.set(this.carrerasDisponibles().map((c) => c.id));
    this.vista.set(null);
  }

  protected limpiarSeleccion(): void {
    this.carrerasSeleccionadas.set([]);
    this.vista.set(null);
  }

  protected previsualizar(): void {
    if (!this.paoId()) {
      this.notificaciones.aviso('Seleccione un periodo académico');
      return;
    }

    this.cargandoVista.set(true);
    this.repositorio.vistaPreviaReporte(this.peticion()).subscribe({
      next: (vista) => {
        this.vista.set(vista);
        this.cargandoVista.set(false);
        if (vista.totalFilas === 0) {
          this.notificaciones.aviso(
            'Sin resultados',
            'Ningún docente cumple los filtros seleccionados.',
          );
        }
      },
      error: (error: ErrorApi) => {
        this.cargandoVista.set(false);
        this.notificaciones.error('No fue posible previsualizar', error.mensaje);
      },
    });
  }

  protected generar(): void {
    if (!this.paoId()) {
      this.notificaciones.aviso('Seleccione un periodo académico');
      return;
    }

    this.generando.set(true);
    this.repositorio.generarReporte(this.peticion(), this.formato()).subscribe({
      next: (archivo) => {
        this.generando.set(false);
        this.descarga.guardar(archivo);
        this.notificaciones.exito('Reporte generado', archivo.nombre);
      },
      error: (error: ErrorApi) => {
        this.generando.set(false);
        // 422 cubre dos casos que el backend ya explica con precision: que
        // ningun docente cumpla los filtros, y que la plantilla tenga mas
        // columnas de las que caben en un PDF. Se muestra su mensaje tal cual.
        if (error.estado === 422) {
          this.notificaciones.aviso('No se generó el archivo', error.mensaje);
          return;
        }
        this.notificaciones.error('No fue posible generar el reporte', error.mensaje);
      },
    });
  }

  private peticion() {
    return {
      paoId: this.paoId(),
      facultadId: this.facultadId() || null,
      carreraIds: this.carrerasSeleccionadas(),
      plantilla: this.plantilla() || null,
      incluirColumnasAuditoria: this.incluirAuditoria(),
    };
  }

  /**
   * Color de cabecera de la plantilla, cuando la trae.
   *
   * El backend lo entrega en RRGGBB para Excel; aqui se usa apenas insinuado
   * para que la vista previa se reconozca sin desentonar con el tema.
   */
  protected fondoCabecera(columna: ColumnaReporte): string | null {
    return columna.colorCabecera ? `#${columna.colorCabecera}` : null;
  }

  protected valor(fila: readonly unknown[], indice: number): string {
    const dato = fila[indice];
    return dato === null || dato === undefined || dato === '' ? '' : String(dato);
  }
}
