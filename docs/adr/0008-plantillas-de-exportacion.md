# ADR-0008 · La exportacion se decide por plantillas registradas

**Estado:** vigente · **Fecha:** 2026-09-11

## Contexto

El distributivo tiene que salir en dos formatos muy distintos:

1. **El institucional** — doce columnas, colores concretos en la cabecera, dos
   datos derivados que no estan en la tabla y uno que se captura a mano.
2. **El de origen** — las 72 columnas del `distributivo.xlsx` de partida, en su
   mismo orden, para poder contrastar lo almacenado contra el archivo.

No comparten columnas, ni origen de datos, ni forma: el primero consulta una
proyeccion con subconsultas derivadas; el segundo, las filas resueltas. Y se
sabe desde ya que van a hacer falta mas.

La salida facil era un `if formato == ...` en el caso de uso, o un caso de uso
por formato.

## Decision

Una **plantilla** es un objeto que decide tres cosas y solo tres:

- que columnas salen,
- de donde se sacan las filas,
- como se numeran y se totalizan.

Vive en `app/application/plantillas/`, implementa `PlantillaDistributivo` y se
registra en `registro.py`. El caso de uso `GenerarReporteDistributivo` no sabe
que columnas existen: resuelve los filtros, pide el contenido a la plantilla
elegida y se lo entrega al exportador del formato de archivo.

**La interfaz pregunta que plantillas hay.** `GET /reportes/distributivo/plantillas`
devuelve la lista, y la vista previa devuelve **las columnas junto con los
datos**. El frontend no tiene ninguna columna escrita.

## Razonamiento

Agregar un formato es escribir una clase y sumarla a una tupla. No se toca el
caso de uso, ni el esquema, ni el router, ni el componente Angular, ni se
escribe una sola linea de TypeScript. Es el principio abierto/cerrado aplicado
donde de verdad se iba a necesitar, no por simetria.

Que las columnas viajen con la respuesta es lo que cierra el circulo: sin eso,
cada plantilla nueva obligaria a desplegar el frontend.

## Consecuencias

### Buenas

- El frontend quedo mas simple que antes: pinta lo que recibe.
- Las diferencias de comportamiento entre formatos —si admite columnas de
  auditoria, si lleva preambulo— son atributos declarados en la plantilla, no
  condicionales repartidos.
- Cada plantilla se prueba aislada, sin base de datos.

### Incomodas

- **Las filas de la vista previa viajan como listas de valores, no como
  objetos.** Las claves del consolidado —`APELLIDOS.Y.NOMBRES`, `N.x`— no
  sobreviven la conversion a camelCase que hace el cliente con los nombres de
  campo. Es menos legible en el inspector de red, y fue la unica forma de que
  las dos plantillas usaran el mismo contrato.
- **`TablaReporte` gano una bandera `solo_datos`** para que la plantilla de
  origen salga sin preambulo ni totales. Es una concesion del puerto de reportes
  a un caso concreto; sin ella la cabecera no cae en la fila 1 y los dos
  archivos no se pueden comparar sin alinearlos a mano.
- Una plantilla puede pedir datos que el repositorio no expone todavia. Pasa:
  la de origen obligo a agregar `filas_resueltas()` y a que la fila resuelta
  cargara genero, titulos y los codigos de catalogo.

## Alternativas descartadas

| Alternativa | Por que no |
|---|---|
| Un caso de uso por formato | Duplica la resolucion de filtros, el control de tamano y el manejo de errores en cada uno |
| Configuracion en base de datos | Las dos plantillas actuales necesitan **codigo** —subconsultas derivadas, recalculo de subtotales—, no una lista de columnas |
| Columnas fijas en el frontend | Cada formato nuevo obligaria a desplegar el frontend, que es justo lo que se queria evitar |
