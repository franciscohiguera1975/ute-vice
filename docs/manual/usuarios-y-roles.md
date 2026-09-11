# Usuarios, roles y permisos

## El principio

La autorizacion se resuelve **por permiso**, nunca por rol. Un rol es solo una
agrupacion nombrada de permisos, pensada para comodidad de quien administra.

La consecuencia practica: si el Vicerrectorado necesita un rol nuevo —«auditor
externo», «coordinador de facultad»— se crea, se le marcan permisos y **no se
toca codigo**.

---

## Los cuatro roles

| Rol | Para quien | Puede |
|---|---|---|
| **ADMIN** | Responsable tecnico | Todo, incluida la gestion de usuarios y roles |
| **COORDINADOR** | Coordinacion del Vicerrectorado | Gestionar personas y titulos, administrar campanas, emitir reportes |
| **ANALISTA** | Personal operativo | Editar titulos, resolver desafios, emitir reportes |
| **CONSULTA** | Consulta general | Solo lectura de personas, titulos y tablero |

`CONSULTA` es el rol por defecto de quien entra por primera vez con Google o con
el directorio activo. Un administrador lo eleva despues.

### Diferencias que importan

- **COORDINADOR vs ANALISTA**: el coordinador administra campanas (crear,
  pausar, cancelar) y gestiona el padron. El analista opera dentro de lo que ya
  existe.
- **ADMIN vs COORDINADOR**: solo el administrador gestiona cuentas y modifica
  roles.

---

## Los 19 permisos

| Modulo | Permisos |
|---|---|
| Personas | `leer`, `escribir`, `eliminar`, `importar` |
| Titulos | `leer`, `escribir`, `eliminar`, `verificar` |
| Consultas | `leer`, `ejecutar`, `resolver`, `administrar` |
| Reportes | `generar` |
| Tablero | `ver` |
| Usuarios | `leer`, `escribir`, `eliminar` |
| Roles | `administrar` |
| Auditoria | `leer` *(reservado)* |

Dos merecen explicacion:

- **`consultas:resolver`** habilita atender los desafios de verificacion humana.
  Es una tarea operativa frecuente si el proveedor los emite.
- **`consultas:administrar`** habilita crear, pausar y cancelar campanas. Es
  mas sensible que ejecutarlas: una campana mal configurada afecta a todo el
  padron.

---

## Crear un usuario

*Administracion → Usuarios → Nuevo usuario*

Requiere permiso `usuarios:escribir`.

- La contrasena debe cumplir la politica: 10 caracteres o mas, con mayuscula,
  minuscula, digito y especial, sin secuencias comunes.
- La cuenta nace marcada para **cambio obligatorio de contrasena**: hasta que la
  cambie, el usuario no puede usar el sistema. Esa contrasena la conoce quien
  creo la cuenta.

### Cuentas federadas

No se crean a mano. Quien entra por Google o por el directorio activo obtiene
cuenta automaticamente con rol `CONSULTA`. Ya fue validado por un sistema de
confianza institucional.

Si una persona con cuenta local empieza a entrar por Google con el mismo correo,
las cuentas se vinculan en lugar de duplicarse.

---

## Cambiar roles

En el listado de usuarios, marque o desmarque las casillas de rol. El cambio se
aplica de inmediato.

**Un usuario debe conservar al menos un rol.** El sistema rechaza dejarlo sin
ninguno.

---

## Desactivar y eliminar

**Prefiera desactivar.** Los registros de auditoria referencian al usuario que
ejecuto cada accion; eliminarlo rompe esa trazabilidad.

Al desactivar una cuenta se **revocan todas sus sesiones abiertas** de
inmediato: no queda navegando media hora hasta que expire su token.

Protecciones que el sistema impone:

- Nadie puede desactivar ni eliminar su propia cuenta.
- El superusuario no puede desactivarse ni eliminarse.
- No se puede dejar el sistema sin superusuario activo.

---

## Restablecer una contrasena

*Administracion → Usuarios → Contrasena*

Fija una contrasena nueva, levanta cualquier bloqueo, cierra todas las sesiones
del usuario y lo marca para cambio obligatorio.

Solo aplica a cuentas locales: en las federadas, la contrasena la gestiona el
proveedor.

---

## Bloqueo por intentos fallidos

Tras **5 intentos fallidos**, la cuenta se bloquea **15 minutos**. El bloqueo se
levanta solo, o con un restablecimiento de contrasena.

Un acceso correcto reinicia el contador.

---

## Modificar los permisos de un rol

*Administracion → Roles y permisos*

Requiere permiso `roles:administrar`.

La matriz muestra los 19 permisos agrupados por modulo. Marcar o desmarcar
aplica el cambio de inmediato.

**El rol ADMIN no es modificable.** Vaciarlo dejaria el sistema sin forma de
recuperar el control. El backend tambien lo impide.

Los cambios afectan a todos los usuarios con ese rol la proxima vez que el
sistema recargue su perfil, que ocurre en cada peticion.


---

## Alcance academico

Los roles dicen **que** puede hacer una cuenta. El alcance dice **sobre que
parte del distributivo** puede hacerlo.

Quien coordina una facultad tiene el mismo rol `COORDINADOR` que quien coordina
otra; lo que los distingue es la facultad asignada.

### Como funciona

En *Administracion › Usuarios*, la columna **Alcance** abre la asignacion. Se
marcan facultades, carreras, o ambas.

**Facultades y carreras se suman, no se cruzan.** Con la facultad `FCID` y la
carrera `Medicina`, la cuenta ve **todo FCID** y **ademas Medicina**, aunque
Medicina pertenezca a otra facultad. Solo hace falta marcar carreras sueltas
para conceder acceso a programas de facultades que no estan marcadas.

### Sin nada marcado, ve todo

Es lo mas importante de entender, y es deliberado: **un alcance vacio no
restringe nada**.

Si vaciarlo significara «no ve nada», cualquier cuenta a la que se olvidara
asignarle facultades quedaria mirando una pantalla en blanco sin explicacion, y
todas las cuentas que existian antes de esta funcion habrian dejado de
funcionar de golpe.

El boton **«Quitar restriccion»** hace exactamente eso: vacia las dos listas.

El **superusuario** nunca se acota, aunque se le marquen facultades: es la
cuenta de rescate, y dejarla sin ver algo podria impedir arreglar justamente
eso.

### Que acota, en concreto

| Se acota | No se acota |
|---|---|
| El listado del distributivo | Personas y titulos |
| Los contadores del resumen | Las consultas al SENESCYT |
| Los reportes del distributivo, en las dos plantillas | Los catalogos de sede, dedicacion, categoria, genero… |
| Los selectores de facultad y carrera | La administracion de usuarios y roles |
| La captura de asignaturas | |

El recorte lo impone el **servidor** a partir de quien pide, nunca la peticion.
Pedir mas de la cuenta no amplia nada: entrar por el identificador de un
registro de otra facultad devuelve un `403 fuera_de_alcance`, no el registro.

### Ejemplo

Un coordinador acotado a una facultad, sobre el historico completo:

| | Administrador | Coordinador acotado |
|---|---|---|
| Filas del distributivo | 15.219 | 1.989 |
| Facultades en el selector | 13 | 1 |
| Sedes en el selector | 4 | 4 |
| Reporte de 2026-1 | 1.523 filas | 214 filas |

No hace falta que el coordinador filtre por su facultad: ya viene recortado.
