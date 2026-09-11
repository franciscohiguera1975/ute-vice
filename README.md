# UTE-VICE — Gestion Academica

Plataforma del Vicerrectorado de la Universidad Tecnologica Equinoccial.
Centraliza la informacion academica del personal —titulos universitarios,
validados contra el registro nacional, y el distributivo docente— con CRUD,
tablero y exportacion.

FastAPI · PostgreSQL 18 · Angular 20 · Arquitectura limpia

---

## Arranque

```bash
cp .env.example .env    # ajustar SECRET_KEY y contrasenas
make up                 # postgres + backend + frontend
make seed               # roles, permisos y superusuario
make seed-demo          # opcional: 60 personas ficticias
```

- **Interfaz** — <http://localhost:4200>
- **API** — <http://localhost:8000/docs>

Ingrese con las credenciales de `FIRST_SUPERUSER_*`. El sistema exige cambiar la
contrasena en el primer acceso.

Detalle en [`docs/manual/instalacion.md`](docs/manual/instalacion.md).

---

## Que hace

- **Padron de personal** con busqueda difusa, filtros y carga masiva.
- **Expediente academico** por persona, distinguiendo titulos vigentes de
  retirados.
- **Consultas al registro nacional** por cedula, con campanas reanudables que
  cubren todo el padron sin repetir a nadie dentro del periodo.
- **Historico completo** de cada intento de consulta, con el detalle de los
  cambios campo a campo.
- **Distributivo docente** con sus doce catalogos, la carga horaria repartida por
  actividad y la captura de la asignatura que imparte cada docente.
- **Tablero** de cobertura, composicion academica y tendencia de consultas.
- **Reportes** en Excel, CSV y PDF, con constancia de los filtros aplicados. El
  distributivo se exporta con **plantillas intercambiables**: la institucional y
  la que reproduce el archivo de origen para contrastar.
- **Control de acceso por permisos**, con acceso local, Google OAuth y
  directorio activo.

---

## Sobre las consultas al SENESCYT

El portal publico esta protegido por captcha. **Este sistema no automatiza su
resolucion ni enmascara el origen de sus peticiones.**

Lo que si hace: reparte la carga en el tiempo con franjas horarias y presupuesto
por hora, garantiza que el padron se cubra entero antes de repetir a nadie,
respeta los rechazos del proveedor deteniendose, y encola los desafios de
verificacion para que **una persona** los resuelva desde la interfaz.

El proveedor de consulta es intercambiable: si la UTE obtiene un convenio
institucional, se activa la API oficial cambiando una variable de entorno.

Razonamiento completo en [`docs/SENESCYT.md`](docs/SENESCYT.md).

---

## Estructura

```
ute-vice/
├── backend/     FastAPI · dominio, casos de uso, infraestructura, API
├── frontend/    Angular · dominio, datos, core, componentes, pantallas
├── infra/       inicializacion de PostgreSQL
└── docs/        arquitectura, decisiones, changelogs y manual
```

Ambos lados siguen la misma regla: **las dependencias apuntan hacia adentro**.
El dominio no conoce el framework, ni la base de datos, ni el proveedor externo.
Hay una prueba automatica que lo verifica.

---

## Documentacion

| Documento | Para que |
|---|---|
| [`docs/CONTEXT.md`](docs/CONTEXT.md) | **Estado del proyecto y punto de retomada** |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Capas, puertos y por que estan asi |
| [`docs/DATA_MODEL.md`](docs/DATA_MODEL.md) | Modelo entidad-relacion y diccionario de datos |
| [`docs/SENESCYT.md`](docs/SENESCYT.md) | Estrategia de consultas y sus limites |
| [`docs/SECURITY.md`](docs/SECURITY.md) | Controles, compromisos conocidos y pendientes |
| [`docs/ROADMAP.md`](docs/ROADMAP.md) | Fases cerradas, en curso y futuras |
| [`docs/adr/`](docs/adr/) | Decisiones tecnicas con sus alternativas descartadas |
| [`docs/changelogs/`](docs/changelogs/) | Historico por fase |
| [`docs/manual/`](docs/manual/) | Instalacion, operacion y uso |

---

## Desarrollo

```bash
make test              # pruebas del backend
make test-integracion  # las de integracion, sobre una base desechable
make lint              # ruff + mypy
make migration m="descripcion"
make psql
make help        # todos los atajos
```

Las pruebas unitarias corren **sin Docker, sin base de datos y sin red** — es el
beneficio directo de la arquitectura. Las de integracion se omiten solas si no
hay PostgreSQL disponible.

Para agregar una tabla nueva:
[`docs/manual/extender-modelo.md`](docs/manual/extender-modelo.md).

---

## Estado

Fases 00 a 07 y 09 cerradas; fase 08 (calidad) en curso. **357 pruebas en verde.**

Backend y frontend funcionales, verificados de extremo a extremo contra
PostgreSQL real y contra el consolidado de distributivo completo (15.219 filas).
Lo pendiente esta listado en [`docs/CONTEXT.md`](docs/CONTEXT.md).
