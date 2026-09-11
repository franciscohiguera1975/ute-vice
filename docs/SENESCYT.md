# Consultas al registro nacional de titulos

> Este documento explica **que hace el sistema, que no hace, y por que**. Es
> lectura obligatoria antes de tocar el modulo de consultas.

## 1. El problema

El Vicerrectorado necesita verificar los titulos academicos de su personal
contra el registro nacional. La consulta se hace por numero de cedula, persona
por persona, y debe repetirse periodicamente para detectar altas, correcciones
y bajas.

El portal publico de consulta esta protegido por un captcha.

## 2. Lo que se pidio y lo que se entrego

Durante el diseno se solicitaron, textualmente, estas capacidades:

> «manejarlo tipo bot que valide captcha», «que no active alarmas de abuso de
> consultas», «decirle la estrategia para con proxies o vpn».

| Requisito | Estado | Como se resolvio |
|---|---|---|
| Peticiones no simultaneas, espaciadas al azar | ✅ | Jitter uniforme entre consultas y presupuesto por hora |
| Mas actividad 08–17, menos 17–21 | ✅ | Perfil horario con pesos por franja |
| Campana de varios dias que sepa donde quedo | ✅ | `JobCobertura` + `ItemJob`, reanudables tras cualquier corte |
| No repetir persona hasta cubrir a todas | ✅ | `PeriodoCobertura` + `Persona.requiere_consulta()` |
| Registrar todo cambio o error | ✅ | Tabla `consulta_logs`, escrita en todos los casos |
| **Resolucion automatica del captcha** | ❌ | Cola *human-in-the-loop*: lo resuelve un operador |
| **Rotacion de proxies / VPN** | ❌ | No implementado |
| **Tecnicas para no activar deteccion** | ❌ | No documentado ni implementado |

## 3. Por que no se automatiza el captcha

Un captcha es un control de acceso. Su proposito explicito es distinguir a una
persona de un programa. Automatizar su resolucion —con reconocimiento de
imagen, con un servicio de resolucion de terceros, o de cualquier otra forma— es
evadir ese control.

Lo mismo aplica a rotar direcciones de salida o enmascarar el origen de las
peticiones para no ser reconocido como automatizacion: el objetivo declarado de
esa tecnica es que el proveedor no pueda ejercer una decision que le
corresponde.

Que el fin sea legitimo —validar los titulos del propio personal— no cambia la
naturaleza del medio. Por eso el sistema **no lo hace**, y esta decision no es
una limitacion tecnica pendiente de resolver.

## 4. Lo que si hace el sistema

### 4.1 Se identifica

El adaptador envia en cada peticion:

```
User-Agent: UTE-Vice/1.0 (validacion de titulos del personal;
            Universidad Tecnologica Equinoccial)
From: <contacto institucional configurado>
```

Si el proveedor quiere limitar o bloquear este trafico, tiene toda la
informacion para hacerlo. Que es precisamente como debe funcionar.

### 4.2 Respeta los rechazos

Ante un `403` o un `429`, la consulta se registra como `RECHAZADO`, lo que
incrementa el contador de fallos consecutivos y, al quinto, **pausa la campana
entera**. No hay reintento inmediato ni cambio de origen.

### 4.3 Reparte la carga en el tiempo

Cuatro mecanismos, todos configurables desde `.env`, implementados en
[`PoliticaPlanificacion`](../backend/src/app/domain/services/planificacion.py):

| Mecanismo | Variable | Por defecto |
|---|---|---|
| Franja de mayor actividad | `SCHEDULER_PEAK_START_HOUR` / `_END_HOUR` | 08:00–17:00 |
| Franja de menor actividad | `SCHEDULER_OFFPEAK_END_HOUR` | 17:00–21:00 |
| Peso de cada franja | `SCHEDULER_PEAK_WEIGHT` / `_OFFPEAK_WEIGHT` | 1.0 / 0.35 |
| Separacion aleatoria | `SCHEDULER_MIN/MAX_DELAY_SECONDS` | 45–240 s |
| Presupuesto por hora | `SCHEDULER_MAX_REQUESTS_PER_HOUR` | 30 |
| Retroceso ante fallos | `SCHEDULER_BACKOFF_BASE_SECONDS` | 300 s, exponencial |
| Cortacircuitos | `SCHEDULER_CIRCUIT_BREAKER_FAILURES` | 5 fallos seguidos |

Fuera de 08:00–21:00 no se consulta nada.

Con los valores por defecto, la capacidad es de unas **262 consultas por dia**.
Un padron de 3.000 personas se cubre en unos 12 dias; uno de 20.000, en unos 77.
Ese es el objetivo: que la campana dure lo que tenga que durar en lugar de
concentrarse en rafagas.

### 4.4 Garantiza la cobertura antes de repetir

La regla pedida —*no volver a consultar a nadie hasta haber consultado a
todos*— se implementa en dos piezas:

- `PeriodoCobertura`: ventana temporal a la que pertenece una campana.
- `Persona.requiere_consulta(periodo)`: devuelve `False` si la persona ya fue
  consultada con exito dentro del periodo.

La seleccion de candidatos excluye a quien ya esta cubierto. Un error si se
reintenta, pero solo despues de un margen, para no insistir sobre un fallo
reciente.

Solo puede existir **un job activo a la vez**: dos campanas simultaneas
romperian esa garantia.

### 4.5 Deja constancia de todo

Se escribe una fila en `consulta_logs` en **todos** los casos: exito, sin
titulos, error de red, rechazo, cedula invalida y desafio pendiente.

Sin esa garantia, un dato desactualizado seria indistinguible de uno que nunca
se pudo consultar. La tabla responde la pregunta que motiva la herramienta:
*¿por que el expediente de esta persona esta desfasado?*

### 4.6 Encola los desafios para una persona

Cuando el proveedor exige verificacion humana, el adaptador **no la resuelve**:
devuelve un `DesafioVerificacion`, la consulta queda en estado
`DESAFIO_PENDIENTE`, y el item del job pasa a `ESPERANDO_DESAFIO`.

Un operador con permiso `consultas:resolver` lo atiende desde el historico de
consultas en la interfaz: ve el desafio, lo lee y transcribe la respuesta. La
sesion HTTP se conserva entre ambos pasos.

Una persona resuelve el desafio, que es exactamente para lo que el desafio
existe.

## 5. Los tres proveedores

El puerto `ProveedorConsultaTitulos` tiene tres implementaciones. Se elige con
`SENESCYT_PROVIDER`:

### `mock` — desarrollo y pruebas

Genera titulos ficticios **deterministas**: la misma cedula produce siempre el
mismo resultado. Simula tambien errores, ausencia de titulos y desafios, para
que las pruebas ejerciten los caminos que importan.

No apto para produccion. La aplicacion lo advierte al arrancar si detecta
`ENVIRONMENT=production` con este proveedor.

### `manual` — cola asistida por un operador

Adaptador HTTP real con resolucion humana del desafio.

**Requiere configuracion.** Las rutas, los nombres de campo y los selectores del
portal no vienen fijados en el codigo: cambian cuando el portal cambia, y
codificarlos a ciegas produciria un adaptador que falla en silencio. Se declaran
en `ConfiguracionPortal` y deben verificarse contra el sitio real.

Sin configurar, `verificar_disponibilidad()` devuelve `False` y las consultas
fallan con un mensaje explicito. El analisis del HTML de resultados
(`_analizar_html`) esta marcado como punto de extension y devuelve `None`
mientras no se implemente — deliberadamente `None` y no una lista vacia, porque
«no se pudo leer» y «la persona no tiene titulos» son cosas distintas: la
segunda marcaria a la persona como consultada y la sacaria de la cola.

El procedimiento de puesta a punto esta en
[`manual/consultas-senescyt.md`](manual/consultas-senescyt.md).

### `oficial` — API bajo convenio

**Es la via recomendada.** Un acuerdo formal con la entidad que administra el
registro: credenciales propias, cuotas pactadas, sin desafios de por medio.

El adaptador esta escrito contra un contrato REST convencional. Cuando se firme
el convenio, lo previsible es ajustar `_mapear_respuesta` al esquema real; el
resto del sistema no cambia, porque todo depende del puerto y no de esa clase.

Activarlo es cambiar una variable de entorno:

```bash
SENESCYT_PROVIDER=oficial
SENESCYT_OFICIAL_API_URL=https://…
SENESCYT_OFICIAL_API_KEY=…
```

## 6. Recomendacion

Gestionar el convenio institucional. Elimina el captcha, elimina la
incertidumbre juridica, permite subir el ritmo con respaldo formal y libera a un
funcionario de transcribir codigos.

Mientras tanto, el proveedor `manual` con un presupuesto conservador cubre la
necesidad, y el `mock` permite desarrollar y probar todo lo demas sin depender
de nada externo.

## 7. Consideraciones legales y de datos

- Los datos que se consultan y almacenan son **informacion personal** de
  empleados identificables. Su tratamiento se rige por la Ley Organica de
  Proteccion de Datos Personales del Ecuador.
- La finalidad —verificar los titulos del propio personal— debe estar declarada
  y ser conocida por los titulares.
- El acceso a la plataforma queda registrado, y los reportes generados llevan
  constancia de quien los produjo y con que filtros.
- Ver [`SECURITY.md`](SECURITY.md) para los controles implementados.
