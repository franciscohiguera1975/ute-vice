/**
 * Las secciones de la aplicacion, con el permiso que habilita cada una.
 *
 * Es la unica fuente: de aqui salen el menu y la ruta a la que aterriza cada
 * usuario. Tenerlas en dos sitios fue lo que produjo el fallo que se describe
 * en `rutaDeInicio`.
 */

import type { SesionStore } from './sesion.store';

import { Permiso } from '@domain/modelos';

export interface Seccion {
  readonly ruta: string;
  readonly etiqueta: string;
  readonly icono: string;
  /** Permisos que habilitan la seccion. Basta con tener uno. */
  readonly permisos: readonly Permiso[];
}

/** El orden importa: es el del menu y el de preferencia al aterrizar. */
export const SECCIONES: readonly Seccion[] = [
  { ruta: '/tablero', etiqueta: 'Tablero', icono: '▤', permisos: [Permiso.DASHBOARD_VER] },
  { ruta: '/personas', etiqueta: 'Personas', icono: '☰', permisos: [Permiso.PERSONAS_LEER] },
  { ruta: '/titulos', etiqueta: 'Titulos', icono: '◈', permisos: [Permiso.TITULOS_LEER] },
  { ruta: '/consultas', etiqueta: 'Consultas', icono: '⟳', permisos: [Permiso.CONSULTAS_LEER] },
  {
    ruta: '/distributivo',
    etiqueta: 'Distributivo',
    icono: '▩',
    permisos: [Permiso.DISTRIBUTIVO_LEER],
  },
  {
    ruta: '/distributivo/asignaturas',
    etiqueta: 'Asignaturas',
    icono: '✎',
    permisos: [Permiso.DISTRIBUTIVO_ESCRIBIR],
  },
  { ruta: '/catalogos', etiqueta: 'Catalogos', icono: '⛁', permisos: [Permiso.CATALOGOS_LEER] },
  { ruta: '/reportes', etiqueta: 'Reportes', icono: '▦', permisos: [Permiso.REPORTES_GENERAR] },
  {
    ruta: '/administracion',
    etiqueta: 'Administracion',
    icono: '⚙',
    permisos: [Permiso.USUARIOS_LEER],
  },
];

/**
 * Sin permisos para ninguna seccion, el perfil siempre esta disponible: no
 * tiene guarda mas alla de estar autenticado.
 */
export const RUTA_REFUGIO = '/perfil';

/**
 * La primera seccion que el usuario puede ver.
 *
 * **Nunca devuelve una ruta que su guarda vaya a denegar.** Esa es la razon de
 * existir de esta funcion: el sistema mandaba a todo el mundo a `/tablero`, y
 * la guarda que denegaba el acceso redirigia otra vez a `/tablero`. Con los
 * cuatro roles originales el fallo no se veia, porque todos tenian
 * `dashboard:ver`; el primer rol sin ese permiso dejaba la aplicacion en un
 * bucle de redirecciones y la pantalla en blanco.
 */
export function rutaDeInicio(sesion: SesionStore): string {
  const disponible = SECCIONES.find((s) => sesion.puedeAlguno(...s.permisos));
  return disponible?.ruta ?? RUTA_REFUGIO;
}
