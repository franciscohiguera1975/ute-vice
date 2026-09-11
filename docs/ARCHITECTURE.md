# Arquitectura

## La regla que sostiene todo lo demas

Una sola regla explica la estructura del proyecto: **las dependencias apuntan
hacia adentro**.

```
    ┌─────────────────────────────────────────────┐
    │  api / interfaces        (FastAPI, Angular) │
    │      ↓                                      │
    │  application             (casos de uso)     │
    │      ↓                                      │
    │  domain                  (reglas de negocio)│
    │      ↑                                      │
    │  infrastructure          (PostgreSQL, JWT…) │
    └─────────────────────────────────────────────┘
```

`domain` no importa a nadie. Ni SQLAlchemy, ni FastAPI, ni Pydantic, ni `httpx`.
Solo la biblioteca estandar de Python.

Eso no es purismo. Tiene tres consecuencias practicas que se notan a diario:

1. **Las reglas de negocio se prueban en milisegundos.** Las 200+ pruebas
   unitarias corren sin Docker, sin base de datos y sin red.
2. **Cambiar de proveedor externo no toca el negocio.** El SENESCYT tiene tres
   implementaciones intercambiables; el dominio no sabe cual esta activa.
3. **Los casos de uso se podran exponer como skills de IA sin reescribirlos**
   (Fase 14). Ya no dependen de HTTP.

Hay una prueba automatica que verifica la regla analizando los `import` de cada
modulo: [`tests/unit/test_arquitectura.py`](../backend/tests/unit/test_arquitectura.py).
Si alguien introduce un `import sqlalchemy` en el dominio, la prueba falla y
explica que hacer en su lugar.

---

## Backend

```
backend/src/app/
├── core/                     configuracion tipada y registro estructurado
├── domain/
│   ├── entities/             Usuario, Rol, Persona, Titulo, ConsultaLog, JobCobertura
│   ├── value_objects.py      Cedula, Email, ContrasenaEnClaro, PeriodoCobertura
│   ├── enums.py              Permisos, estados, niveles
│   ├── errors.py             jerarquia de errores de negocio
│   ├── services/             reconciliador de titulos, politica de planificacion
│   └── ports/                contratos que la infraestructura debe cumplir
├── application/
│   ├── base.py               CasoDeUso, ContextoEjecucion
│   └── casos_uso/            autenticacion, usuarios, personas, titulos,
│                             consultas, reportes, analitica
├── infrastructure/
│   ├── db/                   modelos ORM, mapeadores, repositorios, unidad de trabajo
│   ├── seguridad/            Argon2, JWT, Google OAuth, LDAP
│   ├── senescyt/             proveedores mock / manual / oficial
│   ├── reportes/             exportadores Excel, CSV, PDF
│   ├── planificador/         ejecutor en segundo plano
│   └── contenedor.py         raiz de composicion
└── api/
    ├── dependencias.py       inyeccion, autenticacion, autorizacion
    ├── errores.py            traduccion de errores de dominio a HTTP
    ├── esquemas/             modelos de entrada y salida (Pydantic)
    └── v1/routers/           endpoints
```

### Puertos y adaptadores

Cada dependencia externa entra por un puerto declarado en el dominio:

| Puerto | Que abstrae | Implementaciones |
|---|---|---|
| `RepositorioPersonas`, `RepositorioTitulos`, … | persistencia | PostgreSQL; dobles en memoria en pruebas |
| `UnidadDeTrabajo` | limite transaccional | sesion de SQLAlchemy |
| `HasherContrasenas` | derivacion de claves | Argon2id |
| `ServicioTokens` | emision y verificacion | JWT + secreto opaco |
| `ProveedorIdentidad` | identidad federada | Google OAuth, LDAP/AD |
| `ProveedorConsultaTitulos` | consulta al registro | mock, manual, oficial |
| `ExportadorReporte` | formato de salida | Excel, CSV, PDF |
| `Reloj`, `FuenteAleatoria` | tiempo y azar | sistema; congelados en pruebas |

Los dos ultimos merecen una nota. Las reglas de planificacion dependen de la
hora y del azar. Si el dominio llamara a `datetime.now()` y a `random`
directamente, seria imposible verificar el comportamiento a las 03:00 sin
esperar a esa hora. Con los puertos, una prueba inyecta un reloj congelado y una
semilla fija.

### Los casos de uso tienen una firma unica

```python
resultado = await caso(entrada, contexto)
```

`CasoDeUso.__call__` comprueba el permiso declarado antes de ejecutar. Ningun
caso de uso puede olvidarse de autorizar: si declara `permiso_requerido`, la
verificacion es automatica. Hay una prueba que exige que todo caso de uso lo
declare o figure en una lista de exentos justificados.

Esa uniformidad es tambien la preparacion para la Fase 14: cada caso de uso ya
expone un `descriptor()` con su nombre, descripcion y permiso, que es
exactamente lo que necesita un catalogo de skills.

### Autorizacion por permiso, nunca por rol

El codigo pregunta `usuario.puede(Permiso.PERSONAS_ESCRIBIR)`. Nunca
`usuario.tiene_rol("COORDINADOR")`.

La diferencia importa cuando el Vicerrectorado pida un rol nuevo —«auditor
externo», «coordinador de facultad»—: se crea el rol, se le asignan permisos, y
no se toca ni un endpoint ni una plantilla.

---

## Frontend

La misma estructura, en TypeScript:

```
frontend/src/app/
├── domain/
│   ├── modelos/              entidades y enumeraciones (espejo del backend)
│   └── puertos/              clases abstractas = contratos + tokens de inyeccion
├── data/                     implementaciones HTTP de los puertos
├── core/                     sesion (signals), interceptores, guardas
├── shared/                   componentes, directivas, pipes, layout
└── features/                 una carpeta por seccion, cargada de forma diferida
```

Los componentes dependen de `RepositorioPersonas`, no de `HttpClient`. La
consecuencia: una prueba de componente inyecta una implementacion en memoria y
no necesita simular peticiones HTTP.

`app.config.ts` es la raiz de composicion: el unico sitio donde se decide que
clase concreta cumple cada contrato, igual que `contenedor.py` en el backend.

### Estado con signals

`SesionStore` mantiene el usuario y los tokens con signals. Las plantillas leen
`sesion.puede(...)` directamente, sin `async` ni suscripciones que cancelar.

La directiva `*utePermiso` oculta lo que el usuario no puede usar. **No es un
control de seguridad** —quien conozca la URL de la API puede llamarla igual—;
la autorizacion real la impone el backend en cada caso de uso. Lo que evita es
ofrecer una accion que terminaria en un 403.

---

## Decisiones transversales

### Modelos ORM separados de las entidades

`PersonaModel` (SQLAlchemy) y `Persona` (dominio) son clases distintas, con
`mapeadores.py` traduciendo entre ambas. Es codigo adicional, y vale la pena:
sin esa separacion, cada columna nueva se filtra hasta las reglas de negocio y
un cambio de esquema arrastra al dominio entero.

### Los errores no conocen HTTP

El dominio lanza `NoEncontrado`, `ConflictoDeEstado`, `ErrorAutorizacion`. La
capa de API los traduce a 404, 409 y 403 en un unico lugar
([`api/errores.py`](../backend/src/app/api/errores.py)). Cuando los casos de uso
se expongan por MCP (Fase 15), ese canal hara su propia traduccion sin tocar el
negocio.

Todas las respuestas de error comparten forma, para que el frontend tenga un
solo contrato que interpretar:

```json
{"codigo": "no_encontrado", "mensaje": "…", "detalles": {}, "request_id": "…"}
```

### Nomenclatura entre capas

El backend usa `snake_case`; el frontend, `camelCase`. La conversion ocurre en
un unico punto —[`data/mapeo.ts`](../frontend/src/app/data/mapeo.ts)— en lugar
de renunciar a una de las dos convenciones o escribir un mapeador por entidad.

---

## Como se extiende

Agregar una tabla nueva (Fase 12) es un procedimiento mecanico que no toca nada
de lo existente:

1. Entidad en `domain/entities/`
2. Puerto de repositorio en `domain/ports/repositorios.py`
3. Modelo ORM y mapeador en `infrastructure/db/`
4. Implementacion del repositorio
5. Casos de uso en `application/casos_uso/`
6. Esquemas y router en `api/`
7. Registro en el contenedor
8. Espejo en el frontend: modelo, puerto, repositorio HTTP, componentes

El paso a paso con ejemplos esta en
[`manual/extender-modelo.md`](manual/extender-modelo.md).
