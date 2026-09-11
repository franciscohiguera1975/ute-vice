# Fase 12 · Catalogo de asignaturas, seleccion multiple y personas del padron

**Fecha:** 2026-09-11 · **Estado:** ✅

Cinco cambios pedidos tras revisar la aplicacion ya publicada.

## 1. «Asignatura que imparte» es un catalogo

Era texto libre en cada fila. Escrita a mano sobre cientos de registros, la
misma materia acababa con tres grafias y corregirlas obligaba a tocar fila por
fila. Ahora es el catalogo numero trece, con clave foranea: se corrige una vez
y cambia en todas.

**La captura masiva sigue siendo por texto.** Obligar a elegir de una lista que
empieza vacia no seria capturar nada: la pantalla manda el nombre, el caso de
uso lo resuelve contra el catalogo y lo agrega si no existe. Compara en
mayusculas y con los espacios colapsados, asi que «Calculo I» y
«CALCULO   I» son una sola entrada, no dos. El formulario del distributivo, en
cambio, usa un selector, como los otros catalogos.

La migracion conserva lo ya capturado y la vuelta atras rehace el texto desde
el catalogo. Se probo con variantes sembradas a proposito: cinco filas con tres
grafias distintas quedaron en una sola asignatura.

## 2. `carrera` y `programa` eran el mismo dato

El consolidado traia `CARRERA` y `CARRERA/PROGRAMA` y la importacion creaba un
catalogo para cada una. **Comprobado sobre las 15.219 filas**: cada carrera
apuntaba a exactamente un programa, y los tres programas que apuntaban a varias
carreras lo hacian por erratas del origen —«ARQUITECTURA» frente a
«ARQUITECTURA (R) - PRESENCIAL»—, no por decir cosas distintas. `programa` era
`carrera` capitalizada.

Quedo `carrera`, que ademas es parte de la clave natural de una fila y aquello a
lo que apunta el alcance de los usuarios. El formulario muestra un solo campo,
etiquetado **Carrera / programa**.

La columna `CARRERA/PROGRAMA` sigue saliendo en la plantilla de origen —las 72
tienen que estar— reconstruida desde la carrera, que es lo que siempre fue.

## 3. La relacion entre facultades y carreras

Al marcar facultades, la lista de carreras se acota a las que existen en ellas.
Con 278 carreras, ofrecerlas todas convertia el selector en una busqueda a
ciegas.

**La relacion se deriva de los datos, no de una columna.** Tiene que ser asi:
doce carreras se dictan en dos facultades a la vez —la facultad y la unidad en
linea—, y un `facultad_id` en el catalogo obligaria a elegir una y equivocarse
en la otra. El endpoint responde con las carreras presentes para los periodos,
las facultades y el alcance del usuario, de modo que lo ofrecido coincide
exactamente con lo que despues sale en el archivo.

Verificado: catalogo completo 278 · 2026-1 → 74 · +PFCSEE → 11, el mismo numero
que da la consulta SQL directa.

## 4. Varios periodos y varias facultades

Los tres filtros de la exportacion admiten ahora seleccion multiple. Un reporte
rara vez es de un periodo y una carrera: se emite una facultad con todos sus
programas, o la evolucion de una carrera a lo largo de varios periodos. Antes
habia que generar un archivo por combinacion y pegarlos.

Se exige al menos un periodo: sin el saldria el historico entero, que nadie
quiere por accidente.

Comprobado: 2026-1 → 1.523 filas; 2026-1 y 2025-2 → 2.976; las dos con PFCSEE y
FAU → 547.

## 5. Personas a partir del padron docente

`python -m app.cli personas-desde-docentes` cruza los dos modulos: crea la
persona de cada docente, la enlaza si ya existia y deja el `persona_id` puesto.
Idempotente.

**2.872 personas creadas de 3.021 docentes.** Los 149 restantes tienen
pasaporte: `Persona` exige cedula ecuatoriana porque es con lo que se consulta
al registro nacional, asi que quedan fuera y se informan. No es un fallo; es que
no hay nada que consultar por ellos.

El nombre se parte por convencion —dos apellidos y el resto nombres—, que
acierta en el 90 % del padron con cuatro palabras. La `unidad` sale de la
facultad del docente en su periodo mas reciente, no de una cualquiera del
historico.

## 6. Sesion: dos horas y salida limpia al caducar

`ACCESS_TOKEN_EXPIRE_MINUTES` pasa de 30 a **120**. Media hora obligaba a
renovar constantemente durante una jornada de captura, y cada renovacion es una
ventana para que algo falle; quien limita de verdad cuanto dura una sesion es el
token de refresco.

Y se cerro un hueco: **un 401 sin token de refresco no redirigia a ningun
sitio**. La aplicacion se quedaba a medias, con los datos sin cargar y nada que
explicara por que. Ahora envia al acceso conservando la ruta para volver.

## Un fallo latente encontrado por el camino

**Los arreglos en parametros de consulta viajaban mal.** `aParametros` hacia
`String(valor)`, que convierte `['a','b']` en `"a,b"` — un solo valor que el
backend rechaza como identificador invalido. Nadie lo habia notado porque
ninguna pantalla mandaba todavia un arreglo por `GET`; el filtro de carreras lo
habria estrellado en cuanto se usara. Ahora se manda el parametro repetido,
que es lo que espera FastAPI.

## Pruebas

**393 en verde** (367 unitarias + 26 de integracion), entre ellas:

| Que verifica | Por que importa |
|---|---|
| Dos grafias del mismo nombre son una sola asignatura | Es la razon de ser del catalogo |
| La relacion facultad→carrera sale de los datos y respeta el alcance | Un coordinador no debe ver carreras de otra facultad ni al elegir |
| El reporte exige al menos un periodo | Sin el saldria el historico entero |
| Un identificador inexistente corta el reporte | Devolver menos filas en silencio daria un archivo incompleto |
| La separacion de nombres, con 2, 3, 4 y 5+ palabras | Es heuristica: conviene ver donde acierta y donde no |
| Las personas no se duplican al correrlo dos veces | Se va a correr mas de una vez |

## Lo que quedo pendiente

- **Los 149 docentes con pasaporte no tienen persona.** Si hiciera falta
  registrarlos, `Persona` tendria que admitir el mismo `Identificacion` que
  `Docente`, y el planificador saber que a esos no los puede consultar.
- La separacion de nombres no puede acertar siempre: el origen guarda una sola
  cadena y no marca donde termina el apellido.
