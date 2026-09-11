/**
 * Composicion de la aplicacion.
 *
 * Equivale al contenedor de dependencias del backend: aqui —y solo aqui— se
 * decide que implementacion concreta cumple cada puerto del dominio.
 */

import { registerLocaleData } from '@angular/common';
import { provideHttpClient, withInterceptors } from '@angular/common/http';
import localeEsEc from '@angular/common/locales/es-EC';
import {
  type ApplicationConfig,
  ErrorHandler,
  LOCALE_ID,
  provideAppInitializer,
  provideZoneChangeDetection,
} from '@angular/core';
import { provideRouter, withComponentInputBinding, withInMemoryScrolling } from '@angular/router';

import { PROVEEDORES_DATOS } from '@data/repositorios';
import { PROVEEDORES_DISTRIBUTIVO } from '@data/repositorios-distributivo';

import { rutas } from './app.routes';
import { interceptorAutenticacion, interceptorErrores } from './core/interceptores';
import { ManejadorDeErrores, limpiarCerrojoDeRecarga } from './core/recarga-por-despliegue';

// `LOCALE_ID` por si solo no basta: los pipes de formato necesitan los datos de
// la configuracion regional cargados, o fallan en tiempo de ejecucion. Se
// registra aqui, una sola vez, antes de que arranque la aplicacion.
registerLocaleData(localeEsEc, 'es-EC');

export const configuracionApp: ApplicationConfig = {
  providers: [
    provideZoneChangeDetection({ eventCoalescing: true }),

    provideRouter(
      rutas,
      // Enlaza los parametros de ruta a las entradas del componente: evita
      // inyectar ActivatedRoute solo para leer un identificador.
      withComponentInputBinding(),
      withInMemoryScrolling({
        scrollPositionRestoration: 'enabled',
        anchorScrolling: 'enabled',
      }),
    ),

    // El orden importa: el de autenticacion adjunta el token y puede reintentar
    // tras renovar la sesion; el de errores normaliza lo que salga de ahi.
    provideHttpClient(withInterceptors([interceptorAutenticacion, interceptorErrores])),

    { provide: LOCALE_ID, useValue: 'es-EC' },

    // Recupera la navegacion cuando se publica una version nueva con la
    // aplicacion abierta: sin esto, los enlaces a secciones aun no visitadas
    // dejan de responder y parece que la interfaz se rompio.
    { provide: ErrorHandler, useClass: ManejadorDeErrores },
    provideAppInitializer(() => limpiarCerrojoDeRecarga()),

    ...PROVEEDORES_DATOS,
    ...PROVEEDORES_DISTRIBUTIVO,
  ],
};
