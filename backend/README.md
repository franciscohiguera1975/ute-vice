# Backend — UTE-VICE

API en FastAPI con arquitectura limpia. La documentacion completa vive en
[`../docs/`](../docs/); aqui solo esta lo minimo para trabajar en el backend.

## Capas

```
src/app/
├── domain/          Reglas de negocio puras. No importa nada de fuera.
├── application/     Casos de uso. Depende solo de domain.
├── infrastructure/  Adaptadores: PostgreSQL, JWT, SENESCYT, Excel.
└── api/             FastAPI: routers, esquemas, inyeccion de dependencias.
```

La regla de dependencia es unidireccional: `api → application → domain` e
`infrastructure → domain`. **`domain` no importa a nadie.** Hay una prueba
automatica que lo verifica (`tests/unit/test_arquitectura.py`).

## Comandos

```bash
make sh-backend      # shell en el contenedor
make migrate         # alembic upgrade head
make migration m="…" # nueva migracion autogenerada
make seed            # roles, permisos y superusuario
make test            # pytest
make lint            # ruff + mypy
```
