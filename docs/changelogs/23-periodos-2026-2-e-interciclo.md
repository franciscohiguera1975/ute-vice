# Fase 23 · 2026-2, el interciclo y los campos del sistema académico

**Fecha:** 2026-09-17 · **Estado:** ✅

Entran dos distributivos exportados por el sistema académico —`PAO_2026_2.xls` y
`PAO_2026_1_interciclo.xls`— que traen seis datos que el consolidado no tenía y
obligan a modelar un tipo de período que no existía.

## Un formato distinto, no una variante

El ERP entrega 74 o 75 columnas con cabeceras propias. La diferencia que importa:
**la sede, el nivel y la modalidad vienen en columnas separadas**, mientras el
consolidado los lleva dentro del nombre de la carrera.

```
ERP          Sede=SEDE QUITO  Nivel=GRADO  Modalidad=PRESENCIAL  Carrera=ARQUITECTURA
consolidado  UIO:ARQUITECTURA - GRADO - PRESENCIAL
```

`LectorPaoExcel` recompone esa cadena. No es cosmético: sin ello la misma
carrera entraría dos veces al catálogo con dos nombres. Se midió contra las 278
carreras existentes:

| Estrategia | Coinciden | Crean carrera |
|---|---|---|
| **Recompuesta** | **471** | 532 |
| Solo el nombre | 357 | 646 |
| Nombre + modalidad | 45 | 958 |

Las 13 que aún se crean son **más precisas** que su equivalente: el ERP
distingue la sede —`UIO:MEDICINA`, `MON:MEDICINA`— donde el consolidado
agrupaba todo en `MEDICINA (R) - PRESENCIAL`. Eso alinea medicina, odontología y
psicología con cómo se nombran las otras 265.

## El interciclo es un período, no una etiqueta

Corre entre dos ordinarios, con su propia planificación y su propia carga: un
docente puede aparecer en ambos con carreras y horas distintas. El código lo
distingue en el **último dígito**, como hace el SICAF —`242650` es «2024-2 GRADO
INTERCICLO»—:

```
2 6 1 65 0
│ │ │ │  └─ 1 ordinario · 0 interciclo
│ │ │ └──── nivel
│ │ └────── periodo del anio
└─┴──────── anio
```

No se deduce del archivo: sus filas dicen el mismo semestre que el ordinario, y
la duración no siempre lo separa —51 de las 378 filas del interciclo declaran 16
semanas, no 4—. Lo indica quien importa, con `--interciclo`.

## Los campos nuevos

| Campo | Qué aporta |
|---|---|
| **`estado_validacion`** | Si la carga pasó los controles, y con qué salvedad |
| `fase` | Etapa del ciclo de planificación |
| `semanas` | 16 en el ordinario, 4 en el interciclo |
| `relacion_laboral` | Dependencia laboral o servicios profesionales |
| `tutor_posgrado` · `tutor_medicina` | Tutoría de tesis, que se contabiliza aparte |

**Quedan nulos en todo lo anterior a 2026-2.** Es deliberado: el dato no
existía, que no es lo mismo que estar sin validar. Un valor por defecto
afirmaría algo falso sobre trece semestres.

`estado_validacion` lleva índice parcial —solo donde no es nulo—, porque
consultar qué falta por validar es su razón de ser.

## La categoría se traduce

El ERP antepone «TITULAR» a las tres categorías del escalafón. Sin traducirlo, el
primer ensayo recreó las cuatro duplicadas que la fase 22 acababa de unificar.

```
TITULAR AUXILIAR  → AUXILIAR       TITULAR AGREGADO  → AGREGADO
TITULAR PRINCIPAL → PRINCIPAL      TITULAR AUXILIAR 1 → AUXILIAR
```

Va en el lector y no en una migración: así el problema no vuelve con el próximo
archivo. Titularidad y dedicación sí coinciden y pasan intactas.

## Lo que queda fuera

**228 filas** juntan varias carreras o sedes en una celda:

```
Carrera/Programa = ALIMENTOS, ELECTROMECÁNICA, INGENIERÍA INDUSTRIAL
Sede             = SEDE QUITO, SEDE SANTO DOMINGO
```

La clave natural exige una carrera y una sede, y las horas vienen como un total
único que no se puede repartir. El lector las rechaza y las lista, en lugar de
inventar una atribución o una carrera inexistente.

**65 filas más** las rechaza el importador: 63 sin carrera (`N/A`) y 2 sin
identificación.

## Resultado

| | |
|---|---|
| Períodos nuevos | **6** |
| Filas de 2026-2 | 963 |
| Filas del interciclo | 311 |
| Carreras nuevas | 13 |
| Categorías nuevas | **0** |
| Materias enlazadas | 22.158, intactas |

| Código | Nombre | Filas | Semanas |
|---|---|---|---|
| 261150 | 2026-1 TECNOLOGÍA INTERCICLO | 12 | 4 |
| 261650 | 2026-1 GRADO INTERCICLO | 281 | 4 |
| 261750 | 2026-1 POSGRADO INTERCICLO | 18 | 4 |
| 262151 | 2026-2 TECNOLOGÍA | 21 | 16 |
| 262651 | 2026-2 GRADO | 773 | 16 |
| 262751 | 2026-2 POSGRADO | 169 | 16 |

Estados de validación cargados: 619 OK, 372 pendientes, 244 con excepción, 39 en
error.
