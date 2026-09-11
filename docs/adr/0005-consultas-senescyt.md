# ADR-0005 · Consultas al SENESCYT sin evasion de controles

**Estado:** vigente · **Fecha:** 2026-09-04

## Contexto

El portal publico de consulta de titulos esta protegido por captcha.

El encargo pedia explicitamente automatizar su resolucion, distribuir las
peticiones para «no activar alarmas de abuso» y documentar una estrategia de
proxies o VPN.

La necesidad de fondo es legitima: el Vicerrectorado debe verificar los titulos
de su propio personal.

## Decision

Se implementa el reparto de carga en el tiempo y el control de cobertura. **No**
se implementa la resolucion automatica del captcha, la rotacion de proxies ni
ninguna tecnica orientada a no ser detectado como automatizacion.

En su lugar:

1. **Cola *human-in-the-loop*.** Cuando el proveedor exige verificacion, la
   consulta queda en `DESAFIO_PENDIENTE` y un operador con permiso
   `consultas:resolver` la atiende desde la interfaz.
2. **Identificacion honesta.** El adaptador se presenta con `User-Agent` y
   `From` institucionales.
3. **Respeto a los rechazos.** Un `403` o `429` incrementa el contador de fallos
   y, al quinto, pausa la campana entera.
4. **Puerto conectable.** `ProveedorConsultaTitulos` tiene tres
   implementaciones. Si la UTE consigue el convenio, se activa `oficial` sin
   tocar dominio ni casos de uso.

## Razonamiento

Un captcha es un control de acceso cuyo proposito explicito es distinguir a una
persona de un programa. Automatizar su resolucion es evadirlo. Rotar
direcciones de salida para no ser reconocido tiene, por definicion, el objetivo
de impedir que el proveedor ejerza una decision que le corresponde.

Que el fin sea legitimo no cambia la naturaleza del medio.

Hay ademas una razon practica: un sistema construido sobre la evasion es fragil.
Se rompe cada vez que el proveedor ajusta sus defensas, y su funcionamiento
depende de que nadie del otro lado se de cuenta. La via del convenio produce un
sistema que funciona porque tiene permiso.

## Consecuencias

**A favor**

- El sistema es defendible ante una auditoria y ante el propio proveedor.
- El puerto conectable hace que el trabajo hecho no se pierda cuando llegue el
  convenio: cambia una variable de entorno.
- El reparto en el tiempo *reduce* la carga sobre el proveedor, que era el
  objetivo razonable detras del pedido original.

**En contra**

- Con el proveedor `manual`, un funcionario debe transcribir codigos. Para un
  padron grande, eso es trabajo real y sostenido.
- La cobertura completa del padron tarda mas de lo que tardaria un proceso sin
  restricciones.

**Recomendacion:** gestionar el convenio institucional. Elimina el captcha,
elimina la incertidumbre juridica y libera a esa persona.

Detalle completo en [`../SENESCYT.md`](../SENESCYT.md).
