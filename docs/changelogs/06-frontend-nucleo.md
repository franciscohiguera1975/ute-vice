# Fase 06 · Frontend: nucleo y arquitectura

**Fecha:** 2026-09-04 · **Estado:** cerrada

## Objetivo

Un workspace Angular con la misma disciplina arquitectonica del backend, y las
piezas transversales sobre las que se apoyan todas las pantallas.

## Entregado

### Arquitectura por capas

```
domain/   modelos y puertos (clases abstractas = contratos + tokens de inyeccion)
data/     implementaciones HTTP
core/     sesion, interceptores, guardas
shared/   componentes, directivas, pipes, layout
features/ una carpeta por seccion, con carga diferida
```

Los componentes dependen de `RepositorioPersonas`, no de `HttpClient`. Una
prueba de componente inyecta una implementacion en memoria sin simular
peticiones.

`app.config.ts` es la raiz de composicion, equivalente a `contenedor.py`.

### Sesion con signals

`SesionStore` mantiene usuario y tokens. Las plantillas leen `sesion.puede(...)`
directamente, sin `async` ni suscripciones que cancelar.

### Interceptores

- **Autenticacion**: adjunta el token y renueva la sesion cuando expira,
  reintentando la peticion original. Si varias peticiones reciben 401 a la vez,
  solo la primera dispara el refresco; las demas esperan al token nuevo. Sin esa
  coordinacion, N peticiones concurrentes intentarian N refrescos y la rotacion
  las invalidaria entre si.
- **Errores**: normaliza cualquier fallo al contrato `ErrorApi`, para que los
  componentes tengan una sola forma de error que interpretar.

### Guardas

Autenticado, anonimo, por permiso y **contrasena vigente**. Esta ultima obliga a
cambiar una contrasena provisional antes de usar el sistema: una cuenta recien
creada entra con una contrasena que conoce un tercero.

### Conversion de nomenclatura

El backend usa `snake_case` y el frontend `camelCase`. La conversion ocurre en
un unico punto (`data/mapeo.ts`) en lugar de renunciar a una convencion o
escribir un mapeador por entidad.

### Sistema visual

Todo el color pasa por variables CSS, lo que permite el tema oscuro sin duplicar
reglas. Anillo de foco visible y consistente; se respeta
`prefers-reduced-motion`.

## Hallazgos durante la construccion

- **`inject()` dentro de un `catchError` falla con NG0203.** El cuerpo del
  interceptor corre en contexto de inyeccion, pero el callback de error se
  ejecuta despues, de forma asincrona. El fallo se manifestaba justo cuando mas
  falta hacia: al renovar una sesion expirada. Se corrigio resolviendo las
  dependencias al inicio y pasandolas como parametros.
  Detectado en la consola del navegador.

- **`LOCALE_ID` no basta.** Fijar `es-EC` sin llamar a `registerLocaleData()`
  hace que los pipes de formato fallen en ejecucion, y las cifras del tablero no
  se pintaban. Detectado igual: mirando la consola.

Ambos son fallos que ninguna prueba unitaria habria encontrado. Levantar la
aplicacion y abrirla es parte de darla por terminada.

## Pendiente al cerrar

- Sin pruebas de componentes.
- Sin internacionalizacion: los textos estan en las plantillas.
