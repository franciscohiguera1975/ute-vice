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
| **Indicadores** | `/distributivo/tablero` | Avance de la validacion, dos periodos comparados |
| **Cargar PAO** | `/distributivo/importar` | Subir el distributivo que exporta el sistema academico |
| **Asignaturas** | `/distributivo/asignaturas` | Capturar que materia imparte cada docente |
| **Exportar** | `/distributivo/reporte` | Generar el archivo |
| **Catalogos** | `/catalogos` | Mantener las listas que alimentan los selectores |

Permisos: `distributivo:leer` para consultar y para los indicadores,
`distributivo:escribir` para editar y capturar, `distributivo:importar` para
cargar un PAO, `catalogos:leer` y `catalogos:escribir` para los catalogos,
`reportes:generar` para exportar.

> **Los indicadores piden `distributivo:leer` y no `dashboard:ver`.** Es
> deliberado: el rol de consulta del distributivo no tiene el tablero general y
> aun asi debe poder ver el avance de la validacion.

---

## Los periodos academicos

**Un semestre calendario son tres periodos.** La institucion planifica por
separado la oferta tecnologica, la de grado y la de posgrado, y cada una tiene
su propio periodo con su codigo:

```
2 6 1 65 1
│ │ │ │  └─ 1 ordinario · 0 interciclo
│ │ │ └──── nivel: 15 tecnologia · 65 grado · 75 posgrado
│ │ └────── periodo del anio (1 o 2)
└─┴──────── dos ultimos digitos del anio
```

Asi, `2026-1` son `261151` (tecnologia), `261651` (grado) y `261751` (posgrado).

**Con el interciclo son seis.** El periodo corto que corre entre dos ordinarios
lleva la misma cifra de anio y semestre y termina en `0`: `261650` es el
interciclo de grado de `2026-1`. No se deduce del archivo —sus filas dicen el
mismo semestre que el ordinario— y lo indica quien importa.

**A que periodo va cada fila** lo deciden su facultad y su nivel, en este orden:

1. Facultad `ETECH` o `UAEFTT` → **tecnologia**, sin mirar el nivel.
2. Si no, manda la columna `NIVEL` del consolidado.
3. Si esa columna viene vacia, se toma del nombre de la carrera, que trae la
   forma `SEDE:NOMBRE - NIVEL - MODALIDAD`.
4. Sin ninguna de las dos, grado.

> **En el listado y en la exportacion** se pueden marcar varios periodos a la
> vez. Ver «2026-1 entero» es marcar sus tres.

> **La columna `PAO` de la plantilla de origen sigue diciendo `2026-1`**: ese
> archivo no distinguia niveles y la plantilla existe para contrastar contra el.

---

## Los doce catalogos

Los campos que el consolidado traia como texto libre son catalogos con tabla
propia. Editarlos en un solo lugar corrige el dato en todas las filas que lo
referencian.

| Catalogo | Ejemplos |
|---|---|
| Periodos academicos (PAO) | `261651` (2026-1 GRADO), `261751` (2026-1 POSGRADO) |
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

---

## Cargar un PAO desde la interfaz

`/distributivo/importar`, con permiso `distributivo:importar`.

Es el distributivo que exporta el sistema academico, no el consolidado
historico: tiene sus propias cabeceras y trae seis datos que el consolidado no
tenia —estado de validacion, fase, semanas, relacion laboral y las dos marcas de
tutoria—.

Se acepta `.xls` (Excel 97-2003, que es lo que entrega el ERP), `.xlsx` y
`.xlsm`, hasta 25 MB. **Lo que decide el formato es el contenido del archivo, no
su extension**: el origen a veces entrega un `.xlsx` con nombre `.xls`.

### Lo que hay que indicar

| Campo | Por que |
|---|---|
| **Semestre** | El archivo no lo trae. Formato `2026-2`. |
| **Interciclo** | Tampoco lo trae: sus filas dicen el mismo semestre que el ordinario. |
| **Actualizar las filas que ya existan** | Activado por defecto. Es lo que hace falta al recargar un periodo corregido: sin el, la carga rechaza cada fila ya registrada y habria que borrar el periodo entero, perdiendo las materias enlazadas. |

Un archivo cubre un semestre pero **produce hasta tres periodos**: a cual va
cada fila lo decide su facultad, con la misma regla de arriba.

### Lo que informa al terminar

* Filas creadas y actualizadas, y docentes nuevos.
* **Catalogos poblados**: valores que no existian y se crearon al vuelo.
  Conviene revisarlos —una carrera escrita de otra forma entra como carrera
  nueva, y de ahi salen los duplicados del catalogo—.
* **Filas fusionadas**: el archivo traia la misma clave natural dos veces y se
  sumaron las horas.
* **Filas que no se pudieron desglosar**: juntan varias carreras o sedes en una
  celda —`ALIMENTOS, ELECTROMECANICA`— con un total de horas unico que no se
  puede repartir. Quedan fuera en lugar de inventar una atribucion o una carrera
  que no existe. La solucion es pedir al origen la exportacion desglosada: una
  fila por combinacion de carrera y sede.
* **Rechazadas por la validacion**, con el numero de fila del archivo.

Ninguna fila se descarta en silencio.

---

## Los indicadores

`/distributivo/tablero`, con permiso `distributivo:leer`.

Compara **dos periodos**. Por defecto toma el mas reciente con carga y el
anterior *del mismo tipo*: `2026-2 GRADO` se compara con `2026-1 GRADO`, y un
interciclo con otro interciclo. Comparar grado con posgrado no diria nada.
Ambos se pueden cambiar en los selectores.

### El porcentaje se calcula sobre las filas evaluadas

El estado de validacion lo entrega el sistema academico **desde 2026-2**. Las
filas anteriores lo tienen vacio, y eso no significa que estuvieran sin validar:
significa que el dato no existia.

Por eso el denominador son las filas **con estado**, no el total, y un periodo
sin ninguna muestra un guion —«—»— y no un cero. Contar las filas sin estado
como reprobadas pintaria todo el historico en rojo.

`OK` y `OK, excepcion` cuentan las dos como aprobadas: la segunda solo anade que
la carga es valida por una excepcion concedida.

### Que hay en la pantalla

* Cuatro cifras del periodo: filas —con la diferencia frente al anterior—,
  porcentaje aprobado, pendientes y filas sin estado.
* **Aprobacion de los dos periodos**: una fila por periodo, con filas, filas con
  estado, aprobadas, porcentaje, docentes y horas.
* **Desglose por estado**: los cinco estados con su conteo y su peso, en las dos
  columnas de periodo. Se muestran siempre los cinco, incluidos los que valen
  cero: que «Con error» valga cero es justamente lo que se quiere leer.
* **Facultades, los dos periodos**, con la variacion en puntos porcentuales.
* Cuatro graficos: estados, aprobacion por facultad, filas por sede y filas por
  dedicacion.

> **La diferencia de filas entre los dos periodos es lo primero que hay que
> mirar** al recibir un PAO nuevo. Si el periodo entrante trae mucha menos carga
> que el anterior, la exportacion vino incompleta.
