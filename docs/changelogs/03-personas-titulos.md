# Fase 03 · Personas, titulos e historico

**Fecha:** 2026-09-04 · **Estado:** cerrada

## Objetivo

El nucleo funcional: el padron del personal, su expediente academico y la
bitacora de validacion.

## Entregado

### Personas

CRUD completo con busqueda difusa, filtros compuestos, paginacion y carga
masiva.

La **carga masiva** no aborta por una fila invalida: informa fila a fila para que
el responsable corrija el archivo de origen. Con miles de registros, un «todo o
nada» hace la herramienta inutilizable.

**La cedula no es modificable.** Identifica a la persona ante el registro
nacional; cambiarla invalidaria todo su historico de consultas. Un error de
digitacion se corrige eliminando y volviendo a crear.

**Una persona con expediente no se elimina**, se desactiva. Borrarla destruiria
evidencia de validacion.

### Titulos

Los de origen `SENESCYT` no se editan ni se eliminan: sus datos provienen del
registro nacional, y modificarlos crearia una discrepancia silenciosa que la
siguiente consulta revertiria sin dejar rastro.

Los cargados a mano nacen `POR_VERIFICAR` con origen `MANUAL`. Eso los protege
del reconciliador —que solo retira lo que el mismo trajo— y deja explicito que
su respaldo es documental.

### Identidad por huella

Ver [ADR-0004](../adr/0004-identidad-de-titulos-por-huella.md).

### Reconciliador

Servicio de dominio puro que compara lo que devuelve el proveedor contra lo
almacenado y produce un **plan**: nuevos, actualizados, confirmados, retirados.

Separar el analisis de la escritura permite auditarlo, mostrarlo antes de
aplicarlo y probarlo sin tocar la base. Tiene 29 pruebas.

**Un titulo retirado no se borra.** Es el hallazgo que motiva la auditoria.

## Hallazgos durante la construccion

- **Fallo de borde en la regla de cobertura.** `requiere_consulta()` usaba
  `periodo.contiene()`, cuyo extremo final es exclusivo. Una consulta hecha
  exactamente en ese instante caia fuera de su propio periodo, y la persona
  volvia a la cola. Se cambio a comparar contra el **inicio** del periodo, que
  ademas resuelve el caso de una consulta posterior al cierre.
  Detectado por una prueba con reloj congelado.

## Pendiente al cerrar

- La unidad es texto libre. Se normalizara en la Fase 09, cuando el
  Vicerrectorado confirme el catalogo.
- Sin gestion de documentos de respaldo adjuntos.
