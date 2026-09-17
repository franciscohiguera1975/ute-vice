# Referencia de la API

**Base:** `/api/v1` · **Documentacion interactiva:** `/docs` (desactivada en
produccion)

---

## Autenticacion

Token JWT en la cabecera:

```
Authorization: Bearer <token de acceso>
```

### Obtener un token

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"admin@ute.edu.ec","contrasena":"…"}'
```

```json
{
  "tokens": {
    "acceso": "eyJhbGciOi…",
    "refresco": "kZ8v…",
    "tipo": "bearer",
    "expira_en_segundos": 1800
  },
  "usuario": { "…": "…", "permisos": ["personas:leer", "…"] },
  "debe_cambiar_contrasena": false
}
```

El token de acceso dura 30 minutos. El de refresco, 7 dias, **y rota en cada
uso**: al canjearlo se emite uno nuevo y el anterior queda revocado.

> Si se presenta un token de refresco ya canjeado, el sistema asume robo y
> **revoca todas las sesiones del usuario**. No reutilice tokens.

---

## Forma de las respuestas

### Listados paginados

```json
{
  "items": [ … ],
  "total": 156,
  "pagina": 1,
  "tamano": 25,
  "total_paginas": 7,
  "tiene_siguiente": true,
  "tiene_anterior": false
}
```

Parametros: `pagina`, `tamano` (1–200), `ordenar_por`, `descendente`.

### Errores

Todos comparten forma:

```json
{
  "codigo": "no_encontrado",
  "mensaje": "Persona no encontrado: 3f2b…",
  "detalles": { "entidad": "Persona", "id": "3f2b…" },
  "request_id": "a1b2c3d4…"
}
```

`codigo` es estable y apto para logica; `mensaje` es para mostrar. El
`request_id` tambien vuelve en la cabecera `X-Request-ID`: citelo al reportar un
problema.

| HTTP | Codigos habituales |
|---|---|
| 401 | `token_invalido`, `credenciales_invalidas` |
| 403 | `sin_permiso`, `usuario_inactivo` |
| 404 | `no_encontrado` |
| 409 | `ya_existe`, `conflicto_estado` |
| 413 | `reporte_demasiado_grande` |
| 422 | `validacion`, `regla_negocio` |
| 429 | `usuario_bloqueado`, `limite_consultas` |
| 501 | `proveedor_no_habilitado` |
| 502 | `error_proveedor` |

---

## Endpoints

### Autenticacion

| Metodo | Ruta | Descripcion |
|---|---|---|
| `GET` | `/auth/metodos` | Metodos de acceso habilitados (publico) |
| `POST` | `/auth/login` | Iniciar sesion con credenciales locales |
| `POST` | `/auth/login/ldap` | Iniciar sesion contra el directorio activo |
| `GET` | `/auth/google/autorizar` | Iniciar el flujo de Google |
| `GET` | `/auth/google/callback` | Retorno del flujo de Google |
| `POST` | `/auth/refrescar` | Renovar el par de tokens |
| `POST` | `/auth/logout` | Cerrar la sesion actual |
| `POST` | `/auth/logout-todas` | Cerrar todas las sesiones propias |
| `GET` | `/auth/perfil` | Perfil y permisos del usuario |
| `POST` | `/auth/cambiar-contrasena` | Cambiar la contrasena propia |

### Personas

| Metodo | Ruta | Permiso |
|---|---|---|
| `GET` | `/personas` | `personas:leer` |
| `POST` | `/personas` | `personas:escribir` |
| `GET` | `/personas/{id}` | `personas:leer` |
| `GET` | `/personas/cedula/{cedula}` | `personas:leer` |
| `PATCH` | `/personas/{id}` | `personas:escribir` |
| `DELETE` | `/personas/{id}` | `personas:eliminar` |
| `POST` | `/personas/importar` | `personas:importar` |

Filtros de `GET /personas`: `texto`, `unidad`, `tipo_vinculacion`, `activo`,
`con_titulos`, `nunca_consultadas`, `estado_ultima_consulta`.

### Titulos

| Metodo | Ruta | Permiso |
|---|---|---|
| `GET` | `/titulos` | `titulos:leer` |
| `POST` | `/titulos` | `titulos:escribir` |
| `GET` | `/titulos/{id}` | `titulos:leer` |
| `PATCH` | `/titulos/{id}` | `titulos:escribir` |
| `POST` | `/titulos/{id}/verificar` | `titulos:verificar` |
| `DELETE` | `/titulos/{id}` | `titulos:eliminar` |

> Los titulos de origen `SENESCYT` devuelven **422** en `PATCH` y `DELETE`: sus
> datos provienen del registro nacional y no deben editarse.

### Consultas

| Metodo | Ruta | Permiso |
|---|---|---|
| `POST` | `/consultas/personas/{id}` | `consultas:ejecutar` |
| `GET` | `/consultas/logs` | `consultas:leer` |
| `GET` | `/consultas/jobs` | `consultas:leer` |
| `POST` | `/consultas/jobs` | `consultas:administrar` |
| `GET` | `/consultas/jobs/{id}` | `consultas:leer` |
| `POST` | `/consultas/jobs/{id}/control` | `consultas:administrar` |
| `POST` | `/consultas/jobs/{id}/avanzar` | `consultas:ejecutar` |
| `POST` | `/consultas/desafios/resolver` | `consultas:resolver` |
| `GET` | `/consultas/estado-planificador` | `consultas:leer` |

`POST /consultas/personas/{id}` devuelve **409** si la persona ya fue consultada
dentro del periodo vigente. Use `?forzar=true` con justificacion.

### Tablero y reportes

| Metodo | Ruta | Permiso |
|---|---|---|
| `GET` | `/tablero?dias=30` | `dashboard:ver` |
| `GET` | `/distributivo/tablero` | `distributivo:leer` |
| `GET` | `/distributivo/resumenes` | `distributivo:leer` |
| `GET` | `/distributivo/resumenes/exportar` | `reportes:generar` |
| `GET` | `/reportes/distributivo/ambito` | `distributivo:leer` |
| `POST` | `/distributivo/importaciones/pao` | `distributivo:importar` |
| `GET` | `/reportes/formatos` | `reportes:generar` |
| `GET` | `/reportes/personas` | `reportes:generar` |
| `GET` | `/reportes/titulos` | `reportes:generar` |
| `GET` | `/reportes/consultas` | `reportes:generar` |

Los reportes devuelven el archivo binario con `Content-Disposition`. Parametro
`formato`: `XLSX`, `CSV` o `PDF`.

`GET /distributivo/tablero` acepta `grupo_a` —la referencia— y `grupo_b` —el que
se examina—, repetibles. Sin ellos compara los dos ultimos semestres enteros, la
misma eleccion que hacen los resumenes. Pide `distributivo:leer` y no
`dashboard:ver` para que el rol de consulta del distributivo pueda verlo.

`GET /distributivo/resumenes` acepta `grupo_a` y `grupo_b`, repetibles para
varios periodos cada uno. Sin ellos compara los dos ultimos semestres enteros.
Devuelve los dos resumenes —avance y estados por facultad— sobre los mismos
grupos, en una sola respuesta.

`GET /reportes/distributivo/ambito` acepta `pao_ids` y `facultad_ids`,
repetibles. Devuelve `facultades` —las que tienen filas en esos periodos— y
`carreras` —las de esas facultades dentro de esos periodos—. Las dos viajan
juntas para que no puedan contradecirse entre si.

`GET /distributivo/resumenes/exportar` toma los mismos `grupo_a` y `grupo_b`,
mas `resumen`, `grupo` (`a` o `b`, para el desglose de estados), `etiqueta_a` y
`etiqueta_b` —como titular cada grupo; vacio usa el semestre— y `formato`
(`XLSX`, `CSV` o `PDF`). Hay cuatro resumenes: `avance` y `estados` son los de la
pantalla de resumenes; `aprobacion` y `comparativo`, las dos tablas del tablero.
Cada uno sale del mismo caso de uso que alimenta su pantalla. Devuelve el archivo binario con
`Content-Disposition`; **422** si los periodos elegidos no tienen datos.

`POST /distributivo/importaciones/pao` es `multipart/form-data`: `archivo`
(`.xls`, `.xlsx` o `.xlsm`, hasta 25 MB), `semestre` (`2026-2`, obligatorio
porque el archivo no lo trae), `interciclo`, `actualizar_existentes` y `hoja`.
Devuelve el informe de la carga; **422** si el archivo no tiene la estructura
esperada.

### Administracion

| Metodo | Ruta | Permiso |
|---|---|---|
| `GET` | `/usuarios` | `usuarios:leer` |
| `POST` | `/usuarios` | `usuarios:escribir` |
| `GET` | `/usuarios/{id}` | `usuarios:leer` |
| `PATCH` | `/usuarios/{id}` | `usuarios:escribir` |
| `POST` | `/usuarios/{id}/contrasena` | `usuarios:escribir` |
| `DELETE` | `/usuarios/{id}` | `usuarios:eliminar` |
| `GET` | `/roles` | `usuarios:leer` |
| `PATCH` | `/roles/{codigo}` | `roles:administrar` |
| `GET` | `/permisos` | `usuarios:leer` |

### Sistema

| Metodo | Ruta | Descripcion |
|---|---|---|
| `GET` | `/health` | Estado del servicio (sin prefijo `/api/v1`) |

---

## Ejemplo completo

```bash
BASE=http://localhost:8000/api/v1

# 1. Autenticarse
TOKEN=$(curl -s -X POST $BASE/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"admin@ute.edu.ec","contrasena":"…"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['tokens']['acceso'])")

AUTH="Authorization: Bearer $TOKEN"

# 2. Personas sin titulos registrados
curl -s -H "$AUTH" "$BASE/personas?con_titulos=false&tamano=10"

# 3. Crear una campana de cobertura
JOB=$(curl -s -X POST -H "$AUTH" -H 'Content-Type: application/json' \
  -d '{"nombre":"Actualizacion 2026-I","iniciar_inmediatamente":true}' \
  $BASE/consultas/jobs \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['job']['id'])")

# 4. Avanzar un paso
curl -s -X POST -H "$AUTH" "$BASE/consultas/jobs/$JOB/avanzar"

# 5. Descargar el reporte de titulos
curl -s -H "$AUTH" -OJ "$BASE/reportes/titulos?formato=XLSX"
```

---

## Notas

- **Fechas**: ISO 8601 en UTC (`2026-09-04T14:30:00Z`). La conversion a hora de
  Ecuador ocurre en la interfaz.
- **Nomenclatura**: `snake_case` en la API. El frontend convierte a `camelCase`
  en su capa de datos.
- **Cedulas**: se valida el digito verificador. Una cedula invalida devuelve
  **422** antes de tocar la base.
- **CORS**: solo los origenes de `CORS_ORIGINS`. `Content-Disposition` y
  `Content-Length` estan expuestos para que el navegador pueda leer el nombre de
  los archivos descargados.
