# ADR-0007 · La politica de ritmo vive en el dominio

**Estado:** vigente · **Fecha:** 2026-09-04

## Contexto

El reparto de consultas en el tiempo —franjas horarias, separacion aleatoria,
presupuesto por hora, retroceso ante fallos— podria implementarse en el
planificador, que es el componente que las ejecuta.

## Decision

Toda decision temporal vive en `domain/services/planificacion.py`. El ejecutor
en segundo plano es un bucle deliberadamente tonto: pregunta que hacer, espera
lo que le dicen, repite.

El dominio recibe el reloj y la fuente de azar por constructor
(`Reloj`, `FuenteAleatoria`).

## Razonamiento

El ritmo **es** una regla de negocio. «No consultar fuera de horario de oficina»
y «no repetir a nadie hasta cubrir a todos» son politicas institucionales, no
detalles de implementacion del planificador.

Y hay una razon practica decisiva: si el dominio llamara a `datetime.now()` y a
`random` directamente, verificar el comportamiento a las 03:00 exigiria esperar
a las 03:00. Con los puertos, una prueba inyecta un reloj congelado y una
semilla fija, y comprueba en milisegundos que a las 22:00 el sistema espera
hasta las 08:00 del dia siguiente.

Las pruebas de `test_planificacion.py` no existirian sin esta decision.

## Consecuencias

- El ejecutor en segundo plano tiene ~150 lineas y ninguna regla.
- La misma politica sirve para el planificador automatico y para el endpoint de
  avance manual: no hay dos comportamientos que mantener sincronizados.
- El endpoint `/consultas/estado-planificador` puede explicarle a un operador
  *por que* el sistema no esta consultando ahora mismo, porque la decision es un
  objeto con un motivo, no un efecto lateral.
- Hay dos puertos (`Reloj`, `FuenteAleatoria`) que en un diseno convencional no
  existirian.
