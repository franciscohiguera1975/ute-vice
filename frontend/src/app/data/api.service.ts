/**
 * Cliente HTTP de bajo nivel.
 *
 * Concentra lo que de otro modo se repetiria en cada repositorio: la URL base,
 * la conversion de nomenclatura y la construccion de parametros. Los
 * repositorios quedan reducidos a declarar rutas y tipos.
 */

import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { type Observable, map } from 'rxjs';

import type { ArchivoDescarga, Pagina, ParametrosPaginacion } from '@domain/modelos';
import { environment } from '@env/environment';

import { aCamel, aParametros, aSnake, nombreDeContentDisposition } from './mapeo';

@Injectable({ providedIn: 'root' })
export class ApiService {
  private readonly http = inject(HttpClient);
  private readonly base = environment.apiUrl.replace(/\/$/, '');

  private url(ruta: string): string {
    return `${this.base}${ruta.startsWith('/') ? ruta : `/${ruta}`}`;
  }

  private construirParametros(objeto?: object): HttpParams {
    let parametros = new HttpParams();
    for (const [clave, valor] of Object.entries(aParametros(objeto ?? {}))) {
      parametros = parametros.set(clave, valor);
    }
    return parametros;
  }

  get<T>(ruta: string, parametros?: object): Observable<T> {
    return this.http
      .get<unknown>(this.url(ruta), { params: this.construirParametros(parametros) })
      .pipe(map((respuesta) => aCamel<T>(respuesta)));
  }

  post<T>(ruta: string, cuerpo?: unknown, parametros?: object): Observable<T> {
    return this.http
      .post<unknown>(this.url(ruta), aSnake(cuerpo ?? {}), {
        params: this.construirParametros(parametros),
      })
      .pipe(map((respuesta) => aCamel<T>(respuesta)));
  }

  patch<T>(ruta: string, cuerpo: unknown): Observable<T> {
    return this.http
      .patch<unknown>(this.url(ruta), aSnake(cuerpo))
      .pipe(map((respuesta) => aCamel<T>(respuesta)));
  }

  delete<T>(ruta: string): Observable<T> {
    return this.http.delete<unknown>(this.url(ruta)).pipe(map((r) => aCamel<T>(r)));
  }

  /**
   * Listado paginado. Combina el filtro y la paginacion en un solo query.
   *
   * El filtro se acepta como objeto cualquiera —no como `Record`— para que los
   * repositorios puedan pasar sus interfaces de filtro tipadas sin necesidad de
   * declararles una firma de indice, que las abriria a claves arbitrarias.
   */
  listar<T>(ruta: string, filtro: object, paginacion: ParametrosPaginacion): Observable<Pagina<T>> {
    return this.get<Pagina<T>>(ruta, { ...filtro, ...paginacion });
  }

  /**
   * Descarga un archivo generado a partir de un cuerpo.
   *
   * Existe aparte de `descargar` porque algunos reportes se piden por POST: sus
   * filtros —varias carreras a la vez, por ejemplo— no caben comodamente en una
   * query string.
   */
  descargarConCuerpo(
    ruta: string,
    cuerpo: unknown,
    parametros: object,
    nombrePorDefecto: string,
  ): Observable<ArchivoDescarga> {
    return this.http
      .post(this.url(ruta), aSnake(cuerpo), {
        params: this.construirParametros(parametros),
        responseType: 'blob',
        observe: 'response',
      })
      .pipe(map((respuesta) => this.aArchivo(respuesta, nombrePorDefecto)));
  }

  private aArchivo(
    respuesta: { body: Blob | null; headers: { get(nombre: string): string | null } },
    nombrePorDefecto: string,
  ): ArchivoDescarga {
    const contenido = respuesta.body ?? new Blob();
    return {
      nombre: nombreDeContentDisposition(
        respuesta.headers.get('content-disposition'),
        nombrePorDefecto,
      ),
      contenido,
      tipoMime: contenido.type || 'application/octet-stream',
    };
  }

  /**
   * Descarga un archivo conservando su nombre.
   *
   * El nombre viene en `Content-Disposition`; para poder leerlo desde otro
   * origen, el backend expone esa cabecera en su politica de CORS.
   */
  descargar(ruta: string, parametros: object, nombrePorDefecto: string): Observable<ArchivoDescarga> {
    return this.http
      .get(this.url(ruta), {
        params: this.construirParametros(parametros),
        responseType: 'blob',
        observe: 'response',
      })
      .pipe(map((respuesta) => this.aArchivo(respuesta, nombrePorDefecto)));
  }
}
