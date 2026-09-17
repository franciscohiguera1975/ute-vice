# Fase 22 · Unificar las categorías duplicadas

**Fecha:** 2026-09-17 · **Estado:** ✅

La carga parcial de 2026-1 creó cuatro categorías que significan lo mismo que
las existentes, porque el sistema académico nuevo las escribe con el prefijo
«TITULAR»:

| Duplicada | Filas | Equivale a | Filas |
|---|---|---|---|
| TITULAR AUXILIAR | 84 | AUXILIAR | 3.586 |
| TITULAR PRINCIPAL | 11 | PRINCIPAL | 317 |
| TITULAR AGREGADO | 9 | AGREGADO | 424 |
| TITULAR AUXILIAR 1 | 1 | AUXILIAR | — |

Las cuatro aparecían **solo en 2026-1**. El consolidado usa las formas cortas de
forma uniforme en los trece semestres, así que un conteo por categoría salía
partido en dos grupos donde hay uno.

Tras unificar: AUXILIAR 3.671, AGREGADO 433, PRINCIPAL 328, y las cuatro
duplicadas retiradas del catálogo.

> **`TÉCNICO DOCENTE` no se toca.** También aparece solo en 2026-1, pero es una
> categoría real: está igualmente en el distributivo oficial.

## La tabla de valores previos se generaliza

La fase 21 creó `distributivo_facultad_previa` para poder deshacer la
integración de una facultad en otra. Esta fase necesita lo mismo para las
categorías, así que la tabla pasa a `distributivo_valor_previo` con una columna
`campo`. Evita una tabla por columna.

Su clave deja de ser la fila y pasa a ser `(fila_id, campo)`: una misma fila
puede tener guardados el valor previo de su facultad y el de su categoría.

## Dos cosas que costaron

**Los nombres de las restricciones.** El proyecto usa una convención
—`pk_%(table_name)s`— definida en `Base.metadata`, así que la clave primaria se
llama `pk_distributivo_facultad_previa` y no `..._pkey`. Suponerlo hizo fallar
el primer intento.

**`AmbiguousParameterError` otra vez.** Reutilizar el mismo parámetro en dos
columnas impide que asyncpg deduzca un tipo único. Ya había pasado en la
migración de los tres periodos y volvió a pasar aquí. Los parámetros van ahora
con `CAST(… AS varchar)` explícito.

## Reversible

Probada en ambos sentidos sobre una copia de producción. La vuelta atrás recrea
las cuatro categorías, devuelve sus 105 filas, restaura el nombre anterior de la
tabla y conserva las 213 filas de facultad de la fase 21.
