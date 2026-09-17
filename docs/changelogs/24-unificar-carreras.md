# Fase 24 · Unificar carreras que son la misma

**Fecha:** 2026-09-17 · **Estado:** ✅

El catálogo acumuló variantes del mismo programa porque cada origen lo escribía
a su manera y ninguno mandaba sobre el anterior:

| Código | Filas | Período |
|---|---|---|
| INGENIERÍA MECATRÓNICA | 35 | 2020-1 → 2020-2 |
| MECATRÓNICA | 99 | 2020-1 → 2022-2 |
| MECATRÓNICA (R) - PRESENCIAL | 110 | 2023-1 → 2025-2 |
| UIO:MECATRÓNICA - GRADO - PRESENCIAL | 25 | 2026-1 |

Un informe por carrera salía partido en cuatro donde hay una.

## Por qué no basta un `UPDATE`

La clave natural de una fila es docente, período, carrera y sede. Al reasignar,
dos filas del mismo docente que estaban en variantes distintas **del mismo
período** pasan a compartir clave. En mecatrónica ocurre en **19 casos**, todos
de 2020.

Esas filas se fusionan **sumando sus horas**, que es lo que hace la importación
cuando el origen repite una clave: el total es el dato que la institución
reporta.

Las sumas confirman que eran la misma carrera partida en dos nombres, no dos
asignaciones distintas:

```
20,2 + 9,8  = 30 h      16,8 + 15,2 = 32 h
11,2 + 20,8 = 32 h       8,4 + 23,6 = 32 h
```

Cargas redondas, no cifras arbitrarias.

## Las materias sobreviven

Se conserva la fila que **ya estaba en el destino**, si la hay, para que su
identificador —y con él sus asignaturas enlazadas— no cambie. Las de las filas
absorbidas se unen sin repetir.

El conteo de enlaces baja de 22.158 a 22.124, pero **no se pierde ninguno**: los
34 eran duplicados, el mismo docente con la misma asignatura registrada una vez
por cada variante. Las combinaciones distintas de docente, período y asignatura
son **18.446 antes y después**.

## Lo que la herramienta no decide

**Cuáles son la misma carrera.** Esa comparación no se puede automatizar sin
equivocarse: `UIO:ARQUITECTURA - POSGRADO - HÍBRIDA` y `ARQUITECTURA (R) -
PRESENCIAL` comparten el nombre desnudo y son programas distintos. Las variantes
las indica quien ejecuta.

```bash
python -m app.cli unificar-carreras "INGENIERÍA MECATRÓNICA" \
    "MECATRÓNICA" "MECATRÓNICA (R) - PRESENCIAL" "UIO:MECATRÓNICA - GRADO - PRESENCIAL"
```

## El problema es mayor que un caso

Normalizando los nombres —sin prefijo de sede, sin nivel ni modalidad, sin
«(R)»— el catálogo de 278 carreras se reduce a **182 nombres distintos**:

| | |
|---|---|
| Grupos con más de una entrada | 39 |
| Entradas implicadas | 135 |
| Filas implicadas | 6.900 |

Los mayores: medicina veterinaria (4 entradas, 814 filas), derecho (6, 518),
negocios internacionales (5, 515), arquitectura (6, 432), gastronomía (8, 341).

> Esa cifra es una **estimación al alza**: la normalización mezcla grado con
> posgrado. Cada grupo hay que revisarlo antes de unificarlo.

## Resultado

| | Antes | Después |
|---|---|---|
| Carreras de mecatrónica | 4 | **1** |
| Filas | 269 | 268 *(19 fusionadas)* |
| Períodos que cubre | — | 2020-1 → 2026-2 |
| Materias perdidas | — | **0** |
