# Operar las consultas al registro nacional

> Antes de operar este modulo, lea [`../SENESCYT.md`](../SENESCYT.md). Explica
> que hace el sistema, que deliberadamente **no** hace, y por que.

## Resumen del proceso

1. Se crea una **campana** que encola a todo el personal pendiente de consultar.
2. El sistema recorre la cola con un ritmo controlado, respetando franjas
   horarias y un presupuesto por hora.
3. Cada consulta deja una fila en el **historico**, exitosa o no.
4. Si el proveedor exige verificacion humana, la consulta queda en cola y un
   operador la resuelve.
5. La campana termina cuando todo el padron esta cubierto.

---

## Elegir el proveedor

`SENESCYT_PROVIDER` en `.env`:

### `mock` — desarrollo

Datos ficticios deterministas. Util para probar todo el flujo sin depender de
nada externo. **La aplicacion advierte al arrancar si detecta este proveedor en
produccion.**

### `manual` — operacion con verificacion humana

Requiere configurar `ConfiguracionPortal` en
`backend/src/app/infrastructure/senescyt/manual.py`:

```python
ConfiguracionPortal(
    url_formulario="…",              # pagina que entrega el desafio
    url_consulta="…",                # endpoint que recibe la cedula
    campo_cedula="…",                # nombre del input
    campo_respuesta_desafio="…",
    campo_token_formulario="…",      # token oculto, si lo hay
    ruta_imagen_desafio="…",         # imagen del desafio
    contacto_institucional="vicerrectorado@ute.edu.ec",
)
```

**Estos valores deben verificarse contra el portal real.** No vienen fijados en
el codigo porque cambian cuando el portal cambia, y codificarlos a ciegas
produciria un adaptador que falla en silencio.

Falta ademas implementar `_analizar_html()`, que convierte la pagina de
resultados en titulos. Devuelve `None` mientras no se implemente —y `None`, no
una lista vacia, porque «no se pudo leer» y «no tiene titulos» son cosas
distintas: la segunda marcaria a la persona como consultada y la sacaria de la
cola—.

Sin configurar, las consultas fallan con un mensaje explicito y la campana no
arranca. Es intencional: es preferible un error visible a datos silenciosamente
vacios.

### `oficial` — API bajo convenio

La via recomendada.

```bash
SENESCYT_PROVIDER=oficial
SENESCYT_OFICIAL_API_URL=https://…
SENESCYT_OFICIAL_API_KEY=…
```

No emite desafios. Elimina la transcripcion manual.

---

## Crear una campana

*Consultas → Campanas → Nueva campana*

| Campo | Que hace |
|---|---|
| **Nombre** | Identifica la campana en el historico |
| **Periodo (dias)** | Ventana durante la cual nadie se reconsulta. Por defecto, `SCHEDULER_PERIOD_DAYS` |
| **Limitar a N personas** | Acota la campana. Util para una prueba antes del padron completo |
| **Iniciar inmediatamente** | Deja la campana en curso al crearla |
| **Repartir a lo largo del periodo** | Ver abajo |

Al crearla, el sistema informa la **capacidad estimada** y advierte si el
periodo no alcanza para cubrir el padron.

> Si aparece esa advertencia, **amplie el periodo**. Subir el presupuesto por
> hora traslada el problema al proveedor.

### Sobre «repartir a lo largo del periodo»

Desactivado por defecto. El ritmo ya lo impone la politica de planificacion
—jitter, presupuesto horario y franja—; anadir una segunda espera solo consigue
que una campana pequena tarde dias sin ninguna ganancia.

Actívelo solo si prefiere que la frescura del dato se distribuya de forma
uniforme durante todo el periodo en lugar de concentrarse al principio.

---

## Ejecutar

### Automatico

```bash
SCHEDULER_ENABLED=true
```

El planificador avanza la campana activa en segundo plano, respetando franjas
horarias, presupuesto y retroceso. Es reanudable: si el contenedor se reinicia,
retoma donde quedo.

### Manual

Con el planificador apagado, *Avanzar un paso* ejecuta una consulta. Sirve
tambien para diagnosticar: la respuesta dice **por que** se consulto o por que
no.

---

## Estados de una campana

| Estado | Significado |
|---|---|
| `BORRADOR` | Creada, sin encolar |
| `PROGRAMADO` | Cola lista, sin iniciar |
| `EN_CURSO` | Procesando |
| `PAUSADO` | Detenida por un operador o por el cortacircuitos |
| `COMPLETADO` | Padron cubierto |
| `CANCELADO` | Detenida definitivamente |

**Solo puede haber una campana activa.** Dos simultaneas romperian la garantia
de no repetir personas dentro del periodo.

---

## El cortacircuitos

Tras **5 fallos consecutivos** atribuibles al proveedor —error del servidor,
fallo de red o rechazo— la campana se pausa sola y lo indica en la interfaz.

No es un fallo del sistema: es una proteccion. Insistir sobre un proveedor que
esta caido o rechazando peticiones empeora la situacion para ambos lados.

**Antes de reanudar**, revise el historico filtrado por errores y verifique que
el proveedor responde. Reanudar sin mirar solo vuelve a abrir el cortacircuitos.

Una cedula invalida **no** cuenta: es culpa del dato, no del proveedor, y no
debe detener la campana entera.

---

## Resolver un desafio de verificacion

Cuando el proveedor exige verificacion humana, la consulta queda en estado
`DESAFIO_PENDIENTE`.

**Requiere el permiso `consultas:resolver`** (roles `ANALISTA`, `COORDINADOR`,
`ADMIN`).

1. Ir a *Consultas → Historico*.
2. Filtrar por estado «Espera verificacion».
3. Pulsar **Resolver** en la fila correspondiente.
4. Leer el desafio y transcribir la respuesta.

Si la respuesta es incorrecta, el proveedor emite otro desafio y se puede
reintentar. Si la sesion expiro, la consulta se reintentara desde el inicio.

**El sistema no resuelve el desafio.** Una persona lo lee y lo transcribe. Ver
[ADR-0005](../adr/0005-consultas-senescyt.md).

---

## Leer el historico

*Consultas → Historico*

| Estado | Significado | ¿Se reintenta? |
|---|---|---|
| `EXITO` | Titulos obtenidos y procesados | No |
| `SIN_DATOS` | La persona no tiene titulos registrados | No |
| `DESAFIO_PENDIENTE` | Espera verificacion humana | Al resolverlo |
| `ERROR_PROVEEDOR` | Fallo del servidor del proveedor | Si, con retroceso |
| `ERROR_RED` | Tiempo agotado o fallo de conexion | Si, con retroceso |
| `ERROR_DATOS` | Cedula invalida o rechazada | No |
| `RECHAZADO` | Limite alcanzado o acceso denegado | Si, y abre el cortacircuitos |

**Detalle** despliega los cambios campo a campo, con el valor anterior y el
nuevo. Es lo que se necesita para justificar una observacion ante Talento
Humano.

---

## Entender el planificador

*Consultas → Planificador*

Existe para responder una pregunta concreta: **¿por que el sistema no esta
consultando ahora mismo?**

Muestra la hora local, la franja vigente, el presupuesto y la capacidad
estimada, en lugar de dejar que el comportamiento parezca arbitrario.

Motivos habituales de inactividad:

- **Fuera de horario.** Antes de las 08:00 o despues de las 21:00. Indica cuando
  se reanuda.
- **Presupuesto agotado.** Se alcanzaron las consultas de esta hora. Espera al
  siguiente ciclo.
- **Cortacircuitos abierto.** La campana esta pausada y requiere revision.
- **Sin items listos.** Todos los pendientes estan programados a futuro (solo
  ocurre con el reparto activado).
