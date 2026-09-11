/**
 * Configuracion de desarrollo.
 *
 * La URL de la API se resuelve en tiempo de ejecucion desde `window.__env`
 * cuando existe, para que la misma imagen de produccion sirva en varios
 * entornos sin reconstruirla.
 */
declare global {
  interface Window {
    __env?: { apiUrl?: string };
  }
}

export const environment = {
  produccion: false,
  apiUrl: window.__env?.apiUrl ?? 'http://localhost:8000/api/v1',
  nombreApp: 'UTE Vice — Gestión Académica',
  version: '0.8.0',
  /** Margen antes de la expiracion para renovar el token de acceso. */
  margenRefrescoSegundos: 60,
};
