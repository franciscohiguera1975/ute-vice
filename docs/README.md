# Documentacion — UTE-VICE

Plataforma de gestion y validacion de titulos universitarios del personal de la
Universidad Tecnologica Equinoccial (UTE), construida sobre FastAPI + PostgreSQL
+ Angular con arquitectura limpia.

## Como leer esta documentacion

| Si eres... | Empieza por |
|---|---|
| Una IA que retoma el trabajo | [`CONTEXT.md`](CONTEXT.md) — estado exacto del proyecto |
| Desarrollador nuevo | [`ARCHITECTURE.md`](ARCHITECTURE.md) → [`manual/instalacion.md`](manual/instalacion.md) |
| Usuario funcional | [`manual/`](manual/) |
| Product owner | [`ROADMAP.md`](ROADMAP.md) |

## Indice

### Documentos base
- **[CONTEXT.md](CONTEXT.md)** — Estado del proyecto, decisiones vigentes y punto
  de retomada. **Este es el documento de traspaso entre sesiones de IA.**
- [ARCHITECTURE.md](ARCHITECTURE.md) — Arquitectura limpia, capas, dependencias y
  aplicacion concreta de SOLID en backend y frontend.
- [DATA_MODEL.md](DATA_MODEL.md) — Modelo entidad-relacion y diccionario de datos.
- [ROADMAP.md](ROADMAP.md) — Fases cerradas, en curso y futuras.
- [SENESCYT.md](SENESCYT.md) — Estrategia de consultas al SENESCYT, limites
  eticos y legales, y lo que el sistema deliberadamente NO hace.
- [SECURITY.md](SECURITY.md) — Modelo de amenazas, manejo de datos personales y
  controles implementados.

### Decisiones de arquitectura (ADR)
- [adr/](adr/) — Registro de decisiones tecnicas con su contexto y consecuencias.

### Historico
- [changelogs/](changelogs/) — Un archivo por fase, con lo entregado, los archivos
  tocados y lo que quedo pendiente.

### Manual de uso
- [manual/](manual/) — Instalacion, operacion y uso funcional de la aplicacion.

## Convenciones de esta carpeta

1. **Un changelog por fase**, nombrado `NN-nombre-fase.md`. No se reescribe una
   fase cerrada: si algo cambia, se registra en la fase siguiente.
2. **`CONTEXT.md` se actualiza al cerrar cada fase.** Es el unico documento que
   se sobrescribe, y siempre refleja el presente.
3. Toda decision con alternativas descartadas se documenta como ADR.
4. La documentacion se escribe en espanol; el codigo, en ingles.
