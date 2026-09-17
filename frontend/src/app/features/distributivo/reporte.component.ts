import { DecimalPipe } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  computed,
  effect,
  inject,
  signal,
  untracked,
  type WritableSignal,
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
  protected readonly paosSeleccionados = signal<readonly string[]>([]);
  protected readonly facultadesSeleccionadas = signal<readonly string[]>([]);
  protected readonly carrerasSeleccionadas = signal<readonly string[]>([]);
  protected readonly formato = signal<FormatoReporte>(FormatoReporte.XLSX);
  protected readonly incluirAuditoria = signal(false);
  protected readonly filtroCarrera = signal('');
  protected readonly filtroPeriodo = signal('');

  protected readonly vista = signal<VistaPreviaReporte | null>(null);
  protected readonly cargandoVista = signal(false);
  protected readonly generando = signal(false);

  protected readonly plantillaActual = computed(() =>
    this.plantillas().find((p) => p.codigo === this.plantilla()),
  );

  /**
   * Carreras que existen en los periodos y facultades elegidos.
   *
   * Las pide al backend en lugar de filtrar el catalogo completo, porque la
   * relacion entre facultades y carreras no vive en una columna: doce carreras
   * se dictan en dos facultades a la vez. Con 278 carreras, ofrecerlas todas
   * cuando ya se marco una facultad convierte el selector en una busqueda a
   * ciegas.
   */
  private readonly carrerasDelAmbito = signal<readonly OpcionSelector[]>([]);

  /**
   * Facultades con filas en los periodos elegidos.
   *
   * Mismo motivo que las carreras y uno propio: `FO`, `FCIC`, `CEL` y `ETECH`
   * dejaron de existir en la reestructuracion de 2026-1 y siguen en el
   * catalogo porque siguen en el historico. Ofrecerlas al reportar un periodo
   * reciente lleva a marcar una que devuelve cero filas.
   */
  private readonly facultadesDelAmbito = signal<readonly OpcionSelector[]>([]);
  protected readonly cargandoAmbito = signal(false);

  protected readonly periodosDisponibles = computed<readonly OpcionSelector[]>(() =>
    this.filtrar(this.catalogos.de(TipoCatalogo.PAO), this.filtroPeriodo()),
  );

  protected readonly facultadesDisponibles = computed<readonly OpcionSelector[]>(() =>
    this.facultadesDelAmbito(),
  );

  protected readonly carrerasDisponibles = computed<readonly OpcionSelector[]>(() =>
    this.filtrar(this.carrerasDelAmbito(), this.filtroCarrera()),
  );

  /** Busca en el nombre y en el codigo: el periodo se conoce por los dos. */
  private filtrar(
    opciones: readonly OpcionSelector[],
    texto: string,
  ): readonly OpcionSelector[] {
    const patron = texto.trim().toLowerCase();
    if (!patron) return opciones;
    return opciones.filter(
      (o) =>
        o.nombre.toLowerCase().includes(patron) || o.codigo.toLowerCase().includes(patron),
    );
  }

  protected readonly puedeGenerar = computed(
    () => this.paosSeleccionados().length > 0 && !this.generando(),
  );

  protected readonly resumenSeleccion = computed(() =>
    this.resumir(TipoCatalogo.CARRERA, this.carrerasSeleccionadas(), 'Todas las carreras', 'carreras'),
  );

  protected readonly resumenPeriodos = computed(() =>
    this.resumir(
      TipoCatalogo.PAO,
      this.paosSeleccionados(),
      'Ninguno seleccionado',
      'periodos',
      'seleccionados',
    ),
  );

  protected readonly resumenFacultades = computed(() =>
    this.resumir(
      TipoCatalogo.FACULTAD,
      this.facultadesSeleccionadas(),
      'Todas las facultades',
      'facultades',
    ),
  );

  /** Un nombre si se eligio uno, un recuento si son varios. */
  private resumir(
    tipo: TipoCatalogo,
    seleccion: readonly string[],
    vacio: string,
    plural: string,
    // «periodos seleccionados», «carreras seleccionadas»: el genero lo decide
    // el sustantivo, no la plantilla.
    participio: 'seleccionados' | 'seleccionadas' = 'seleccionadas',
  ): string {
    if (seleccion.length === 0) return vacio;
    if (seleccion.length === 1) return this.catalogos.nombreDe(tipo, seleccion[0]);
    return `${seleccion.length} ${plural} ${participio}`;
  }

  constructor() {
    this.catalogos.cargar();
    this.cargarPlantillas();

    // Los catalogos llegan de forma asincrona: se espera a que esten para
    // preseleccionar el periodo, en lugar de intentarlo una vez y fallar la
    // carrera. Se marca solo el mas reciente, que es lo que se reporta casi
    // siempre; quien necesite varios los agrega.
    effect(() => {
      const paos = this.catalogos.de(TipoCatalogo.PAO);
      if (paos.length > 0 && this.paosSeleccionados().length === 0) {
        const ultimo = [...paos].sort((a, b) => b.codigo.localeCompare(a.codigo))[0];
        this.paosSeleccionados.set([ultimo.id]);
      }
    });

    // Cada vez que cambia lo elegido se vuelve a preguntar que hay dentro.
    // Va en un efecto y no en cada `alternar` para no repetir la llamada en
    // tres sitios.
    effect(() => {
      const paos = this.paosSeleccionados();
      const facultades = this.facultadesSeleccionadas();
      if (paos.length === 0) {
        this.facultadesDelAmbito.set([]);
        this.carrerasDelAmbito.set([]);
        return;
      }
      untracked(() => this.recargarAmbito(paos, facultades));
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

  /** Marca o desmarca un elemento en cualquiera de las tres listas. */
  private alternar(
    seleccion: WritableSignal<readonly string[]>,
    id: string,
    marcado: boolean,
  ): void {
    seleccion.update((lista) =>
      marcado ? [...new Set([...lista, id])] : lista.filter((x) => x !== id),
    );
    // Lo previsualizado deja de corresponder con lo elegido.
    this.vista.set(null);
  }

  protected alternarPao(id: string, marcado: boolean): void {
    this.alternar(this.paosSeleccionados, id, marcado);
  }

  protected alternarFacultad(id: string, marcada: boolean): void {
    this.alternar(this.facultadesSeleccionadas, id, marcada);
  }

  protected alternarCarrera(id: string, marcada: boolean): void {
    this.alternar(this.carrerasSeleccionadas, id, marcada);
  }

  private recargarAmbito(paos: readonly string[], facultades: readonly string[]): void {
    this.cargandoAmbito.set(true);
    this.repositorio.ambitoDisponible(paos, facultades).subscribe({
      next: (ambito) => {
        this.facultadesDelAmbito.set(ambito.facultades);
        this.carrerasDelAmbito.set(ambito.carreras);
        this.cargandoAmbito.set(false);

        // Lo que ya no cabe en el ambito deja de estar marcado: si no, el
        // archivo saldria filtrado por una carrera que la pantalla ya no
        // muestra y nadie entenderia por que faltan filas.
        this.podar(this.facultadesSeleccionadas, ambito.facultades);
        this.podar(this.carrerasSeleccionadas, ambito.carreras);
      },
      error: (error: ErrorApi) => {
        this.cargandoAmbito.set(false);
        this.notificaciones.error('No fue posible cargar el ambito', error.mensaje);
      },
    });
  }

  private podar(
    seleccion: WritableSignal<readonly string[]>,
    vigentes: readonly OpcionSelector[],
  ): void {
    const validos = new Set(vigentes.map((o) => o.id));
    seleccion.update((sel) => sel.filter((id) => validos.has(id)));
  }

  protected seleccionarTodas(): void {
    this.carrerasSeleccionadas.set(this.carrerasDisponibles().map((c) => c.id));
    this.vista.set(null);
  }

  /** «Todos» y «Ninguno» de las otras dos listas, con la misma mecanica. */
  protected marcarTodosLosPeriodos(): void {
    this.paosSeleccionados.set(this.periodosDisponibles().map((o) => o.id));
    this.vista.set(null);
  }

  protected limpiarPeriodos(): void {
    this.paosSeleccionados.set([]);
    this.vista.set(null);
  }

  protected marcarTodasLasFacultades(): void {
    this.facultadesSeleccionadas.set(this.facultadesDisponibles().map((o) => o.id));
    this.vista.set(null);
  }

  protected limpiarFacultades(): void {
    this.facultadesSeleccionadas.set([]);
    this.vista.set(null);
  }

  protected limpiarSeleccion(): void {
    this.carrerasSeleccionadas.set([]);
    this.vista.set(null);
  }

  protected previsualizar(): void {
    if (this.paosSeleccionados().length === 0) {
      this.notificaciones.aviso('Seleccione al menos un periodo académico');
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
    if (this.paosSeleccionados().length === 0) {
      this.notificaciones.aviso('Seleccione al menos un periodo académico');
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
      paoIds: this.paosSeleccionados(),
      facultadIds: this.facultadesSeleccionadas(),
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
