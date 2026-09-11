# Fase 11 · Alcance academico por usuario

**Fecha:** 2026-09-11 · **Estado:** ✅

Los roles dicen **que** puede hacer una cuenta. Faltaba decir **sobre que parte
del distributivo**: quien coordina una facultad tiene el mismo rol que quien
coordina otra, y hasta ahora los dos veian las 15.219 filas del historico.

## La decision que ordena todo lo demas

**Un alcance vacio no restringe nada.**

La alternativa —vacio significa «no ve nada»— parecia mas segura y era peor: al
desplegar la funcion, todas las cuentas existentes se habrian quedado mirando
una pantalla en blanco, y cualquier cuenta nueva a la que se olvidara asignarle
facultades tambien, sin ningun mensaje que lo explicara.

Con la regla elegida, la migracion no necesita poblar nada: al aplicarla, todo
el mundo sigue viendo lo mismo que antes, y acotar es una accion explicita.

El **superusuario** no se acota nunca, aunque se le marquen facultades: es la
cuenta de rescate, y dejarla sin ver algo podria impedir arreglar justamente
eso.

## Facultades y carreras se suman, no se cruzan

Con la facultad `FCID` y la carrera `Medicina`, la cuenta ve **todo FCID** y
**ademas Medicina**, aunque Medicina sea de otra facultad.

Cruzarlas —ver solo las carreras marcadas *dentro* de las facultades marcadas—
obligaria a enumerar todas las carreras de una facultad para conceder lo que
una sola casilla concede.

## Donde se impone

En el **servidor**, a partir de quien pide, **nunca desde la peticion**. Si el
recorte viajara en el cuerpo o en la URL, cualquiera podria ampliarlo pidiendo
mas.

`FiltroDistributivo` lleva un campo `alcance` que el caso de uso rellena con
`contexto.alcance` **sobreescribiendo** lo que trajera la peticion.

Se acota el listado, el resumen, las dos plantillas de exportacion, la captura
de asignaturas y los selectores de facultad y carrera. Los otros diez catalogos
—sede, dedicacion, genero…— no acotan a nadie y van completos.

### Los listados no bastan

Un listado recortado se esquiva pidiendo un registro por su identificador. Por
eso la comprobacion se repite en cada acceso puntual: obtener, actualizar,
eliminar y capturar asignaturas. Actualizar la hace **dos veces** —antes y
despues— porque mover una fila fuera del propio alcance seria perderla de
vista, y traerla desde fuera, apropiarsela.

Fuera de alcance responde `403 fuera_de_alcance`, con un error propio y no
`sin_permiso`: el permiso esta, lo que falta es la facultad. Decirlo asi evita
que alguien crea que le falta un rol cuando lo que le falta es alcance.

## Comprobado contra datos reales

Un coordinador acotado a una facultad, sobre el historico completo:

| | Administrador | Coordinador acotado |
|---|---|---|
| Filas del distributivo | 15.219 | 1.989 |
| Docentes en el resumen | 3.021 | 501 |
| Facultades en el selector | 13 | 1 |
| Sedes en el selector | 4 | 4 |
| Reporte de 2026-1 | 1.523 filas | 214 filas |
| Un registro de otra facultad, por `id` | 200 | **403** |

## Archivos

| Archivo | Que aporta |
|---|---|
| `domain/alcance.py` | `AlcanceAcademico`: el objeto de valor y sus reglas |
| `domain/entities/auth.py` | `Usuario.alcance` y `definir_alcance()` |
| `application/base.py` | `ContextoEjecucion.alcance`, derivado del actor |
| `infrastructure/db/modelos_distributivo.py` | `usuario_facultades` y `usuario_carreras` |
| `infrastructure/db/repositorios/auth.py` | Carga y guardado, en dos consultas por pagina |
| `infrastructure/db/repositorios/distributivo.py` | El recorte en SQL |
| `alembic/versions/…_alcance_academico_por_usuario.py` | Migracion, reversible |
| `features/administracion/usuarios.component.*` | Asignacion desde la interfaz |

El `CatalogosStore` paso de `features/distributivo/` a `core/`: lo usan dos
funcionalidades, y dejarlo donde estaba habria hecho que administracion
importara de otra feature.

## De paso

**`reset-password` en la linea de comandos.** La contrasena del `.env` solo
sirve para el alta inicial; una vez cambiada, ese valor ya no abre nada. Sin
esta salida, recuperar el acceso obligaba a escribir SQL contra la tabla de
usuarios. Genera una clave, la imprime y obliga a cambiarla en el proximo
acceso: una clave que paso por una terminal no deberia seguir siendo valida
manana.

## Pruebas

**19 nuevas** en `tests/unit/test_alcance.py`: el objeto de valor, el usuario,
el contexto y —lo que de verdad importa— que el recorte se imponga sobre lo que
pida la peticion y que llegar por identificador no lo esquive.

Una de ellas encontro un limite del doble en memoria, no del sistema: al
abortar una tanda de asignaturas, el fake comparte el objeto de la entidad y no
simula el `rollback`. La prueba comprueba ahora que no hubo confirmacion, que
es lo que de verdad garantiza que no quedo nada guardado.

## Lo que quedo pendiente

- **`personas` y `titulos` no se acotan.** No tienen facultad ni carrera; su
  campo `unidad` es texto libre. Acotarlos exigiria normalizarlo primero.
- **No hay alcance por sede.** Nadie lo ha pedido; el objeto de valor admitiria
  un tercer conjunto sin cambiar su forma.
