# ADR-0001 · Arquitectura limpia con puertos y adaptadores

**Estado:** vigente · **Fecha:** 2026-09-04

## Contexto

El sistema empieza con una tabla funcional —titulos de empleados— pero el
encargo anticipa dos etapas mas: tablas adicionales aun sin confirmar, y una
capa de IA con skills, MCP, agentes y reconocimiento de voz.

Nada de eso esta especificado todavia. Lo unico seguro es que las reglas de
negocio —quien puede consultar a quien, cuando toca reconsultar, que cuenta como
un cambio— van a sobrevivir a los cambios de interfaz, de base de datos y de
proveedor externo.

## Decision

Arquitectura limpia con la regla de dependencia estricta: **el dominio no
importa a nadie**. Ni el ORM, ni el framework web, ni la libreria de validacion.
Solo la biblioteca estandar.

Toda dependencia externa entra por un puerto declarado en el dominio. La
infraestructura implementa esos puertos.

Se agrega una prueba que analiza los `import` de cada modulo y falla si la regla
se rompe.

## Alternativas descartadas

**Capas convencionales (controlador → servicio → repositorio) con modelos ORM
como entidades.** Es mas rapido de escribir y perfectamente valido para un CRUD
que no va a crecer. Se descarto porque aqui las reglas mas valiosas —la
reconciliacion de titulos y la politica de ritmo— quedarian atadas a SQLAlchemy
y solo se podrian probar con una base levantada.

**Arquitectura por modulos verticales sin inversion de dependencias.** Buena
para equipos grandes con dominios independientes. Aqui los modulos comparten
demasiado —personas, titulos y consultas son un solo dominio— y la separacion
vertical habria multiplicado el codigo sin reducir el acoplamiento real.

## Consecuencias

**A favor**

- Las 200+ pruebas unitarias corren sin Docker, sin base y sin red.
- Cambiar de proveedor SENESCYT es cambiar una variable de entorno.
- Los casos de uso no dependen de HTTP, lo que habilita la Fase 16 sin
  reescribirlos.

**En contra**

- Hay una capa de mapeadores entre modelos ORM y entidades que no existiria en
  un diseno convencional.
- Agregar un campo exige tocar entidad, modelo, mapeador y esquema de API.
- Para un CRUD trivial, es mas ceremonia de la necesaria.

El costo se paga por adelantado y se cobra cada vez que hay que cambiar algo sin
romper lo demas. Dado el roadmap, se considera una buena inversion.
