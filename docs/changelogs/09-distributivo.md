# Fase 09 · Distributivo docente, catalogos y exportacion

**Fecha:** 2026-09-11 · **Estado:** ✅

Punto de partida: `docs/distributivo/distributivo.xlsx`, el consolidado de
distributivo de 2020-1 a 2026-1 —15.287 filas, 72 columnas— construido fuera del
sistema cruzando varias fuentes.

## Lo entregado

### La tabla `distributivo` y sus doce catalogos

Una fila por **carga de un docente en una carrera durante un periodo**. Los doce
campos que el consolidado traia como texto libre pasaron a ser catalogos con
tabla propia y clave foranea: `pao`, `facultad`, `carrera`, `sede`,
`titularidad`, `dedicacion`, `categoria`, `nivel`, `carrera/programa`,
`titulo profesional`, `tipo de titulo` y `genero`.

**Doce tablas y un solo CRUD.** Cada catalogo tiene su tabla —para que la clave
foranea exista de verdad— pero comparten repositorio, casos de uso, router y
componente. El tipo selecciona la tabla a traves de `MODELOS_CATALOGO`; los
valores de `TipoCatalogo` son directamente los segmentos de la URL.

### La clave natural incluye la sede

`(docente, pao, carrera)` parecia suficiente y no lo era: 154 grupos de filas la
repetian. Al revisarlos, en 118 de los 154 la **SEDE difería** —el mismo docente
dictando la misma carrera en dos campus, que son dos cargas distintas—. La clave
quedo en `(docente, pao, carrera, sede)`, y con `UNIQUE NULLS NOT DISTINCT`
porque 19 filas no tienen sede y PostgreSQL, por omision, considera distintos
dos `NULL`: sin eso la restriccion tenia un agujero justo donde falta el dato.

Los 36 grupos que siguieron repitiendose son inconsistencias reales del origen.
La importacion **suma sus horas** y deja constancia de cada consolidacion en el
resultado, en lugar de descartar filas en silencio.

### Los titulos se separan por `&` **y** por coma

El primer intento rompio contra titulos de 488 caracteres. Eran varios titulos
en una celda. Al revisar el separador aparecio que el origen mezcla ` & ` con
` , `: 387 titulos usan la coma y **ninguno** tiene el patron `\w,\w`, asi que
separar por coma-con-espacio no parte ningun titulo legitimo. Resultado: 2.767
titulos distintos, el mas largo de 199 caracteres.

### El grado academico se hereda del ultimo periodo conocido

El consolidado trae `TIPOTITULO = 'NA'` para **todo 2026-1** (1.542 filas). Sin
respaldo, la columna «grado academico mas alto completado» habria salido vacia
para todos. Se agrego una subconsulta que toma el ultimo grado conocido del
docente en cualquier periodo: si en 2025-2 constaba PHD, en 2026-1 sigue siendo
PHD. Resolvio 46 de 50 casos revisados.

### Exportacion con plantillas

Dos formatos, y la estructura para que crezcan:

| Plantilla | Que produce |
|---|---|
| `docencia-carrera` | El formato institucional de `tabla_excel.png`: doce columnas, las cinco primeras en amarillo y el resto en gris |
| `consolidado-origen` | Las 72 columnas del `distributivo.xlsx` de partida, en su mismo orden, para contrastar |

Una plantilla decide **tres cosas**: que columnas salen, de donde se sacan las
filas y como se numeran. El resto —resolver filtros, elegir formato de archivo,
controlar el tamano— es igual para todas y vive en el caso de uso. Agregar un
formato es escribir una clase en `app/application/plantillas/` y registrarla:
ni el caso de uso, ni el router, ni el frontend cambian, porque la interfaz
**pregunta** que plantillas hay y pinta las que reciba.

Se filtra por periodo, por facultad y por **varias carreras a la vez**, que es
como se emite: una facultad con el conjunto de sus programas.

### Fidelidad de la plantilla de origen

Verificada contra el archivo real, no asumida:

* Las **72 cabeceras** coinciden una a una, incluido el orden sin logica de las
  columnas de investigacion (`Ic, Ie, Ig, Ih, Ii, I, V, Ia, Ib, Id, If, Ij`) y
  las cinco columnas residuales del cruce (`NA`, `an`, `gen`, `N.x`, `N.y`), que
  se reconstruyen para que las posiciones calcen.
* El texto de los catalogos sale del **codigo**, que conserva como los nombraba
  el consolidado, y no del nombre, que la importacion capitaliza para que se lea
  en pantalla. Sin esto cada celda de texto figuraba como diferencia por una
  simple cuestion de mayusculas.
* El archivo sale **sin preambulo ni totales**, con la cabecera en la fila 1.
  Con titulo y filtros alrededor, las filas no quedan donde el original las
  tiene y los dos archivos ya no se pueden comparar sin alinearlos a mano.

Contraste de 2025-2 —periodo en que el origen **si** trae las columnas
derivadas— sobre 1.395 filas con clave unica:

| Derivada | Filas que difieren |
|---|---|
| `D`, `G`, `I`, `V` | 0 |
| `TotalHoras` | 2, por 0,01 (redondeo bancario) |

Las diferencias en 2026-1 son todas explicables y quedan documentadas en el
modulo: el origen deja `D`, `G`, `I`, `V` y `TotalHoras` **vacias en todo el
periodo** (1.542 de 1.542 filas) y el sistema las recalcula; 7 nombres venian
duplicados sobre si mismos en el origen; 14 generos venian como `NA` y se
derivan de otro periodo; `SEDE` sale normalizada porque el consolidado nombraba
un mismo campus de varias formas y no hay un texto original al que volver.

### «Asignatura que imparte»: capturada, no inventada

Es la unica columna del reporte institucional que **no existe en ninguna parte
del origen**: el distributivo reparte horas por tipo de actividad, no por
materia. Se decidio dejarla vacia antes que rellenarla con la carrera.

Tiene pantalla propia —`/distributivo/asignaturas`— pensada para lo que es:
escribir a mano cientos de filas. Tabla editable en linea sin abrir un modal por
registro, boton para copiar la asignatura de la fila anterior —un docente suele
aparecer varias veces seguidas con la misma materia—, filtro «solo pendientes» y
guardado por tandas en **una sola transaccion**. La pantalla de exportacion
enlaza aqui con el periodo y la facultad ya elegidos.

Las tres cuentas de «sin asignatura» —las dos plantillas y el filtro de la
pantalla— usan la **misma regla del dominio**: `total_docencia > 0 y sin
asignatura`. A quien tiene toda su carga en gestion o investigacion no le falta
ninguna materia. Antes de unificarlas, la plantilla institucional avisaba de
1.523 pendientes y la pantalla mostraba 1.404.

### La aplicacion se llama «Gestion Academica»

El nombre anterior, «Gestion de Titulos», describia solo el primer modulo.

## Resultado de la importacion

```
15.219 filas creadas · 3.021 docentes · 2.763 titulos profesionales
41 consolidadas · 27 rechazadas
```

Las 27 rechazadas: 19 sin carrera, 6 con carrera `'0'` y 2 con la
identificacion `06452930/5`. Ninguna se descarto en silencio.

| Catalogo | Elementos |
|---|---|
| paos | 13 |
| facultades | 13 |
| carreras | 278 |
| sedes | 4 |
| titularidades | 3 |
| dedicaciones | 3 |
| categorias | 6 |
| niveles | 2 |
| programas | 274 |
| titulos profesionales | 2.763 |
| tipos de titulo | 3 |
| generos | 2 |

## Archivos

### Backend

| Archivo | Que aporta |
|---|---|
| `domain/value_objects_distributivo.py` | `Identificacion` (cedula o pasaporte), `PeriodoAcademico`, `DistribucionHoras` |
| `domain/entities/catalogo.py` | `TipoCatalogo`, `ElementoCatalogo` |
| `domain/entities/distributivo.py` | `Docente`, `FilaDistributivo`, `separar_titulos()` |
| `domain/ports/distributivo.py` | Filtros, DTOs resueltos y los tres puertos de repositorio |
| `domain/ports/importacion.py` | Puerto del lector del consolidado |
| `infrastructure/db/modelos_distributivo.py` | Las doce tablas `cat_*`, `docentes`, `distributivo` |
| `infrastructure/db/repositorios/distributivo.py` | Un repositorio para los doce catalogos; subconsultas derivadas |
| `infrastructure/importadores/distributivo_excel.py` | Lectura en flujo del consolidado |
| `application/plantillas/` | Contrato de plantilla, las dos implementaciones y el registro |
| `application/casos_uso/catalogos.py` | CRUD generico |
| `application/casos_uso/docentes.py` | CRUD, con enlace a `personas` cuando hay cedula |
| `application/casos_uso/distributivo.py` | CRUD, resumen y captura de asignaturas por tandas |
| `application/casos_uso/importar_distributivo.py` | Importacion con consolidacion y rechazos |
| `application/casos_uso/reporte_distributivo.py` | Vista previa y generacion, delegando en la plantilla |
| `api/v1/routers/catalogos.py` | Un router para los doce |
| `api/v1/routers/distributivo.py` | Docentes, distributivo, captura y exportacion |
| `alembic/versions/…_distributivo_docente_y_catalogos.py` | Migracion, reversible |

### Frontend

| Archivo | Que aporta |
|---|---|
| `features/catalogos/` | Un componente para los doce CRUD |
| `features/distributivo/catalogos.store.ts` | Cache en señales de los doce catalogos |
| `features/distributivo/lista.component.*` | Listado, filtros y editor con las 47 subactividades |
| `features/distributivo/asignaturas.component.*` | Captura masiva de la asignatura |
| `features/distributivo/reporte.component.*` | Exportacion: plantilla, periodo, facultad y multiples carreras |
| `data/repositorios-distributivo.ts` | Adaptadores HTTP |

## Dos fallos encontrados al verificar

### El PDF reventaba con la plantilla de origen

Las seis combinaciones de plantilla y formato se probaron una a una. Cinco
funcionaron; **consolidado + PDF devolvia 500**: con 72 columnas, el ancho
repartido cae por debajo del relleno de celda y `reportlab` aborta a mitad del
armado con un ancho negativo.

No era de la plantilla sino del exportador, que no tenia suelo de ancho: le
pasaba a cualquier reporte ancho. Ahora comprueba el reparto antes de armar y
responde 422 con el motivo y la alternativa:

> El reporte tiene 72 columnas y en PDF caben 48. Use Excel o CSV, o elija una
> plantilla con menos columnas.

### Las pruebas de integracion borraban la base de desarrollo

`tests/integration/conftest.py` documentaba `ute_vice_test` pero su valor por
omision era `ute_vice`, y usa `setdefault`: con un entorno de desarrollo
cargado, correr la bateria hacia `drop_all` sobre la base de trabajo. Paso en
esta sesion: se perdieron las 15.219 filas importadas y hubo que reconstruirlas.

Ahora las pruebas **se omiten** si `POSTGRES_DB` no termina en `_test`, salvo
que se defina `PERMITIR_BASE_NO_TEST=1` para un contenedor efimero de CI.

## Pruebas

**331 unitarias** y 26 de integracion. Las unitarias, sin Docker ni red.

| Grupo | Cantidad |
|---|---|
| Dominio del distributivo | 50 |
| Importacion del consolidado | 36 |
| Plantillas de exportacion | 22 |
| Captura de asignaturas | 6 |

La prueba que mas valor tiene es `test_las_columnas_son_las_del_archivo_de_origen`:
compara las 72 claves de la plantilla contra la cabecera literal del archivo. Si
alguien reordena una columna, falla.

## Lo que quedo pendiente

1. **Pruebas de frontend.** El proyecto no tiene ninguna: `tsconfig.spec.json`
   no encuentra archivos. No es de esta fase, pero ya es visible.
2. **Reimportar periodos.** Existe `vaciar-distributivo`, pero no una
   reimportacion incremental que reemplace un periodo sin tocar los demas.
3. **Mas plantillas.** La estructura esta para eso; las dos actuales son el
   punto de partida que se pidio.
4. **`SEDE` en la plantilla de origen.** Sale normalizada porque el consolidado
   usaba varios nombres para un mismo campus. Si hiciera falta el texto literal,
   habria que guardarlo al importar.
