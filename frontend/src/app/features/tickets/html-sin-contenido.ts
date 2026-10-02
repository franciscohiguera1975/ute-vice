/**
 * `true` si el HTML de un editor enriquecido no tiene texto visible ni imagenes.
 *
 * Un editor "vacio" sigue emitiendo marcado —p. ej. `<p><br></p>`—, asi que
 * `.trim()` sobre el HTML nunca da vacio. Hay que quitar las etiquetas antes;
 * y un contenido que es solo una captura de pantalla, sin texto, cuenta como
 * contenido igual.
 */
export const sinContenido = (html: string): boolean =>
  !html.replace(/<[^>]*>/g, '').trim() && !/<img\b/i.test(html);
