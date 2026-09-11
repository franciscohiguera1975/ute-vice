# Personas y titulos

## Personas

### Buscar

El buscador acepta nombre, cedula, unidad o codigo de empleado, y **ignora
acentos**: escribir «munoz» encuentra «Muñoz».

Filtros combinables:

- **Vinculacion**: docente, administrativo, directivo, servicios, otro.
- **Titulos registrados**: «sin titulos» aisla a quienes no tienen ninguno, que
  suele ser el punto de partida de una revision.
- **Estado**: activos, inactivos o ambos.
- **Nunca consultadas**: quienes jamas se han verificado contra el registro
  nacional.

Los filtros viajan en la direccion, asi que un listado filtrado se puede
compartir o guardar como marcador.

### Registrar

*Personas → Nueva persona*

La **cedula se valida en el navegador** con el algoritmo del Registro Civil
antes de enviarse. Si el digito verificador no cuadra, se avisa al instante.

Solo cedula, nombres y apellidos son obligatorios.

### Editar

**La cedula no se puede modificar.** Identifica a la persona ante el registro
nacional; cambiarla invalidaria todo su historico de consultas. Si esta mal
digitada, elimine el registro y vuelva a crearlo.

### Desactivar en lugar de eliminar

Una persona inactiva **se excluye de las campanas de consulta** pero conserva su
expediente e historico.

El sistema solo permite eliminar a quien no tenga titulos ni consultas: borrar a
alguien con expediente destruiria evidencia de validacion.

### Carga masiva

Endpoint `POST /api/v1/personas/importar`, permiso `personas:importar`.

Una fila invalida **no aborta la carga**: se informa fila por fila con el motivo
del rechazo, para que el archivo de origen se corrija. Con miles de registros,
un «todo o nada» hace la herramienta inutilizable.

Se informan tres cifras: creadas, duplicadas y rechazadas.

---

## Titulos

### De donde vienen

| Origen | Como llego | ¿Editable? | ¿Eliminable? |
|---|---|---|---|
| **Registro nacional** | Consulta al SENESCYT | No | No |
| **Carga manual** | Un funcionario, con documentacion fisica | Si | Si |
| **Importacion** | Archivo masivo | Si | Si |

Los del registro nacional **no se editan**: sus datos provienen de la fuente
oficial, y modificarlos crearia una discrepancia silenciosa que la siguiente
consulta revertiria sin dejar rastro. Para corregirlos, ejecute una consulta de
actualizacion.

### Estados

| Estado | Significado |
|---|---|
| **Vigente** | Presente en la ultima consulta exitosa |
| **Retirado** | Estaba antes y ya no aparece en el registro nacional |
| **Por verificar** | Cargado a mano, sin contraste contra el registro |

### Sobre los titulos retirados

**Es el hallazgo que motiva la herramienta.**

Un titulo que figuraba en consultas anteriores y desaparecio del registro
nacional puede significar una revocacion, una correccion del registro o un error
del proveedor. En cualquier caso, requiere que una persona lo revise.

Por eso **no se borran**: se marcan, se muestran aparte en el expediente y
aparecen en los reportes. Borrarlos destruiria la evidencia.

### Registrar un titulo a mano

Requiere permiso `titulos:escribir`.

Nace como **por verificar** y de origen manual. Eso lo protege del reconciliador
—que solo retira lo que el mismo trajo— y deja explicito que su respaldo es
documental, no el registro nacional.

### Verificar

Requiere permiso `titulos:verificar`.

Deja constancia de que un funcionario reviso el respaldo documental. Se registra
quien y cuando.

---

## Consultar una persona al registro nacional

Desde el detalle: **Consultar al registro nacional**. Requiere permiso
`consultas:ejecutar`.

### Si aparece «ya fue consultada»

El sistema no repite a nadie dentro del periodo de cobertura vigente. Es la
regla que garantiza que el padron se cubra entero antes de volver sobre alguien.

Se ofrece **forzar**, con su advertencia. Uselo solo con un motivo concreto —por
ejemplo, una correccion reciente en el registro nacional—: cada consulta forzada
consume presupuesto y altera el reparto que calculo el planificador.

### Si requiere verificacion humana

La consulta queda en cola. Un operador con permiso `consultas:resolver` la
atiende desde *Consultas → Historico*. Ver
[consultas-senescyt.md](consultas-senescyt.md).

---

## Interpretar el expediente

En el detalle de una persona:

- **Titulos vigentes** — el expediente actual.
- **Titulos retirados** — en un bloque aparte, con explicacion.
- **Estado de validacion** — cuando se consulto por ultima vez, con que
  resultado, y cuantas veces en total.

Un **origen «Registro nacional»** significa que el dato viene de la fuente
oficial. Un **«Carga manual»** sin verificar significa que alguien lo escribio y
nadie ha contrastado el respaldo todavia.
