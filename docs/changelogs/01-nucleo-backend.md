# Fase 01 · Nucleo del backend

**Fecha:** 2026-09-04 · **Estado:** cerrada

## Objetivo

Construir la capa de dominio completa y la infraestructura de persistencia,
estableciendo la regla de dependencia que va a gobernar el resto del proyecto.

## Entregado

### Configuracion tipada (`core/config.py`)

Configuracion por secciones anidadas (`settings.jwt.secret_key`), validada al
arrancar. Si falta algo o esta mal formado, el proceso muere de inmediato con un
mensaje claro en lugar de fallar a mitad de una peticion.

Incluye un **cerrojo de produccion**: con `ENVIRONMENT=production`, la
aplicacion se niega a iniciar si detecta secretos de ejemplo, `DEBUG=true` o un
origen CORS sin cifrar.

### Registro estructurado (`core/logging.py`)

JSON en produccion, texto coloreado en desarrollo. El `request_id` viaja por
`ContextVar`, de modo que cualquier log emitido durante una peticion queda
correlacionado sin pasarlo por parametro.

### Capa de dominio

- **Objetos de valor**: `Cedula` (con el algoritmo de modulo 10 del Registro
  Civil), `Email`, `ContrasenaEnClaro`, `NombrePersona`, `PeriodoCobertura`.
- **Entidades** con comportamiento, no anemicas: `Usuario.puede()`,
  `Persona.requiere_consulta()`, `JobCobertura.registrar_resultado()`.
- **Errores de negocio** en una jerarquia que la API traduce a codigos HTTP.
- **Puertos**: repositorios, unidad de trabajo, seguridad, SENESCYT, reportes,
  reloj y fuente de azar.

### Persistencia

11 tablas, mapeadores entidad ↔ modelo, repositorios sobre PostgreSQL, unidad de
trabajo reentrante y Alembic en modo asincrono.

## Decisiones

Ver [ADR-0001](../adr/0001-arquitectura-limpia.md) y
[ADR-0003](../adr/0003-modelos-orm-separados.md).

Dos decisiones menos evidentes:

- **`Reloj` y `FuenteAleatoria` como puertos.** Parecen exagerados hasta que hay
  que probar que a las 22:00 el planificador espera a las 08:00.
  Ver [ADR-0007](../adr/0007-ritmo-en-el-dominio.md).
- **Unidad de trabajo reentrante.** Un caso de uso puede invocar a un
  colaborador que tambien abre el contexto, sin abrir una transaccion paralela.

## Hallazgos durante la construccion

- **Las tablas de asociacion son Core, no ORM.** `mapped_column()` no funciona
  dentro de `Table()`; hay que usar `Column()`. Detectado al cargar los modelos.
- **La migracion inicial se genero contra un PostgreSQL 18 real**, no a mano. Se
  verifico que aplica y revierte limpiamente.

## Pendiente al cerrar

- Sin indices de rendimiento afinados: los actuales son los evidentes.
- Sin politica de retencion para `consulta_logs`.
