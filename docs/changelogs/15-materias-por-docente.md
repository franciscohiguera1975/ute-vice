# Fase 15 · Las materias que imparte cada docente

**Fecha:** 2026-09-14 · **Estado:** ✅

La columna «Asignatura que imparte» existía desde la fase 12, y el reporte ya
sabía unir varias materias en una celda separadas por comas. Lo que faltaba eran
los datos: el catálogo de asignaturas estaba **vacío**.

Esta fase carga el reporte de materias del SICAF —17.088 filas, 16 semestres—
y lo enlaza con el distributivo.

## El problema: dos granos distintos

El reporte de origen agrupa por **docente y semestre**:

```
periodo | codigo_periodo | cedula_docente | nombre_materia
2026-1  | 261651         | 1715439285     | ADMINISTRACIÓN GENERAL
```

El distributivo se organiza por **docente, periodo, carrera y sede**. Falta un
dato para unir las dos cosas sin ambigüedad, y el archivo no lo tiene: el 20 %
de las filas corresponde a docentes con varias carreras en el mismo semestre.

**La regla que se aplica:** las materias de un docente en un semestre se enlazan
a *todas* sus filas de ese semestre. Es lo que pide el informe —«las materias por
periodo de cada docente»— y es honesto con lo que el origen sabe. Repartirlas
entre carreras exigiría adivinar cuál materia pertenece a cuál, y una atribución
inventada es peor que una lista completa.

Cuando el archivo declara el nivel del periodo —`261651` es grado, `261751`
posgrado— se usa para acotar el destino. Resuelve 411 de los 2.954 casos
ambiguos; los que resuelve, los resuelve bien. Si el nivel no acierta ninguna
fila se conservan todas: el origen y el distributivo pueden discrepar en cómo
clasificaron a un docente, y perder la materia por eso sería peor.

## Codocencia: una materia, varias cédulas

El 10 % de las filas trae varias cédulas en la misma celda:

```
1716723612; 1716723612          ← el mismo, repetido (así anota la codocencia)
1712434206; 1718081076          ← dos docentes distintos
```

Se separan y la materia se enlaza a cada uno. Sin esto se perdían 1.728 filas.
El efecto medido: **7.753 → 9.089** filas del distributivo enlazadas.

## Numerales romanos

`_titulo_legible` capitalizaba palabra a palabra, y las asignaturas del SICAF
vienen en mayúsculas con el nivel en romanos:

| Antes | Ahora |
|---|---|
| `Clinica Iii` | `Clinica III` |
| `Adulto Ii-azotemia Aguda` | `Adulto II-Azotemia Aguda` |

Afectaba a 404 asignaturas. Ahora se opera sobre rachas de letras y no sobre
palabras separadas por espacios, porque el origen escribe `II-AZOTEMIA AGUDA`
sin espacio tras el guion.

Se limita a `IVX` a propósito: admitir `LCDM` convertiría siglas como `CD` o
`MD` en numerales.

## Resultado de la carga

| | |
|---|---|
| Filas leídas | 17.088 |
| Asignaturas creadas | 2.591 |
| Filas del distributivo enlazadas | 9.089 |
| Enlaces creados | 22.158 |
| Materias sin destino | 2.185 |

Las sin destino son docentes que dictan y no constan en el distributivo de ese
periodo. Se informan agrupadas por docente y semestre en lugar de descartarse
en silencio: es justamente lo que interesa detectar.

Aparte quedan 37 filas de **educación continua** (`2025`, `2026` a secas), que
no son un semestre y no tienen periodo académico al que pertenecer.

## Un hallazgo: el código de tecnología

El SICAF numera la tecnología con **55**, no con 15:

| Código real | Nombre |
|---|---|
| `261551` | 2026-1 TECNOLOGÍAS |
| `261651` | 2026-1 GRADO |
| `261751` | 2026-1 POSGRADO |

La fase 13 implementó `15`, y producción tiene hoy `261151`.

**Decisión (2026-09-14): se conserva el `15`.** No se alinea con el ERP. Los
trece períodos ya están emitidos con ese código y los informes que salieron del
sistema ya lo llevan; cambiarlo obligaría a reemitirlos para ganar una
coincidencia que nadie consulta. `65` y `75` sí coinciden en ambos sistemas, así
que la divergencia se limita a un dígito de un nivel.

La traducción ocurre en un solo sitio —`_NIVELES`, en `importar_materias`—, que
es por donde entran los códigos ajenos. No es una errata: no lo «corrija».

## Archivos

| Archivo | Cambio |
|---|---|
| `domain/ports/importacion.py` | `FilaCrudaMateria`, `ResultadoImportacionMaterias` |
| `domain/ports/distributivo.py` | `indice_para_materias`, `enlazar_asignaturas` |
| `infrastructure/importadores/materias_excel.py` | nuevo |
| `infrastructure/db/repositorios/distributivo.py` | los dos métodos, por lotes de 5.000 |
| `application/casos_uso/importar_materias.py` | nuevo |
| `application/casos_uso/importar_distributivo.py` | `_Catalogos` → `CacheDeCatalogos`; romanos |
| `cli.py` | comando `importar-materias` |
| `tests/unit/test_importar_materias.py` | nuevo, 32 casos |

## Cómo se ejecuta

```bash
python -m app.cli importar-materias ../data/materias/materias_docentes.xlsx
```

Es idempotente: reemplaza las materias de cada fila que aparezca en el reporte,
de modo que volver a cargar el mismo archivo deja el mismo resultado. Las filas
que el reporte no menciona no se tocan.

> El `IN` de la limpieza va en lotes de 5.000: con quince mil parámetros en una
> sentencia se supera el límite del protocolo de PostgreSQL, que son 65.535.
