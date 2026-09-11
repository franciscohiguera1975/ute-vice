# Fase 02 · Autenticacion y control de acceso

**Fecha:** 2026-09-04 · **Estado:** cerrada

## Objetivo

Tres vias de acceso —credencial local, Google OAuth y directorio activo— con
control de acceso por roles, sin que la logica de sesion se duplique tres veces.

## Entregado

### Tres vias, un solo camino

`IniciarSesion` e `IniciarSesionFederado` terminan ambas en `_EmisorSesion`,
porque las reglas posteriores —cuenta activa, bloqueo por intentos, emision y
rotacion de tokens— son identicas. Lo unico que cambia es como se prueba la
identidad.

Agregar un IdP nuevo hereda esas reglas sin escribirlas otra vez.

### Google OAuth 2.0

Flujo de codigo de autorizacion. El canje ocurre en el backend porque exige el
`client_secret`, que nunca debe llegar al navegador. Se valida `email_verified`
y el dominio institucional.

### LDAP / Active Directory

Autenticacion en dos pasos: una cuenta de servicio busca al usuario y obtiene su
DN; luego se intenta un *bind* con ese DN y la contrasena aportada. Si el bind
tiene exito, la contrasena es correcta. El sistema nunca la almacena ni la
compara: eso ocurre entero dentro del directorio.

`ldap3` es dependencia opcional. Si no esta instalada, el proveedor se reporta
como deshabilitado en lugar de romper el arranque.

### Aprovisionamiento automatico

Un usuario federado que entra por primera vez obtiene cuenta automaticamente,
siempre con el rol minimo (`CONSULTA`). Ya fue validado por un sistema de
confianza institucional; obligarlo a esperar una creacion manual no aporta
seguridad. Lo que si se controla es el rol.

### Tokens

- **Acceso**: JWT de 30 minutos con los permisos dentro, para no ir a la base en
  cada peticion.
- **Refresco**: secreto opaco; en la base solo su HMAC-SHA256. Los JWT no se
  revocan, y para una sesion larga esa capacidad es indispensable.
- **Rotacion con deteccion de reutilizacion**: si llega un token ya canjeado, se
  asume robo y se revocan todas las sesiones del usuario. Es agresivo a
  proposito.

### RBAC

19 permisos, 4 roles. Ver [ADR-0002](../adr/0002-autorizacion-por-permiso.md).

## Hallazgos durante la construccion

- **La mitigacion de temporizacion inicial estaba mal.** Se verificaba contra un
  hash señuelo escrito a mano, que Argon2 rechaza como malformado sin consumir
  tiempo —justo lo contrario del efecto buscado—. Se corrigio ejecutando
  `hashear()` sobre la contrasena recibida, que si consume el coste real.
- **El comando `seed` fallaba con la contrasena de ejemplo.** `Admin.2026.Cambiar`
  contiene «admin», que la politica rechaza como secuencia comun. La politica es
  correcta; se cambio el ejemplo y se movio la validacion al inicio del comando
  para fallar antes de escribir nada.

## Pendiente al cerrar

- Sin segundo factor.
- Sin bitacora de operaciones administrativas. El permiso `auditoria:leer` queda
  reservado para eso.
