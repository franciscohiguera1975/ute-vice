/** Implementaciones HTTP de los puertos del distributivo docente. */

import { Injectable, inject } from '@angular/core';
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
  PeticionCargaPao,
  PeticionReporteDistributivo,
  PeticionResumen,
  PlantillaReporte,
  ResultadoCapturaAsignaturas,
  ResultadoCargaPao,
  ResumenComparativo,
  ResumenDistributivo,
  ResumenTiempoParcial,
  TableroDistributivo,
  TipoCatalogo,
  VistaPreviaReporte,
} from '@domain/modelos';
import {
  RepositorioCatalogos,
  RepositorioDistributivo,
  RepositorioDocentes,
} from '@domain/puertos';

import { ApiService } from './api.service';

@Injectable()
export class CatalogosHttp extends RepositorioCatalogos {
  private readonly api = inject(ApiService);

  tiposDisponibles(): Observable<readonly DescriptorCatalogo[]> {
    return this.api.get<DescriptorCatalogo[]>('/catalogos');
  }

  opciones(
    tipo: TipoCatalogo,
    incluirInactivos = false,
  ): Observable<readonly OpcionSelector[]> {
    return this.api.get<OpcionSelector[]>(`/catalogos/${tipo}/opciones`, {
      incluirInactivos,
    });
  }

  listar(
    tipo: TipoCatalogo,
    filtro: FiltroCatalogo,
    paginacion: ParametrosPaginacion,
  ): Observable<Pagina<ElementoCatalogo>> {
    return this.api.listar<ElementoCatalogo>(`/catalogos/${tipo}`, filtro, paginacion);
  }

  obtener(tipo: TipoCatalogo, id: string): Observable<ElementoCatalogo> {
    return this.api.get<ElementoCatalogo>(`/catalogos/${tipo}/${id}`);
  }

  crear(tipo: TipoCatalogo, datos: DatosElementoCatalogo): Observable<ElementoCatalogo> {
    return this.api.post<ElementoCatalogo>(`/catalogos/${tipo}`, datos);
  }

  actualizar(
    tipo: TipoCatalogo,
    id: string,
    cambios: CambiosElementoCatalogo,
  ): Observable<ElementoCatalogo> {
    return this.api.patch<ElementoCatalogo>(`/catalogos/${tipo}/${id}`, cambios);
  }

  eliminar(tipo: TipoCatalogo, id: string): Observable<void> {
    return this.api.delete<void>(`/catalogos/${tipo}/${id}`);
  }
}

@Injectable()
export class DocentesHttp extends RepositorioDocentes {
  private readonly api = inject(ApiService);

  listar(
    filtro: FiltroDocentes,
    paginacion: ParametrosPaginacion,
  ): Observable<Pagina<Docente>> {
    return this.api.listar<Docente>('/docentes', filtro, paginacion);
  }

  obtener(id: string): Observable<DocenteDetalle> {
    return this.api.get<DocenteDetalle>(`/docentes/${id}`);
  }

  crear(datos: DatosDocente): Observable<Docente> {
    return this.api.post<Docente>('/docentes', datos);
  }

  actualizar(id: string, cambios: CambiosDocente): Observable<Docente> {
    return this.api.patch<Docente>(`/docentes/${id}`, cambios);
  }

  eliminar(id: string): Observable<void> {
    return this.api.delete<void>(`/docentes/${id}`);
  }
}

@Injectable()
export class DistributivoHttp extends RepositorioDistributivo {
  private readonly api = inject(ApiService);

  listar(
    filtro: FiltroDistributivo,
    paginacion: ParametrosPaginacion,
  ): Observable<Pagina<FilaDistributivo>> {
    return this.api.listar<FilaDistributivo>('/distributivo', filtro, paginacion);
  }

  resumen(filtro: FiltroDistributivo): Observable<ResumenDistributivo> {
    return this.api.get<ResumenDistributivo>('/distributivo/resumen', filtro);
  }

  obtener(id: string): Observable<FilaDistributivo> {
    return this.api.get<FilaDistributivo>(`/distributivo/${id}`);
  }

  crear(datos: DatosFilaDistributivo): Observable<FilaDistributivo> {
    return this.api.post<FilaDistributivo>('/distributivo', datos);
  }

  actualizar(id: string, cambios: CambiosFilaDistributivo): Observable<FilaDistributivo> {
    return this.api.patch<FilaDistributivo>(`/distributivo/${id}`, cambios);
  }

  eliminar(id: string): Observable<void> {
    return this.api.delete<void>(`/distributivo/${id}`);
  }

  capturarAsignaturas(
    filas: readonly AsignaturaCapturada[],
  ): Observable<ResultadoCapturaAsignaturas> {
    return this.api.patch<ResultadoCapturaAsignaturas>('/distributivo/asignaturas', { filas });
  }

  plantillasReporte(): Observable<readonly PlantillaReporte[]> {
    return this.api.get<readonly PlantillaReporte[]>('/reportes/distributivo/plantillas');
  }

  ambitoDisponible(
    paoIds: readonly string[],
    facultadIds: readonly string[],
  ): Observable<AmbitoDisponible> {
    return this.api.get<AmbitoDisponible>('/reportes/distributivo/ambito', {
      paoIds,
      facultadIds,
    });
  }

  vistaPreviaReporte(peticion: PeticionReporteDistributivo): Observable<VistaPreviaReporte> {
    return this.api.post<VistaPreviaReporte>('/reportes/distributivo/vista-previa', peticion);
  }

  generarReporte(
    peticion: PeticionReporteDistributivo,
    formato: FormatoReporte,
  ): Observable<ArchivoDescarga> {
    return this.api.descargarConCuerpo(
      '/reportes/distributivo',
      peticion,
      { formato },
      `distributivo.${formato.toLowerCase()}`,
    );
  }

  tablero(
    grupoA: readonly string[],
    grupoB: readonly string[],
  ): Observable<TableroDistributivo> {
    return this.api.get<TableroDistributivo>('/distributivo/tablero', {
      grupoA,
      grupoB,
    });
  }

  resumenes(
    grupoA: readonly string[],
    grupoB: readonly string[],
    dedicacionIds: readonly string[] = [],
  ): Observable<ResumenComparativo> {
    return this.api.get<ResumenComparativo>('/distributivo/resumenes', {
      grupoA,
      grupoB,
      dedicacionIds,
    });
  }

  exportarResumen(
    peticion: PeticionResumen,
    formato: FormatoReporte,
  ): Observable<ArchivoDescarga> {
    return this.api.descargar(
      '/distributivo/resumenes/exportar',
      { ...peticion, formato },
      `resumen-${peticion.resumen}.${formato.toLowerCase()}`,
    );
  }

  tiempoParcial(grupo: readonly string[]): Observable<ResumenTiempoParcial> {
    return this.api.get<ResumenTiempoParcial>('/distributivo/tiempo-parcial', { grupo });
  }

  cargarPao(peticion: PeticionCargaPao): Observable<ResultadoCargaPao> {
    return this.api.subir<ResultadoCargaPao>(
      '/distributivo/importaciones/pao',
      peticion.archivo,
      {
        semestre: peticion.semestre,
        interciclo: String(peticion.interciclo),
        actualizar_existentes: String(peticion.actualizarExistentes),
        ...(peticion.hoja ? { hoja: peticion.hoja } : {}),
      },
    );
  }
}

/** Enlaza cada puerto del distributivo con su implementacion HTTP. */
export const PROVEEDORES_DISTRIBUTIVO = [
  { provide: RepositorioCatalogos, useClass: CatalogosHttp },
  { provide: RepositorioDocentes, useClass: DocentesHttp },
  { provide: RepositorioDistributivo, useClass: DistributivoHttp },
];
