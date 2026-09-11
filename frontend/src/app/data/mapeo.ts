/**
 * Conversion de nomenclatura entre la API y el dominio del frontend.
 *
 * El backend usa `snake_case` —la convencion de Python— y el frontend
 * `camelCase` —la de TypeScript—. En lugar de renunciar a una de las dos, o de
 * escribir un mapeador a mano por cada entidad, se convierte en el unico punto
 * por el que pasan todos los datos: esta capa.
 *
 * Es una decision consciente con un limite claro: funciona porque el contrato
 * de la API es consistente. Si algun dia un campo debe conservar su forma
 * original, se excluye explicitamente aqui y no en cada consumidor.
 */

/** Claves cuyo contenido no debe convertirse: son datos, no estructura. */
const CLAVES_OPACAS = new Set(['detalle', 'campos', 'datos_crudos', 'respuesta_cruda']);

const aCamelCase = (texto: string): string =>
  texto.replace(/_([a-z0-9])/g, (_, letra: string) => letra.toUpperCase());

const aSnakeCase = (texto: string): string =>
  texto.replace(/[A-Z]/g, (letra) => `_${letra.toLowerCase()}`);

const esObjetoPlano = (valor: unknown): valor is Record<string, unknown> =>
  typeof valor === 'object' &&
  valor !== null &&
  !Array.isArray(valor) &&
  !(valor instanceof Date) &&
  !(valor instanceof Blob);

/** Convierte recursivamente las claves de la respuesta de la API a camelCase. */
export function aCamel<T>(valor: unknown): T {
  if (Array.isArray(valor)) {
    return valor.map((item) => aCamel(item)) as T;
  }
  if (!esObjetoPlano(valor)) {
    return valor as T;
  }

  const salida: Record<string, unknown> = {};
  for (const [clave, contenido] of Object.entries(valor)) {
    // El contenido de una clave opaca se copia tal cual: sus claves son datos
    // del negocio (nombres de campo que cambiaron), no estructura del contrato.
    salida[aCamelCase(clave)] = CLAVES_OPACAS.has(clave) ? contenido : aCamel(contenido);
  }
  return salida as T;
}

/** Convierte las claves de un cuerpo de peticion a snake_case. */
export function aSnake<T>(valor: unknown): T {
  if (Array.isArray(valor)) {
    return valor.map((item) => aSnake(item)) as T;
  }
  if (!esObjetoPlano(valor)) {
    return valor as T;
  }

  const salida: Record<string, unknown> = {};
  for (const [clave, contenido] of Object.entries(valor)) {
    // `undefined` significa "sin cambio": se omite para no enviar nulos que el
    // backend interpretaria como una peticion de borrar el campo.
    if (contenido === undefined) continue;
    salida[aSnakeCase(clave)] = aSnake(contenido);
  }
  return salida as T;
}

/**
 * Convierte un filtro u objeto de parametros en query string.
 *
 * Omite los valores vacios: un filtro sin usar no debe aparecer en la URL, ni
 * en los registros del servidor, ni en la constancia de filtros del reporte.
 */
export function aParametros(objeto: object): Record<string, string | string[]> {
  const parametros: Record<string, string | string[]> = {};
  for (const [clave, valor] of Object.entries(objeto)) {
    if (valor === undefined || valor === null || valor === '') continue;

    // Un arreglo se manda como el parametro repetido —`?ids=a&ids=b`—, que es
    // lo que espera el backend. Convertirlo con `String()` produciria un solo
    // valor `"a,b"` y el servidor lo rechazaria como identificador invalido.
    if (Array.isArray(valor)) {
      if (valor.length === 0) continue;
      parametros[aSnakeCase(clave)] = valor.map(String);
      continue;
    }
    parametros[aSnakeCase(clave)] = String(valor);
  }
  return parametros;
}

/**
 * Lee el nombre de archivo de la cabecera `Content-Disposition`.
 *
 * Se prefiere `filename*` (RFC 5987) cuando existe, porque es el que conserva
 * los acentos; `filename` es el respaldo para clientes antiguos.
 */
export function nombreDeContentDisposition(cabecera: string | null, porDefecto: string): string {
  if (!cabecera) return porDefecto;

  const extendido = /filename\*=UTF-8''([^;]+)/i.exec(cabecera);
  if (extendido?.[1]) {
    try {
      return decodeURIComponent(extendido[1]);
    } catch {
      // Cabecera mal formada: se continua con el respaldo.
    }
  }

  const simple = /filename="?([^";]+)"?/i.exec(cabecera);
  return simple?.[1] ?? porDefecto;
}
