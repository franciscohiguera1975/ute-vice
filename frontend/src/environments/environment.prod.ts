declare global {
  interface Window {
    __env?: { apiUrl?: string };
  }
}

export const environment = {
  produccion: true,
  apiUrl: window.__env?.apiUrl ?? '/api/v1',
  nombreApp: 'UTE Vice — Gestión Académica',
  version: '0.8.0',
  margenRefrescoSegundos: 60,
};
