# Reportes

## Los tres reportes

| Reporte | Contenido | Para que sirve |
|---|---|---|
| **Padron de personas** | Personal con su estado de validacion | Ver quien esta cubierto y quien no |
| **Inventario de titulos** | Titulos con su titular | Composicion academica de la planta |
| **Historico de consultas** | Bitacora del proceso | Auditar como se llego a los datos |

Requieren el permiso `reportes:generar` (roles `ANALISTA`, `COORDINADOR`,
`ADMIN`).

---

## Los tres formatos

### Excel (.xlsx)

**El recomendado para trabajar.** Los numeros y las fechas van con su tipo
nativo, no como texto: se pueden ordenar, filtrar y sumar. Incluye cabecera
institucional, panel inmovilizado y autofiltro.

### CSV

Para cargar en otro sistema. Usa separador `;` y UTF-8 con BOM, que es lo que
Excel espera en configuracion regional en espanol —con coma como separador el
archivo se abriria en una sola columna, y sin BOM las tildes se corrompen—.

### PDF

Para imprimir o adjuntar a un oficio. Apaisado, con numeracion de pagina.

**Se limita a 5.000 filas.** Si el reporte es mas grande, se genera con las
primeras 5.000 y se advierte dentro del propio documento. Un PDF con decenas de
miles de filas no le sirve a nadie.

---

## La constancia de filtros

Todo reporte imprime en su cabecera **los filtros aplicados, quien lo genero y
cuando**.

No es decoracion. Un reporte que dice «45 personas sin titulo» no significa nada
si quien lo recibe no puede saber si son todas o solo las de una unidad. Sin esa
constancia, la cifra no es auditable.

---

## Reporte del padron

Filtros: unidad, vinculacion, con o sin titulos, solo activos.

**Desglosar por titulo** cambia la forma del reporte: en lugar de una fila por
persona con el conteo de sus titulos, produce una fila por titulo con los datos
del titular repetidos.

Las personas sin titulos **aparecen igual**, con la nota «(sin titulos
registrados)». Su ausencia es justamente el dato que el reporte debe evidenciar.

### Casos de uso frecuentes

**Quienes no tienen ningun titulo registrado**
Titulos registrados → «Solo sin titulos». Es el punto de partida de una revision
con Talento Humano.

**Composicion academica de una facultad**
Unidad → nombre de la facultad, y activar «Desglosar por titulo».

---

## Reporte de titulos

Filtros: nivel academico, estado, institucion.

### Casos de uso frecuentes

**Titulos retirados del registro nacional**
Estado → «Retirado». Son los que requieren revision: figuraban antes y ya no.

**Titulos cargados a mano sin verificar**
Estado → «Por verificar». Trabajo pendiente de contrastar.

**Personal con posgrado**
Nivel → «Maestria» o «Doctorado». Util para reportes de acreditacion.

---

## Reporte de consultas

Es el reporte de **auditoria del proceso**. Responde: ¿que se intento, cuando,
con que resultado?

Filtros: rango de fechas, solo errores, solo las que detectaron cambios.

### Casos de uso frecuentes

**Justificar un dato desfasado**
Rango de fechas + «Solo errores». Muestra que se intento consultar y por que no
se pudo.

**Cambios detectados en un periodo**
«Solo las que detectaron cambios». Es el insumo para informar a Talento Humano
de altas, correcciones y bajas.

---

## Limites

El servidor rechaza reportes que superan el maximo configurado
(`REPORTS_MAX_ROWS`, por defecto 100.000 filas). Aparece el aviso «El reporte es
demasiado grande».

La salida es **acotar con filtros**, no reintentar. Un reporte que agota la
memoria del servidor es peor que uno que se niega a generarse.

---

## Datos personales

Estos archivos contienen informacion personal de empleados identificables:
cedula, nombre, correo, telefono y expediente academico.

Su distribucion debe tratarse con el cuidado que corresponde. El reporte lleva
constancia de quien lo genero, lo que ayuda si hay que rastrear una filtracion.

Ver [`../SECURITY.md`](../SECURITY.md).
