# ADR-0006 · Preparacion para la capa de IA

**Estado:** vigente · **Fecha:** 2026-09-04

## Contexto

El roadmap contempla una tercera etapa con skills invocables, un servidor MCP,
consultas en lenguaje natural, agentes de tarea y una interfaz de voz.

Nada de eso esta especificado. La tentacion es doble y opuesta: construirlo ya
—sobre requisitos inexistentes— o ignorarlo y arreglarselas despues.

## Decision

No se construye nada de la capa de IA. Se toman tres decisiones de forma que la
hacen posible sin reescribir el nucleo:

**1. Firma unica de los casos de uso**

```python
resultado = await caso(entrada, contexto)
```

Entrada tipada como dataclass, salida tipada, autorizacion resuelta dentro. De
una dataclass se deriva un esquema JSON de forma mecanica: eso es exactamente lo
que necesita la definicion de una herramienta.

**2. Descriptor de metadatos**

Cada caso de uso expone:

```python
{"nombre": "consultas.consultar_persona",
 "descripcion": "Consulta al registro nacional los titulos de una persona",
 "permiso": "consultas:ejecutar",
 "clase": "app.application.casos_uso.consultas.ConsultarPersona"}
```

Nombre, descripcion y permiso son los tres campos de un catalogo de skills.

**3. Los casos de uso no conocen HTTP**

Reciben un `ContextoEjecucion` y lanzan errores de dominio. Un agente los invoca
igual que un endpoint, y traduce los errores a su propio lenguaje.

## Restriccion de diseno para la Fase 18

Cuando se implementen las consultas en lenguaje natural, **el modelo no debe
generar SQL libre**. Solo podra componer skills registradas, que ya llevan sus
filtros de permisos.

El motivo: una consulta en lenguaje natural traducida a SQL sobre una base con
datos personales es una via directa a la fuga de informacion. Un usuario con rol
`CONSULTA` que pregunta «dame todos los correos y telefonos» obtendria
exactamente eso. Restringiendo al catalogo de skills, cada operacion pasa por su
verificacion de permiso.

## Alternativas descartadas

**Construir el registro de skills ahora.** Sin un caso de uso concreto, el
diseno seria una conjetura. Se prefiere que la primera skill real determine la
forma del registro.

**No hacer nada.** Habria llevado a casos de uso acoplados a FastAPI, y la Fase
11 empezaria por reescribirlos.

## Consecuencias

- Hay un `descriptor()` que hoy no usa nadie. Es codigo muerto hasta la Fase 16,
  y es barato.
- La uniformidad de firma obliga a declarar una dataclass de entrada incluso
  para casos de uso que reciben un solo UUID.
- La restriccion sobre SQL libre debe recordarse cuando llegue la Fase 18. Por
  eso esta escrita aqui y no en la cabeza de nadie.
