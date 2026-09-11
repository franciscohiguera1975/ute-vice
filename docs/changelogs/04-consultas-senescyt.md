# Fase 04 · Consultas al registro nacional

**Fecha:** 2026-09-04 · **Estado:** cerrada

## Objetivo

El proceso central: recorrer el padron, consultar los titulos de cada persona
por su cedula, y dejar constancia de todo lo que ocurra.

## Entregado

### `EjecutorConsulta`

Unico sitio del sistema donde se llama al proveedor externo y se escribe en el
historico. Tanto la consulta puntual como el job por lotes pasan por aqui, de
modo que ambas producen exactamente el mismo rastro.

**Garantia central:** se escribe una fila en `consulta_logs` pase lo que pase.
Sin ella, un dato desactualizado seria indistinguible de uno que no se pudo
consultar.

### Jobs de cobertura reanudables

`JobCobertura` + `ItemJob`. Cada paso es autonomo y transaccional: si el proceso
muere entre dos pasos, el estado en la base ya refleja todo lo hecho y la
siguiente ejecucion retoma donde quedo. Esa es la propiedad que permite que una
campana dure dias.

`FOR UPDATE SKIP LOCKED` en la reclamacion del siguiente item: varios
trabajadores nunca toman la misma persona.

**Un solo job activo a la vez.** Dos campanas simultaneas romperian la garantia
de no repetir personas dentro del periodo.

### Politica de ritmo

Franjas horarias con pesos, separacion aleatoria, presupuesto por hora,
retroceso exponencial y cortacircuitos. Vive en el dominio, no en el ejecutor.
Ver [ADR-0007](../adr/0007-ritmo-en-el-dominio.md).

Se evalua la **factibilidad** antes de arrancar: si el periodo no alcanza para
cubrir el padron con el ritmo configurado, se advierte. La respuesta correcta es
ampliar el periodo, no acelerar el ritmo, y el mensaje lo dice.

### Tres proveedores intercambiables

`mock`, `manual` (human-in-the-loop) y `oficial` (convenio).
Ver [ADR-0005](../adr/0005-consultas-senescyt.md) y [`SENESCYT.md`](../SENESCYT.md).

### Cola de desafios

Cuando el proveedor exige verificacion humana, la consulta queda en
`DESAFIO_PENDIENTE` y un operador la atiende desde la interfaz. **El sistema no
resuelve el desafio.**

## Hallazgos durante la construccion

- **El reparto de items duplicaba el control de ritmo.** El job distribuia los
  items a lo largo de todo el periodo *ademas* de aplicar la politica de ritmo.
  Con 12 personas y 90 dias, eso significaba una consulta cada dos dias, muy por
  debajo del presupuesto. Dos mecanismos de espera superpuestos no espacian
  mejor: bloquean. Se dejo el reparto como opcion explicita
  (`distribuir_en_periodo`), desactivada por defecto.
  Detectado en la prueba de humo de extremo a extremo.

- **Clasificacion incorrecta del nivel academico.** «ESPECIALISTA EN MEDICINA
  INTERNA» aparecia como *Maestria*: el proveedor lo reporta con la categoria
  generica «CUARTO NIVEL», y el mapeo la aplicaba antes de mirar la
  denominacion. Se corrigio con una regla mas precisa: **la categoria acota el
  resultado y la denominacion lo afina dentro de ella**, de modo que un
  «INGENIERO EN SISTEMAS» reportado como cuarto nivel tampoco se degrada
  contradiciendo al registro oficial.
  Detectado revisando la interfaz con datos reales.

## Pendiente al cerrar

- El analisis del HTML del proveedor `manual` (`_analizar_html`) es un punto de
  extension sin implementar: requiere inspeccionar el portal real.
- El planificador automatico esta implementado pero llega desactivado
  (`SCHEDULER_ENABLED=false`). Debe habilitarse conscientemente.
- Sin notificaciones cuando el cortacircuitos pausa una campana.
