# ADR-0003 · Modelos ORM separados de las entidades de dominio

**Estado:** vigente · **Fecha:** 2026-09-04

## Contexto

SQLAlchemy permite usar los modelos ORM directamente como entidades de negocio.
Es lo mas comun y ahorra una capa entera.

## Decision

`PersonaModel` (SQLAlchemy) y `Persona` (dominio) son clases distintas.
`infrastructure/db/mapeadores.py` traduce entre ambas.

## Alternativas descartadas

**Usar los modelos ORM como entidades.** Habria eliminado ~400 lineas de
mapeadores. Se descarto porque rompe la regla del ADR-0001: el dominio pasaria a
importar SQLAlchemy, y con ello se llevaria consigo el ciclo de vida de la
sesion, la carga diferida y el comportamiento transaccional a lugares donde solo
deberian existir reglas de negocio.

**Dataclasses con `@registry.mapped` (mapeo imperativo).** Un punto intermedio
que conserva una sola clase. Se descarto porque el acoplamiento sigue ahi, solo
menos visible: un atributo de dominio no puede cambiar sin considerar su columna.

## Consecuencias

**A favor**

- El dominio expresa reglas, no filas. `Persona.requiere_consulta(periodo)` no
  tiene nada que ver con como se guarda.
- Un cambio de esquema queda contenido en el mapeador.
- Las entidades se construyen libremente en pruebas, sin sesion ni base.

**En contra**

- Un campo nuevo se toca en cuatro sitios.
- Los mapeadores son codigo repetitivo, de esos que se escriben con desgana.

La forma de detectar que el mapeador se rompio es la prueba de integracion
`test_migraciones.py` y las pruebas de API, que recorren el ciclo completo.
