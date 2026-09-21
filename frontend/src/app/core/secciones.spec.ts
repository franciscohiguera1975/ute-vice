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

import { RUTA_REFUGIO, SECCIONES, SECCIONES_PLANAS, rutaDeInicio } from './secciones';
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
    for (const seccion of SECCIONES_PLANAS) {
      for (const permiso of seccion.permisos) {
        const sesion = sesionCon(permiso);
        const destino = rutaDeInicio(sesion);
        if (destino === RUTA_REFUGIO) continue; // el perfil no tiene guarda

        const alQueVa = SECCIONES_PLANAS.find((s) => s.ruta === destino);
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
    expect(SECCIONES_PLANAS.some((s) => s.ruta === RUTA_REFUGIO)).toBeFalse();
  });
});

/**
 * El menu del rol de consulta.
 *
 * Es de solo lectura: ve los indicadores del distributivo —que piden
 * `distributivo:leer` y no `dashboard:ver`, justamente para esto— y no ve la
 * carga de archivos, que modifica datos.
 */
describe('secciones del rol de consulta del distributivo', () => {
  const sesion = sesionCon(
    Permiso.DISTRIBUTIVO_LEER,
    Permiso.CATALOGOS_LEER,
    Permiso.REPORTES_GENERAR,
  );

  const visibles = () =>
    SECCIONES_PLANAS.filter((s) => sesion.puedeAlguno(...s.permisos)).map((s) => s.ruta);

  it('incluye el tablero del distributivo', () => {
    expect(visibles()).toContain('/distributivo/tablero');
  });

  it('no incluye la carga de un PAO', () => {
    expect(visibles()).not.toContain('/distributivo/importar');
  });

  it('no incluye ninguna seccion que escriba', () => {
    expect(visibles()).not.toContain('/distributivo/asignaturas');
    expect(visibles()).not.toContain('/administracion');
  });
});

describe('la carga de un PAO', () => {
  it('solo aparece con permiso de importar', () => {
    const importador = sesionCon(Permiso.DISTRIBUTIVO_IMPORTAR);
    const seccion = SECCIONES_PLANAS.find((s) => s.ruta === '/distributivo/importar');

    expect(seccion).toBeDefined();
    expect(importador.puedeAlguno(...seccion!.permisos)).toBeTrue();
    expect(sesionCon(Permiso.DISTRIBUTIVO_ESCRIBIR).puedeAlguno(...seccion!.permisos)).toBeFalse();
  });
});

/**
 * El grupo «Distributivo».
 *
 * Un grupo se muestra si alguno de sus hijos se muestra: sus permisos son la
 * union de los de ellos. Si eso se desincroniza, un usuario veria un
 * desplegable que al abrirse esta vacio.
 */
describe('agrupacion del menu', () => {
  const grupo = SECCIONES.find((s) => s.hijos !== undefined);

  it('el distributivo es el grupo, con sus seis pantallas y asignaturas', () => {
    expect(grupo?.ruta).toBe('/distributivo');
    expect(grupo?.hijos?.map((h) => h.etiqueta)).toEqual([
      'Registros',
      'Indicadores',
      'Cargar PAO',
      'Reportes',
      'Resumenes',
      'Tiempo parcial',
      'Asignaturas',
    ]);
  });

  it('los permisos del grupo son la union de los de sus hijos', () => {
    const union = new Set((grupo?.hijos ?? []).flatMap((h) => h.permisos));
    expect(new Set(grupo?.permisos ?? [])).toEqual(union);
  });

  it('un grupo nunca se ofrece como destino de aterrizaje', () => {
    // `SECCIONES_PLANAS` son las hojas; el encabezado del grupo no esta.
    expect(SECCIONES_PLANAS.some((s) => s.hijos !== undefined)).toBeFalse();
  });

  it('quien solo puede exportar ve el grupo, y dentro solo Reportes', () => {
    const sesion = sesionCon(Permiso.REPORTES_GENERAR);
    expect(sesion.puedeAlguno(...(grupo?.permisos ?? []))).toBeTrue();
    expect(
      (grupo?.hijos ?? []).filter((h) => sesion.puedeAlguno(...h.permisos)).map((h) => h.ruta),
    ).toEqual(['/distributivo/reporte']);
  });
});

describe('los resumenes', () => {
  it('los ve el rol de consulta: son de solo lectura', () => {
    const consulta = sesionCon(
      Permiso.DISTRIBUTIVO_LEER,
      Permiso.CATALOGOS_LEER,
      Permiso.REPORTES_GENERAR,
    );
    const seccion = SECCIONES_PLANAS.find((s) => s.ruta === '/distributivo/resumenes');

    expect(seccion).toBeDefined();
    expect(consulta.puedeAlguno(...seccion!.permisos)).toBeTrue();
  });
});
