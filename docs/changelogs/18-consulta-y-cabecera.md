# Fase 18 · Rol de consulta y cabecera institucional

**Fecha:** 2026-09-15 · **Estado:** ✅

## El rol `CONSULTA_DISTRIBUTIVO`

Acceso de solo lectura a la carga docente, sin abrir el expediente de cada
persona. Tres permisos:

| Permiso | Qué habilita |
|---|---|
| `distributivo:leer` | La sección Distributivo |
| `catalogos:leer` | La sección Catálogos |
| `reportes:generar` | La sección Reportes y las tres descargas: xlsx, csv y pdf |

Y nada más. El menú se gobierna por permiso —cada sección declara los suyos y
`*utePermiso` la oculta—, así que con estos tres se ven exactamente esas tres
opciones. Tablero, Personas, Títulos, Consultas, Asignaturas y Administración
desaparecen.

**No lleva los permisos de escritura.** Sin ellos la interfaz oculta los botones
de alta, edición y borrado, y el backend rechaza la operación aunque alguien
llame al endpoint a mano: la comprobación vive en el caso de uso, no en la
pantalla.

### Por qué no se reutilizó `CONSULTA`

El rol de consulta existente es **más ancho**, no más estrecho: incluye
`personas:leer`, `titulos:leer` y `consultas:leer`, que son justo lo que aquí
no debe verse. Y no incluye `reportes:generar`, que aquí hace falta. No es que
uno contenga al otro; son alcances distintos.

La prueba `test_es_mas_estrecho_que_consulta_en_lo_suyo` fija el conteo en tres:
cada permiso que se agregue abre una pantalla, y conviene que eso cueste editar
una prueba.

## La cabecera

Se adopta la barra institucional del resto de sistemas de la UTE: fondo azul,
marca a la izquierda, navegación horizontal, usuario a la derecha. La columna
lateral desaparece en pantallas anchas y el contenido gana ese ancho.

Detalles que importan:

- **La barra no sigue al tema.** El azul es identidad, no superficie, así que se
  queda igual en claro y oscuro. Por eso los colores de dentro se escriben
  literales: sobre azul, `--texto` sería ilegible en tema claro. El desplegable
  del usuario sí vuelve a superficie normal, donde el tema manda.
- **El logotipo va sin placa.** `log-fondo-blanco.png` ya es la versión en
  blanco sobre el azul institucional, hecha para una barra como esta. Su fondo
  es **opaco**, así que depende de que la barra lleve exactamente ese color: con
  `--azul-800` (`#1f3864`) se veía como un rectángulo más claro recortado.
- **La barra pasa a `--azul-ute` (`#005795`).** No es un color elegido: es el
  fondo del archivo del logotipo, muestreado de él. Igual que `--verde-ute`
  (`#22a94b`), que sale del logotipo circular.
- **El activo se marca con subrayado, no con relleno.** Sobre un fondo de color,
  una pastilla clara compite con el botón de usuario y se lee como si estuviera
  pulsada.
- **El corte responsivo sube a 1100px.** Con nueve secciones, la navegación
  horizontal empieza a empujar el botón de usuario fuera de la barra antes de
  llegar a tableta. Por debajo, el lateral vuelve como cajón.
- **`--rojo-ute`** es un token nuevo para el avatar. No se reutilizó `--error`:
  un avatar en rojo de error se lee como una alerta, y esto es identidad.

## La pantalla de acceso

Dos columnas dentro de una tarjeta: identidad a la izquierda, formulario a la
derecha.

- **El degradado va del azul al verde del propio logotipo**, en esa dirección,
  para que el panel se lea como una ampliación de la marca y no como un fondo
  elegido aparte. Los dos valores salen de muestrear los archivos, no del ojo.
- **Columnas de ancho fijo** —22rem y 24rem— y no fracciones: el formulario no
  debe encogerse cuando el texto de la izquierda crece.
- **Por debajo de 48rem el panel de identidad se oculta entero** en lugar de
  apilarse. No contiene nada que haga falta para entrar, y apilado empujaría el
  formulario fuera de la primera pantalla.
- **No lleva `aria-hidden`.** Dentro está el único `h1` de la página, y
  esconderlo dejaría el documento sin encabezado de primer nivel. Lo decorativo
  es la imagen, y eso lo dice su `alt` vacío.

En la cabecera, en cambio, el logotipo **sí** lleva `alt`: aporta el nombre de
la institución, que el texto contiguo no dice.

Verificado en el navegador a 800×620: tarjeta centrada (99 px arriba, 99 px
esperados), degradado `linear-gradient(150deg, #005795, #22a94b)` y la
proporción del logotipo intacta.

## El favicon

`public/favicon.ico` sustituye al SVG en línea que había en `index.html`. La
carpeta `public` ya era origen de assets, así que el archivo viaja al paquete
sin tocar `angular.json`.

## Archivos

| Archivo | Cambio |
|---|---|
| `domain/enums.py` | `CONSULTA_DISTRIBUTIVO` y sus tres permisos |
| `cli.py` | descripción del rol para la siembra |
| `alembic/versions/…b8d3f1a29e64…` | el rol en las bases que ya existen |
| `shared/layout/layout.component.html` | navegación a la cabecera |
| `shared/layout/layout.component.scss` | barra azul, nav horizontal, cajón |
| `features/acceso/acceso.component.*` | pantalla de acceso a dos columnas |
| `styles.scss` | `--rojo-ute`, `--azul-ute`, `--verde-ute` |
| `index.html` | favicon |
| `tests/unit/test_autorizacion.py` | 4 casos del rol nuevo |

La migración es reversible e idempotente: volver a aplicarla no duplica
permisos, y la vuelta atrás retira el rol y sus vínculos de usuario.
