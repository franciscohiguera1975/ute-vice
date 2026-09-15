# Fase 20 · Nombres en mayúsculas, la sede real y el nivel tecnología

**Fecha:** 2026-09-16 · **Estado:** ✅

Tres correcciones que salieron de mirar las pantallas de catálogos.

## 1. «Monjas» no salía de ningún dato

La sede `MON` se llamaba **«Monjas (Ricardo Hidalgo Ottolenghi)»**. Se revisó el
consolidado y ese nombre no aparece: el origen solo escribe tres formas.

| En el archivo | Veces |
|---|---|
| `MON` | 146 |
| `RICARDO HIDALGO OTTOLENGHI` | 42 |
| `RHO` | 11 |

El código de sede —`MON`— sí sale de los datos. El «Monjas» era una suposición
de quien escribió `NOMBRES_SEDE`: alguien expandió la abreviatura por su cuenta.

Pasa a llamarse **`RICARDO HIDALGO OTTOLENGHI`**, que es como lo nombra el
propio consolidado en sus otras filas.

> `NOMBRES_SEDE` queda reducido a esa única entrada. Las demás sedes se llamaban
> igual que su código y la tabla solo repetía el valor.

## 2. Los nombres van en mayúsculas

La lista de niveles mostraba «Posgrado» junto a «GRADO». Convivían los nombres
escritos a mano con los que generaba el importador en formato título.

`ElementoCatalogo` normaliza ahora el nombre igual que el código: a mayúsculas,
al construirse. No es una convención que haya que recordar en cada sitio que
cree un elemento; **no hay forma de guardar uno en minúsculas**.

### Lo que esto deja obsoleto

`_titulo_legible` —el formateador que convertía `MAESTRÍA EN X` en `Maestría en
X`— deja de tener efecto y se retira. Con él se va la maquinaria de numerales
romanos de la fase 15: con todo en mayúsculas, `CLINICA III` ya se lee bien y el
problema de `Clinica Iii` no puede existir.

`NOMBRES_GENERO` desaparece por lo mismo: solo servía para escribir «Masculino»
en vez de `MASCULINO`.

## 3. Faltaba el nivel tecnología

El catálogo tenía dos niveles, grado y posgrado, porque **el consolidado no
conoce la tecnología**: sus filas de `ETECH` y `UAEFTT` vienen etiquetadas como
grado. La fase 13 ya lo sabía y las mandaba a un período de tecnología, pero la
columna `nivel` de la fila seguía diciendo grado.

El resultado era visible en pantalla: una fila que decía **«GRADO» dentro del
período «2026-1 TECNOLOGÍA»**.

El importador deriva ahora el nivel con `clasificar_periodo`, la misma regla que
decide el período. Así no pueden discrepar: salen de la misma llamada.

**103 filas** pasaron a declarar tecnología —las que ya estaban en un período de
tecnología—. Ninguna fila de grado o posgrado quedó dentro de uno.

## Sobre la reversibilidad

La migración deshace el nivel y el nombre de la sede. **Las mayúsculas no**: no
se guarda cómo estaba escrito cada nombre antes, y reconstruirlo con un formato
título daría un texto distinto del original. Queda dicho en la migración en
lugar de fingir que es reversible.

## Archivos

| Archivo | Cambio |
|---|---|
| `domain/entities/catalogo.py` | el nombre se normaliza a mayúsculas |
| `application/casos_uso/importar_distributivo.py` | `_nivel_de_la_fila`; fuera `_titulo_legible` y `NOMBRES_GENERO`; `NOMBRES_SEDE` reducida |
| `alembic/versions/…d5c8e2f41a37…` | mayúsculas, sede y nivel sobre lo ya cargado |
| `tests/unit/test_distributivo.py` · `test_asignaturas.py` · `test_plantillas_reporte.py` · `test_importar_materias.py` | esperan mayúsculas |

## Queda pendiente

**283 filas siguen sin nivel.** Es anterior a este cambio —eran 290— y no se
tocó: el consolidado las trae con la columna vacía y no hay regla que permita
deducirlo sin inventar.
