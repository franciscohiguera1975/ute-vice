/** Puertos del distributivo docente. */

import type { Observable } from 'rxjs';

import type {
  AmbitoDisponible,
  ArchivoDescarga,
  CambiosDocente,
  CambiosElementoCatalogo,
  CambiosFilaDistributivo,
  DatosDocente,
  DatosElementoCatalogo,
  DatosFilaDistributivo,
  DescriptorCatalogo,
  Docente,
  DocenteDetalle,
  ElementoCatalogo,
  FilaDistributivo,
  FiltroCatalogo,
  FiltroDistributivo,
  FiltroDocentes,
  FormatoReporte,
  OpcionSelector,
  Pagina,
  ParametrosPaginacion,
  AsignaturaCapturada,
  PeticionReporteDistributivo,
  PlantillaReporte,
  PeticionCargaPao,
  PeticionHorasPorDocentes,
  PeticionResumen,
  ResultadoCapturaAsignaturas,
  ResultadoCargaPao,
  ResumenComparativo,
  ResumenDeHoras,
  ResumenDistributivo,
  TableroDistributivo,
  TipoCatalogo,
  VistaPreviaReporte,
} from '../modelos';

/**
 * Un solo puerto para los doce catalogos.
 *
 * El `tipo` selecciona el catalogo, igual que en el backend. Declarar doce
 * puertos identicos solo multiplicaria el codigo del lado del cliente.
 */
export abstract class RepositorioCatalogos {
  abstract tiposDisponibles(): Observable<readonly DescriptorCatalogo[]>;

  /** Catalogo completo, sin paginar, para poblar un selector. */
  abstract opciones(
    tipo: TipoCatalogo,
    incluirInactivos?: boolean,
  ): Observable<readonly OpcionSelector[]>;

  abstract listar(
    tipo: TipoCatalogo,
    filtro: FiltroCatalogo,
    paginacion: ParametrosPaginacion,
  ): Observable<Pagina<ElementoCatalogo>>;

  abstract obtener(tipo: TipoCatalogo, id: string): Observable<ElementoCatalogo>;
  abstract crear(tipo: TipoCatalogo, datos: DatosElementoCatalogo): Observable<ElementoCatalogo>;
  abstract actualizar(
    tipo: TipoCatalogo,
    id: string,
    cambios: CambiosElementoCatalogo,
  ): Observable<ElementoCatalogo>;
  abstract eliminar(tipo: TipoCatalogo, id: string): Observable<void>;
}

export abstract class RepositorioDocentes {
  abstract listar(
    filtro: FiltroDocentes,
    paginacion: ParametrosPaginacion,
  ): Observable<Pagina<Docente>>;
  abstract obtener(id: string): Observable<DocenteDetalle>;
  abstract crear(datos: DatosDocente): Observable<Docente>;
  abstract actualizar(id: string, cambios: CambiosDocente): Observable<Docente>;
  abstract eliminar(id: string): Observable<void>;
}

export abstract class RepositorioDistributivo {
  abstract listar(
    filtro: FiltroDistributivo,
    paginacion: ParametrosPaginacion,
  ): Observable<Pagina<FilaDistributivo>>;
  abstract resumen(filtro: FiltroDistributivo): Observable<ResumenDistributivo>;
  abstract obtener(id: string): Observable<FilaDistributivo>;
  abstract crear(datos: DatosFilaDistributivo): Observable<FilaDistributivo>;
  abstract actualizar(
    id: string,
    cambios: CambiosFilaDistributivo,
  ): Observable<FilaDistributivo>;
  abstract eliminar(id: string): Observable<void>;

  /**
   * Registra la asignatura de varias filas de una vez.
   *
   * No viene del consolidado y hay que capturarla a mano sobre cientos de
   * filas; una peticion por fila haria la tarea impracticable.
   */
  abstract capturarAsignaturas(
    filas: readonly AsignaturaCapturada[],
  ): Observable<ResultadoCapturaAsignaturas>;

  /** Que plantillas de exportacion ofrece el backend. */
  abstract plantillasReporte(): Observable<readonly PlantillaReporte[]>;

  /**
   * Facultades y carreras que existen en lo ya elegido.
   *
   * Ninguna de las dos relaciones vive en una columna del catalogo: doce
   * carreras se dictan en dos facultades a la vez, y cuatro facultades dejaron
   * de existir en 2026-1 sin desaparecer del historico. Se derivan de los
   * datos, que es lo unico que no miente.
   */
  abstract ambitoDisponible(
    paoIds: readonly string[],
    facultadIds: readonly string[],
  ): Observable<AmbitoDisponible>;

  /** Muestra el reporte antes de descargarlo. */
  abstract vistaPreviaReporte(
    peticion: PeticionReporteDistributivo,
  ): Observable<VistaPreviaReporte>;

  abstract generarReporte(
    peticion: PeticionReporteDistributivo,
    formato: FormatoReporte,
  ): Observable<ArchivoDescarga>;

  /**
   * Indicadores de validacion de dos periodos, uno frente al otro.
   *
   * Sin periodos, el backend elige el mas reciente y el anterior del mismo
   * tipo —grado con grado, interciclo con interciclo—.
   */
  abstract tablero(
    grupoA: readonly string[],
    grupoB: readonly string[],
  ): Observable<TableroDistributivo>;

  /** Sube un distributivo exportado por el sistema academico. */
  abstract cargarPao(peticion: PeticionCargaPao): Observable<ResultadoCargaPao>;

  /**
   * Compara dos grupos de periodos.
   *
   * Son grupos y no periodos sueltos porque un semestre son varios: `2026-1`
   * es tecnologia, grado y posgrado, mas sus interciclos.
   */
  abstract resumenes(
    grupoA: readonly string[],
    grupoB: readonly string[],
    dedicacionIds?: readonly string[],
  ): Observable<ResumenComparativo>;

  /** Descarga un resumen. Sale del mismo calculo que la pantalla. */
  abstract exportarResumen(
    peticion: PeticionResumen,
    formato: FormatoReporte,
  ): Observable<ArchivoDescarga>;

  /**
   * Docentes de un PAO, con sus horas de `Da` por carrera y facultad.
   *
   * Es un grupo y no periodos sueltos por lo mismo que en `resumenes`: un
   * semestre son varios. Sin grupo, el backend propone el semestre mas
   * reciente. Sin dedicacion, se incluyen todas. `menosDe` ademas lista los
   * docentes con menos de esas horas de `Da`.
   */
  abstract horasPorDocentes(
    grupo: readonly string[],
    dedicacionId?: string,
    menosDe?: number,
  ): Observable<ResumenDeHoras>;

  /** Descarga una tabla de «Horas por docentes». Sale del mismo calculo que la pantalla. */
  abstract exportarHorasPorDocentes(
    peticion: PeticionHorasPorDocentes,
    formato: FormatoReporte,
  ): Observable<ArchivoDescarga>;
}
