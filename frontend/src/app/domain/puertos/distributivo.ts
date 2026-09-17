/** Puertos del distributivo docente. */

import type { Observable } from 'rxjs';

import type {
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
  PeticionResumen,
  ResultadoCapturaAsignaturas,
  ResultadoCargaPao,
  ResumenComparativo,
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
   * Carreras que existen en esos periodos y facultades.
   *
   * Es la relacion entre facultades y carreras, derivada de los datos: doce
   * carreras se dictan en dos facultades a la vez, asi que no puede vivir en
   * una columna del catalogo.
   */
  abstract carrerasDisponibles(
    paoIds: readonly string[],
    facultadIds: readonly string[],
  ): Observable<readonly OpcionSelector[]>;

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
    paoId?: string,
    paoAnteriorId?: string,
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
  ): Observable<ResumenComparativo>;

  /** Descarga un resumen. Sale del mismo calculo que la pantalla. */
  abstract exportarResumen(
    peticion: PeticionResumen,
    formato: FormatoReporte,
  ): Observable<ArchivoDescarga>;
}
