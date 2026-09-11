# Distributivo docente

El distributivo registra la **carga de un docente en una carrera durante un
periodo academico**: sus horas repartidas por tipo de actividad y las condiciones
de su contrato.

Un mismo docente aparece varias veces en un periodo si dicta en varias carreras,
o en varios campus. Cada combinacion es una fila con su propia distribucion de
horas.

---

## Las pantallas

| Pantalla | Ruta | Para que |
|---|---|---|
| **Distributivo** | `/distributivo` | Consultar, filtrar y editar las cargas |
| **Asignaturas** | `/distributivo/asignaturas` | Capturar que materia imparte cada docente |
| **Exportar** | `/distributivo/reporte` | Generar el archivo |
| **Catalogos** | `/catalogos` | Mantener las listas que alimentan los selectores |

Permisos: `distributivo:leer` para consultar, `distributivo:escribir` para
editar y capturar, `catalogos:leer` y `catalogos:escribir` para los catalogos,
`reportes:generar` para exportar.

---

## Los doce catalogos

Los campos que el consolidado traia como texto libre son catalogos con tabla
propia. Editarlos en un solo lugar corrige el dato en todas las filas que lo
referencian.

| Catalogo | Ejemplos |
|---|---|
| Periodos academicos (PAO) | `2026-1`, `2025-2` |
| Facultades | `FCID`, `FCSEE` |
| Carreras | Las 278 del historico |
| Sedes | Quito, Cuenca, Santo Domingo, Monjas |
| Titularidades | Titular, No titular, Tecnico docente |
| Dedicaciones | Tiempo completo, medio tiempo, tiempo parcial |
| Categorias | Auxiliar, agregado, principal, invitado… |
| Niveles | Grado, posgrado |
| Carreras/programas | El programa concreto dentro de la carrera |
| Titulos profesionales | Los 2.763 titulos del padron |
| Tipos de titulo | Tercer nivel, maestria o equivalente, PHD |
| Generos | Masculino, femenino |

Los doce comparten la misma pantalla: cambia el catalogo, no la forma de usarla.

> **Antes de borrar un elemento**, el sistema cuenta cuantas filas lo
> referencian y se niega si hay alguna. Desactivarlo lo saca de los selectores
> sin tocar el historico, que casi siempre es lo que se busca.

---

## «Asignatura que imparte»

Esta columna **no viene del distributivo**. El consolidado reparte horas por
tipo de actividad —docencia, gestion, investigacion, vinculacion— y nunca dice
que materia se dicta. Como el reporte institucional la exige, se captura a mano.

Mientras nadie la complete, **viaja vacia** al archivo. No se rellena con la
carrera ni con nada aproximado: un dato inventado en un reporte institucional es
peor que una celda en blanco.

### Como capturarla

1. Entre a **Asignaturas** y elija el periodo. Puede acotar por facultad,
   carrera o nombre del docente.
2. Deje marcado **«Solo pendientes»**: muestra unicamente las filas que dictan
   clase y no tienen materia registrada.
3. Escriba directamente en la tabla. La fila editada se resalta.
4. El boton **↑** copia la asignatura de la fila de arriba. Un docente suele
   aparecer varias veces seguidas con la misma materia.
5. Pulse **Guardar**. La tanda entera se guarda en una transaccion: o entra
   completa o no entra nada.
6. La lista se renueva con los siguientes pendientes. Se capturan de a 100.

> Solo se cuentan como pendientes las filas **con horas de docencia**. A quien
> tiene toda su carga en gestion o investigacion no le falta ninguna materia.

---

## Exportar

### Elegir el formato

| Plantilla | Cuando usarla |
|---|---|
| **Cuerpo docente por carrera** | Para entregar. Es el formato institucional: doce columnas, las cinco primeras resaltadas en amarillo |
| **Consolidado (formato original)** | Para contrastar. Reproduce las 72 columnas del archivo de origen, en su mismo orden |

Van a existir mas plantillas. Aparecen solas en el selector a medida que se
agregan; esta pantalla no cambia.

### Elegir el alcance

* **Periodo academico** — obligatorio.
* **Facultad** — opcional. Sin ella se incluyen todas.
* **Carreras** — se pueden marcar **varias a la vez**, que es como se emite el
  reporte: una facultad con el conjunto de sus programas. Sin seleccion, entran
  todas las del periodo y la facultad elegidos. El buscador filtra la lista;
  «Todas» y «Ninguna» actuan sobre lo filtrado.

### Previsualizar antes de descargar

**Previsualizar** muestra las primeras filas con las columnas reales de la
plantilla, cuantos registros y docentes saldrian, y **cuantas filas irian sin
asignatura**, con un enlace directo a la pantalla de captura llevando el periodo
y la facultad ya elegidos.

### Los formatos de archivo

Excel, CSV y PDF, con el mismo criterio que el resto de reportes
([reportes.md](reportes.md)).

> El **consolidado en PDF no se genera**: 72 columnas no caben en una pagina.
> El sistema lo dice al intentarlo y sugiere Excel o CSV, que es lo que sirve
> para comparar de todos modos.

La casilla **«Agregar columnas de auditoria»** suma identificacion, carrera y
total de horas al final. Solo aparece en la plantilla institucional; la de
origen ya trae todo.

---

## Comparar contra el archivo de origen

La plantilla **Consolidado (formato original)** existe para eso: sale sin
cabecera institucional ni totales, con los nombres de columna en la fila 1, para
que los dos archivos se puedan abrir y contrastar directamente.

### Lo que va a coincidir

Los datos del docente y del contrato, los repartos de horas por subactividad, el
nivel, el programa y el tipo de titulo.

### Lo que va a diferir, y por que

| Diferencia | Motivo |
|---|---|
| `D`, `G`, `I`, `V`, `TotalHoras` en 2026-1 | El origen las trae **vacias en todo el periodo**. El sistema las recalcula desde el detalle |
| `TotalHoras`, en algun caso, por 0,01 | Redondeo bancario, el mismo que usa el archivo consolidado original |
| `SEDE` | El origen nombraba un mismo campus de varias formas («CAMPUS CUENCA», «CUENCA»). Estan unificadas |
| `TITULO` | Se rearma uniendo los titulos con `" & "`. El origen mezclaba ese separador con comas |
| Algunos nombres | Siete venian duplicados sobre si mismos en el origen |
| Algunos generos | Catorce venian como `NA` y se derivan del periodo en que si constaban |
| `NA`, `an`, `gen`, `N.x`, `N.y` | Residuos del cruce que produjo el archivo. Se reconstruyen para que las columnas calcen por posicion; no son dato nuevo |

Si aparece una diferencia que no esta en esta lista, es un hallazgo: conviene
revisarla.

---

## Importar el consolidado

Desde la linea de comandos del backend:

```bash
python -m app.cli importar-distributivo docs/distributivo/distributivo.xlsx
```

La importacion:

* Crea los elementos de catalogo que no existan.
* Enlaza cada docente con su expediente en `personas` cuando tiene cedula. Los
  docentes con pasaporte quedan sin enlazar, no fuera.
* **Consolida** las filas que repiten la clave natural sumando sus horas, y
  reporta cada consolidacion.
* **Rechaza** e informa las filas que no se pueden construir, con el numero de
  fila del archivo. Ninguna se descarta en silencio.

`vaciar-distributivo` deja la tabla y sus catalogos vacios, para reimportar
desde cero.
