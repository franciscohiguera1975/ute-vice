# Fase 14 · La sesion expirada vuelve al acceso

**Fecha:** 2026-09-14 · **Estado:** ✅

Al caducar el token, la aplicacion se quedaba en la pantalla con los datos
vacios y dos avisos superpuestos: «No fue posible cargar la lista de catalogos»
y «No fue posible cargar el catalogo · Signature has expired». Ninguno decia
que la sesion habia terminado ni que habia que volver a entrar.

## La causa

El interceptor de autenticacion ya tenia el codigo para reconocer el 401,
renovar la sesion y, si no era posible, redirigir al acceso. **Nunca se
ejecutaba.**

Los dos interceptores estaban registrados en este orden:

```ts
withInterceptors([interceptorAutenticacion, interceptorErrores])
```

Angular aplica el arreglo al *salir* la peticion, asi que el primero queda por
fuera y es el **ultimo** en ver el error al volver:

```
peticion  →  autenticacion  →  errores  →  red
error     ←  autenticacion  ←  errores  ←  401
                                 └─ aqui el HttpErrorResponse ya se convirtio
                                    en un objeto plano ErrorApi
```

Cuando el error llegaba al interceptor de autenticacion, `instanceof
HttpErrorResponse` era `false`, la comprobacion del 401 no se cumplia y el
error seguia de largo hacia el componente.

No fallaba nada de forma visible: ni una excepcion, ni un aviso en consola.
Solo el sintoma indirecto de pantallas vacias.

> El mismo fallo dejaba muerta **la renovacion automatica de sesion**. El
> refresco del token no se habia ejecutado nunca; cada caducidad obligaba a
> volver a entrar aunque el token de refresco fuera valido.

## Los cambios

**Orden de los interceptores** — `interceptorErrores` pasa a ir primero, para
envolver al de autenticacion. Asi este recibe el `HttpErrorResponse` original y
la normalizacion a `ErrorApi` ocurre despues, ya con la sesion resuelta.

El orden deja de estar en `app.config.ts` y vive en `INTERCEPTORES`, junto a
los interceptores: es parte de su comportamiento, no de la configuracion de la
aplicacion, y asi las pruebas lo cubren.

**Reconocimiento del 401 tolerante a la forma** — `esNoAutenticado()` acepta
tanto el `HttpErrorResponse` como el `ErrorApi` ya normalizado. Depender solo
del orden de registro significaba que invertirlo volveria a romper la sesion en
silencio.

**Un solo aviso** — al caducar el token fallan a la vez todas las peticiones en
vuelo, y cada pantalla anunciaba su propio fallo. `SesionStore.expirar()` es
ahora reentrante: la primera llamada limpia los avisos, muestra «Su sesion
expiro · Vuelva a ingresar para continuar donde estaba» y navega; las demas no
hacen nada. `NotificacionesService.anunciarYSilenciar()` descarta los errores y
avisos de los siguientes 4 segundos —los exitos no, que son informacion util y
no ruido de la misma causa—.

El cerrojo se levanta al **establecer una sesion nueva**, no al terminar de
navegar: los 401 de las demas peticiones llegan despues de la navegacion. Sin
eso, la segunda llamada mandaba al acceso con `retorno=/acceso` y el usuario no
volvia a donde estaba.

**El backend deja de filtrar el texto de PyJWT** — `decodificar_acceso` lanzaba
`TokenInvalido(str(exc))`, y ese `str(exc)` —«Signature has expired»— acababa
literal en la pantalla del usuario. Ahora usa el mensaje por defecto, en
espanol; el motivo tecnico queda en el `raise ... from` para la traza.

## Pruebas

Es el **primer conjunto de pruebas del frontend**. `tsconfig.spec.json` y el
constructor de Karma ya estaban configurados, pero no habia ningun `.spec.ts`
que ejecutar.

`src/app/core/interceptores.spec.ts` cubre siete casos a traves de
`INTERCEPTORES` —la lista real, en su orden real—, de modo que un orden mal
puesto hace fallar las pruebas:

| Caso | Que verifica |
|---|---|
| adjunta el token | `Authorization: Bearer …` en rutas protegidas |
| no adjunta en login | las rutas publicas van sin token |
| normaliza el error | el contrato `ErrorApi` llega al componente |
| 401 sin refresco | limpia la sesion y navega a `/acceso` |
| 401 con refresco | renueva y reintenta con el token nuevo |
| refresco fallido | una sola navegacion al acceso |
| varias a la vez | un unico aviso, no uno por pantalla |

Se comprobo que detectan el fallo: restaurando el orden anterior, **cuatro de
las siete fallan**.

El trabajo de frontend entra ademas en CI: el paso «Pruebas» corre antes de
compilar.

## Archivos

| Archivo | Cambio |
|---|---|
| `frontend/src/app/core/interceptores.ts` | `INTERCEPTORES`, `esNoAutenticado()` |
| `frontend/src/app/core/interceptores.spec.ts` | nuevo |
| `frontend/src/app/core/sesion.store.ts` | `expirar()` reentrante y con aviso |
| `frontend/src/app/core/notificaciones.service.ts` | `anunciarYSilenciar()` |
| `frontend/src/app/app.config.ts` | consume `INTERCEPTORES` |
| `backend/src/app/infrastructure/seguridad/tokens.py` | no propaga el texto de PyJWT |
| `.github/workflows/ci.yml` | paso de pruebas del frontend |
