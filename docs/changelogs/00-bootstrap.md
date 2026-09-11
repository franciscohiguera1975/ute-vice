# Fase 00 · Bootstrap del monorepo

**Fecha:** 2026-09-04 · **Estado:** cerrada

## Objetivo

Dejar el repositorio en un estado donde `make up` levante la plataforma completa
y donde la estructura ya refleje las decisiones de arquitectura, en lugar de
tener que reorganizarla mas adelante.

## Entregado

### Monorepo

```
ute-vice/
├── docker-compose.yml     postgres 18 + backend + frontend
├── Makefile               atajos de desarrollo y operacion
├── .env.example           plantilla de configuracion documentada
├── backend/
├── frontend/
├── infra/postgres/init/   extensiones de PostgreSQL
└── docs/
```

Se eligio monorepo, y no dos repositorios, porque backend y frontend comparten
un contrato que cambia junto: un cambio de API y su consumo viajan en el mismo
commit y se revisan a la vez.

### Docker Compose

Tres servicios con dependencias por estado de salud: el backend no arranca hasta
que PostgreSQL responde `pg_isready`. Sin eso, el primer arranque falla de forma
intermitente y confusa.

El puerto externo de PostgreSQL es **5433**, no 5432, para no chocar con una
instalacion local en la maquina de quien desarrolla.

### Configuracion

`.env.example` con 60+ variables agrupadas y comentadas. Cada bloque explica que
hace y que valores admite. Es el documento que va a leer quien despliegue, asi
que se escribio para eso y no como una lista de nombres.

### Extensiones de PostgreSQL

`pgcrypto` (UUID del lado del servidor), `pg_trgm` (busqueda por similitud) y
`unaccent` (normalizacion de acentos). Se instalan al crear el volumen.

## Decisiones

- **Puerto 5433 en el host.** Evita el choque mas comun.
- **Un `.env` unico en la raiz**, no uno por servicio. La configuracion de la
  plataforma es una sola cosa; repartirla obliga a mantener sincronizados
  valores que deben coincidir.
- **`Makefile` como interfaz de operacion.** `make up`, `make seed`, `make test`.
  Quien opera no deberia tener que recordar la sintaxis de `docker compose exec`.

## Pendiente al cerrar

- La imagen de produccion del frontend (nginx) esta escrita pero no se ha
  probado en un despliegue real.
- No hay pipeline de integracion continua.
