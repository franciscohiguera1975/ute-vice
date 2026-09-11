import { bootstrapApplication } from '@angular/platform-browser';

import { AppComponent } from './app/app.component';
import { configuracionApp } from './app/app.config';

bootstrapApplication(AppComponent, configuracionApp).catch((error: unknown) => {
  // Un fallo aqui deja la pagina en blanco: se registra para poder
  // diagnosticarlo desde la consola del navegador.
  console.error('No fue posible iniciar la aplicacion', error);
});
