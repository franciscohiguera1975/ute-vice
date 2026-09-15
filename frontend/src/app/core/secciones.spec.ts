/**
 * Pruebas de la ruta de aterrizaje.
 *
 * Existen por un fallo que dejo la aplicacion en blanco en produccion: todo el
 * mundo era enviado a `/tablero`, y la guarda que denegaba el acceso redirigia
 * otra vez a `/tablero`. Con los cuatro roles originales no se veia, porque
 * todos tenian `dashboard:ver`. El primer rol sin ese permiso —consulta del
 * distributivo— entraba en un bucle de redirecciones.
 *
 * La invariante que se protege es una sola: **`rutaDeInicio` nunca devuelve una
 * ruta cuya guarda vaya a denegar el paso.**
 */

import { Permiso } from '@domain/modelos';

import { RUTA_REFUGIO, SECCIONES, rutaDeInicio } from './secciones';
import type { SesionStore } from './sesion.store';

/** Doble minimo: de `SesionStore` solo se usa `puedeAlguno`. */
function sesionCon(...permisos: readonly Permiso[]): SesionStore {
  const suyos = new Set<string>(permisos);
  return {
    puedeAlguno: (...pedidos: readonly Permiso[]) => pedidos.some((p) => suyos.has(p)),
    autenticado: () => true,
  } as unknown as SesionStore;
}

describe('rutaDeInicio', () => {
  it('lleva al tablero a quien puede verlo', () => {
    expect(rutaDeInicio(sesionCon(Permiso.DASHBOARD_VER, Permiso.PERSONAS_LEER))).toBe('/tablero');
  });

  it('lleva al distributivo al rol de consulta del distributivo', () => {
    // El caso exacto que rompio: sin `dashboard:ver`.
    const sesion = sesionCon(
      Permiso.DISTRIBUTIVO_LEER,
      Permiso.CATALOGOS_LEER,
      Permiso.REPORTES_GENERAR,
    );
    expect(rutaDeInicio(sesion)).toBe('/distributivo');
  });

  it('respeta el orden del menu cuando hay varias disponibles', () => {
    expect(rutaDeInicio(sesionCon(Permiso.REPORTES_GENERAR, Permiso.TITULOS_LEER))).toBe(
      '/titulos',
    );
  });

  it('cae en el perfil cuando no hay ninguna seccion disponible', () => {
    expect(rutaDeInicio(sesionCon())).toBe(RUTA_REFUGIO);
  });

  // ------------------------------------------------------------ la invariante
  it('nunca devuelve una ruta que el usuario no pueda abrir', () => {
    // Cada combinacion de un solo permiso, que es como se construyen los roles
    // estrechos y donde aparecio el fallo.
    for (const seccion of SECCIONES) {
      for (const permiso of seccion.permisos) {
        const sesion = sesionCon(permiso);
        const destino = rutaDeInicio(sesion);
        if (destino === RUTA_REFUGIO) continue; // el perfil no tiene guarda

        const alQueVa = SECCIONES.find((s) => s.ruta === destino);
        expect(alQueVa)
          .withContext(`${destino} no esta entre las secciones`)
          .toBeDefined();
        expect(sesion.puedeAlguno(...alQueVa!.permisos))
          .withContext(`con ${permiso} se aterriza en ${destino}, que la guarda denegaria`)
          .toBeTrue();
      }
    }
  });

  it('el perfil no figura como seccion: es el refugio, no una opcion del menu', () => {
    expect(SECCIONES.some((s) => s.ruta === RUTA_REFUGIO)).toBeFalse();
  });
});
