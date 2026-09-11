# Seguridad y proteccion de datos

## Que datos custodia este sistema

Informacion personal de empleados identificables: cedula, nombre, correo,
telefono, fecha de nacimiento, vinculacion laboral y expediente academico
completo.

Su tratamiento se rige por la **Ley Organica de Proteccion de Datos Personales
del Ecuador**. La finalidad —verificar los titulos del propio personal— debe
estar declarada y ser conocida por los titulares.

Todo lo que sigue existe por ese motivo.

---

## Controles implementados

### Autenticacion

| Control | Implementacion |
|---|---|
| Derivacion de claves | Argon2id, 64 MiB de memoria, 3 pasadas, 4 hilos |
| Rehash transparente | Al iniciar sesion, si los parametros subieron desde el ultimo acceso |
| Politica de contrasenas | ≥10 caracteres, mayuscula, minuscula, digito, especial; se rechazan secuencias comunes |
| Bloqueo por intentos | 5 fallos → 15 minutos de bloqueo |
| Resistencia a temporizacion | Se consume el mismo coste de hashing aunque la cuenta no exista |
| Token de acceso | JWT firmado, 30 minutos, con emisor y audiencia verificados |
| Token de refresco | Secreto opaco de 48 bytes; en la base solo se guarda su HMAC-SHA256 |
| Rotacion del refresco | Cada canje emite uno nuevo y revoca el anterior |
| Deteccion de reutilizacion | Un token ya revocado revoca **todas** las sesiones del usuario |
| Cambio de contrasena | Revoca todas las sesiones abiertas |
| Contrasena provisional | Una cuenta nueva o restablecida no puede navegar hasta cambiarla |

Sobre el bloqueo por temporizacion: si la respuesta a un correo inexistente
fuera mas rapida que a uno registrado, un atacante podria enumerar cuentas
midiendo tiempos. Por eso, cuando el correo no existe, se ejecuta igualmente una
operacion de hashing.

### Autorizacion

- Se resuelve **por permiso**, nunca por rol. 19 permisos atomicos.
- La comprobacion vive en `CasoDeUso.__call__`: ningun caso de uso puede
  olvidarse de autorizar. Hay una prueba que exige que todos declaren su permiso
  o figuren en una lista de exentos justificados.
- Los endpoints declaran ademas el permiso como dependencia, lo que lo hace
  visible en la documentacion de OpenAPI y evita ejecutar trabajo que va a ser
  rechazado.
- **El usuario se recarga de la base en cada peticion**, aunque el token traiga
  los permisos. Es un viaje mas, y es intencional: sin el, revocar un rol no
  tendria efecto hasta que expirara el token, y una cuenta desactivada seguiria
  operando media hora.
- La interfaz oculta lo que el usuario no puede usar. **Eso no es un control de
  seguridad** —quien conozca la URL de la API puede llamarla igual—; la
  autorizacion real la impone el backend.

### Proteccion contra abusos comunes

| Vector | Mitigacion |
|---|---|
| Inyeccion SQL | ORM con consultas parametrizadas; el `ORDER BY` acepta solo columnas de una lista blanca |
| XSS | La API devuelve JSON, nunca HTML interpretable; CSP `default-src 'none'` |
| Clickjacking | `X-Frame-Options: DENY` y `frame-ancestors 'none'` |
| Sniffing de tipo | `X-Content-Type-Options: nosniff` |
| CSRF en OAuth | Parametro `state` obligatorio en el flujo de Google |
| Redireccion abierta | El parametro `retorno` de la pantalla de acceso solo admite rutas internas |
| Fuga por referrer | `Referrer-Policy: no-referrer` |
| Enumeracion de cuentas | Mismo error y mismo tiempo para correo inexistente y contrasena incorrecta |
| Filtro LDAP inyectado | Se rechazan los caracteres con significado en un filtro, en vez de escaparlos |
| Concurrencia en la cola | `FOR UPDATE SKIP LOCKED`: dos trabajadores nunca toman la misma persona |

### Registro y trazabilidad

- Cada peticion recibe un `request_id` que viaja por `ContextVar` y vuelve en la
  cabecera `X-Request-ID`. Cualquier log emitido durante esa peticion queda
  correlacionado.
- Las cedulas se enmascaran en los registros (`17******65`).
- **Los mensajes de excepcion nunca llegan al cliente.** Un error no controlado
  devuelve un texto generico y el `request_id`; el detalle queda en los
  registros del servidor.
- La tabla `consulta_logs` es un historico de solo insercion.
- Los reportes llevan constancia de quien los genero, cuando y con que filtros.

### Configuracion

Un **cerrojo de produccion** impide arrancar con valores de ejemplo. Con
`ENVIRONMENT=production`, la aplicacion se niega a iniciar si:

- `SECRET_KEY` es el de ejemplo o mide menos de 32 caracteres
- `POSTGRES_PASSWORD` es el de ejemplo
- `FIRST_SUPERUSER_PASSWORD` es el de ejemplo
- `DEBUG=true`
- `CORS_ORIGINS` contiene un origen `http://` no local

Ademas, en produccion se desactivan `/docs`, `/redoc` y `/openapi.json`.

### Contenedores

- El proceso del backend corre como usuario sin privilegios (uid 1001).
- La imagen de produccion no incluye herramientas de desarrollo.
- El frontend se sirve con nginx estatico, sin Node en ejecucion.

---

## Compromisos conocidos

Se documentan porque una decision de seguridad sin su contrapartida explicita es
una decision a medias.

### Los tokens se guardan en `localStorage`

**Riesgo:** quedan expuestos a un XSS, a diferencia de una cookie `HttpOnly`.

**Por que:** el backend es un servicio separado del frontend. Usar cookies
exigiria un proxy de sesion o compartir dominio, lo que complica el despliegue.

**Compensacion:** tokens de acceso cortos (30 min), rotacion del refresco con
deteccion de reutilizacion, y una politica de contenido restrictiva. Si se
despliega backend y frontend bajo el mismo dominio, migrar a cookies `HttpOnly`
es una mejora recomendable.

### `X-Forwarded-For` se cree

**Riesgo:** si la aplicacion se expusiera directamente a internet, un cliente
podria falsear su IP en los registros.

**Por que:** el despliegue previsto tiene un proxy inverso delante que reescribe
la cabecera.

**Compensacion:** la IP se usa solo para auditoria, nunca para autorizar.
**Requisito de despliegue:** no exponer el backend sin proxy inverso.

### La validacion de cedula esta duplicada

El algoritmo de modulo 10 se implementa en el backend (Python) y en el frontend
(TypeScript).

Es duplicacion deliberada. El backend sigue siendo la autoridad; el frontend
valida solo para dar respuesta inmediata sin un viaje al servidor.

---

## Pendiente

Trabajo identificado y no incluido en esta etapa:

- **Bitacora de auditoria general.** Hoy se audita el proceso de consultas
  (`consulta_logs`), pero no las operaciones administrativas: quien cambio un
  rol, quien desactivo una cuenta. El permiso `auditoria:leer` ya existe
  reservado para esto.
- **Cifrado en reposo** de los campos mas sensibles.
- **Segundo factor** para los roles administrativos.
- **Politica de retencion** de `consulta_logs` y de los reportes generados.
- **Revision de seguridad independiente** antes del despliegue en produccion.

---

## Antes de desplegar en produccion

```bash
# 1. Generar un secreto real
python -c "import secrets; print(secrets.token_urlsafe(64))"

# 2. En el .env de produccion
ENVIRONMENT=production
DEBUG=false
SECRET_KEY=<el generado arriba>
POSTGRES_PASSWORD=<contrasena fuerte, no la de ejemplo>
FIRST_SUPERUSER_PASSWORD=<contrasena fuerte>
CORS_ORIGINS=https://vice.ute.edu.ec        # solo https
SENESCYT_PROVIDER=manual                    # o `oficial`; nunca `mock`
```

Lista de verificacion:

- [ ] TLS terminado en el proxy inverso, con HSTS
- [ ] El backend no accesible directamente desde internet
- [ ] Respaldos automaticos de PostgreSQL, y una restauracion probada
- [ ] Rotacion de registros configurada
- [ ] Contrasena del superusuario cambiada en el primer acceso
- [ ] `SENESCYT_PROVIDER` distinto de `mock`
- [ ] Politica de retencion de datos acordada con el Vicerrectorado
