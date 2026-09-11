# ADR-0004 · Identidad de titulos por huella de contenido

**Estado:** vigente · **Fecha:** 2026-09-04

## Contexto

Cada consulta al registro nacional devuelve la lista completa de titulos de una
persona. El sistema debe distinguir tres situaciones:

- es el mismo titulo que ya teniamos,
- es el mismo titulo pero con datos corregidos,
- es un titulo nuevo.

El proveedor no entrega un identificador estable propio, y el texto llega con
acentuacion y espaciado inconsistentes entre consultas.

## Decision

Cada titulo lleva una **huella** derivada de su contenido normalizado:

- Con numero de registro → `sha256("reg:" + registro_normalizado)`
- Sin el → `sha256("txt:" + denominacion + "|" + institucion)`, normalizados

Se normaliza a minusculas, sin acentos y con espacios colapsados.

Restriccion `UNIQUE (persona_id, huella)`.

## Alternativas descartadas

**Comparar por denominacion e institucion literales.** Cada variacion de tilde o
de espaciado habria producido un titulo «nuevo», duplicando registros y llenando
el historico de cambios falsos.

**Confiar solo en el numero de registro.** No todos los titulos lo traen,
especialmente los mas antiguos y los obtenidos en el exterior.

**Comparacion difusa por similitud de texto.** Habria resuelto casos que la
normalizacion no cubre, a cambio de un umbral arbitrario y de fusiones
incorrectas entre titulos parecidos. Se prefirio un criterio determinista y
explicable: si dos titulos se consideran el mismo, se puede decir exactamente
por que.

## Consecuencias

- Un cambio de acentuacion no genera ruido en el historico.
- Con numero de registro, una reformulacion del texto se reporta como
  *modificacion*, no como titulo distinto —que es lo correcto, porque el
  registro es el identificador oficial—.
- Si el proveedor corrige un numero de registro erroneo, la huella cambia y el
  sistema lo vera como un titulo nuevo mas uno retirado. Es un falso positivo
  conocido, y es el comportamiento prudente: obliga a que una persona lo revise
  en lugar de fusionar registros en silencio.
