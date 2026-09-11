# ADR-0002 · Autorizacion por permiso, nunca por rol

**Estado:** vigente · **Fecha:** 2026-09-04

## Contexto

El sistema necesita control de acceso por roles. La forma directa es preguntar
`if usuario.rol == "COORDINADOR"` en cada endpoint.

## Decision

El codigo pregunta siempre por **permiso**:

```python
usuario.puede(Permiso.PERSONAS_ESCRIBIR)
```

Nunca por rol. Un rol es solo una agrupacion nombrada de permisos, y existe para
comodidad de quien administra, no para la logica del sistema.

`Usuario.puede()` es el unico predicado de autorizacion. La comprobacion ocurre
en `CasoDeUso.__call__`, antes de ejecutar, de modo que ningun caso de uso puede
olvidarse de autorizar.

## Alternativas descartadas

**Comprobar el rol directamente.** Menos codigo al principio. Se descarto porque
cada rol nuevo obligaria a revisar todos los endpoints buscando donde agregarlo,
y ese tipo de revision se hace mal.

**Reglas basadas en atributos (ABAC).** Mas expresivo —«puede editar personas de
su propia facultad»—. Se descarto por ahora: el Vicerrectorado no ha planteado
esa necesidad, y anticiparla habria complicado el modelo sin un caso concreto.
Si aparece, se agrega como una condicion adicional al predicado existente, sin
cambiar la estructura.

## Consecuencias

- Agregar un rol es insertar una fila y marcar casillas. No se toca codigo.
- El catalogo de permisos se sirve desde el backend, para que el frontend no
  mantenga una copia que se desincronizaria.
- Hay 19 permisos donde 4 roles bastarian hoy. Es deliberado: los permisos son
  el vocabulario estable y los roles son la parte que va a cambiar.
- El rol `ADMIN` no es modificable. Vaciarlo dejaria el sistema sin forma de
  recuperar el control.
