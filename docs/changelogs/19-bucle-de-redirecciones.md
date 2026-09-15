# Fase 19 · El bucle de redirecciones que dejaba la pantalla en blanco

**Fecha:** 2026-09-15 · **Estado:** ✅

Tras crear el rol `CONSULTA_DISTRIBUTIVO`, la aplicación quedaba **en blanco**
para quien lo tuviera. Se reportó como «el servidor se cuelga».

## No era el servidor

La pestaña de red lo descartaba: **las 12 peticiones respondían 200 en 385 ms**,
349 kB. En el navegador, Angular arrancaba —`ng-version` presente— y el
componente estaba en el DOM. Lo que no ocurría era la navegación.

## La causa

```
usuario sin dashboard:ver
  → entra, el router lo manda a /tablero        (redirectTo fijo)
  → guardaPermiso(DASHBOARD_VER) lo deniega
  → y redirige a /tablero                        ← el mismo sitio
  → bucle
```

`guardaPermiso` devolvía `createUrlTree(['/tablero'])` al denegar, y `/tablero`
está protegido por esa misma guarda. Con los cuatro roles originales —ADMIN,
COORDINADOR, ANALISTA, CONSULTA— el fallo **no podía aparecer**: todos incluyen
`dashboard:ver`. El rol de consulta del distributivo fue el primero sin él.

> El fallo llevaba ahí desde la fase 06. Lo que cambió en la 18 no fue el
> código de las guardas, sino que por primera vez existiera un usuario capaz de
> recorrer ese camino.

Había **seis sitios** que daban por hecho `/tablero` como destino: la
redirección de la raíz, las dos guardas, el acceso local, el retorno de Google y
el botón del 404.

## La corrección

Una función, `rutaDeInicio(sesion)`, que devuelve **la primera sección que el
usuario puede ver**, en el orden del menú, y `/perfil` —que no tiene guarda de
permiso— si no puede ver ninguna.

La invariante es lo que importa: **nunca devuelve una ruta cuya guarda vaya a
denegar el paso**, porque la elige comprobando permisos. Un destino verificado
no puede rebotar.

La lista de secciones se muda de `layout.component.ts` a `@core/secciones`: de
ella salen ahora tanto el menú como el aterrizaje. Tenerla en un solo sitio es
lo que hace que no puedan divergir.

La redirección de la raíz pasa a ser una función —`redirectTo` la admite y corre
en contexto de inyección—, en lugar de la cadena fija `'tablero'`.

## Pruebas

`core/secciones.spec.ts`, seis casos. El que importa recorre **cada sección con
un solo permiso** y comprueba que el destino resultante es abrible con ese
permiso. Restaurando la conducta anterior falla con el diagnóstico escrito:

```
con distributivo:leer se aterriza en /tablero, que la guarda denegaria
```

## Archivos

| Archivo | Cambio |
|---|---|
| `core/secciones.ts` | nuevo: `SECCIONES`, `RUTA_REFUGIO`, `rutaDeInicio` |
| `core/secciones.spec.ts` | nuevo, 6 casos |
| `core/guardas.ts` | las dos redirecciones, calculadas |
| `app.routes.ts` | `redirectTo` como función |
| `features/acceso/acceso.component.ts` | destino tras entrar |
| `features/acceso/retorno-google.component.ts` | ídem para Google |
| `shared/layout/layout.component.ts` | consume `SECCIONES` |
| `shared/paginas/no-encontrado.component.ts` | el botón ya no asume el tablero |

## Lo que deja como lección

Una guarda que redirige **a una ruta fija** es un bucle esperando a que exista
el usuario adecuado. El destino de un rechazo tiene que calcularse con los
mismos permisos que provocaron el rechazo.
