/**
 * Entrega de archivos al navegador.
 *
 * Aislar esta operacion en un servicio permite que los componentes que generan
 * reportes no manipulen el DOM directamente, y que una prueba pueda sustituirla
 * por un doble para verificar que se pidio la descarga correcta.
 */

import { Injectable } from '@angular/core';

import type { ArchivoDescarga } from '@domain/modelos';

@Injectable({ providedIn: 'root' })
export class DescargaService {
  guardar(archivo: ArchivoDescarga): void {
    const url = URL.createObjectURL(archivo.contenido);
    const enlace = document.createElement('a');
    enlace.href = url;
    enlace.download = archivo.nombre;
    enlace.style.display = 'none';

    document.body.appendChild(enlace);
    enlace.click();
    document.body.removeChild(enlace);

    // Se libera el objeto tras un instante: revocarlo de inmediato aborta la
    // descarga en algunos navegadores.
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
}
