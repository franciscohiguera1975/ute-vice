# =====================================================================
# UTE-VICE — Atajos de desarrollo
# =====================================================================
SHELL := /bin/bash
COMPOSE := docker compose

.DEFAULT_GOAL := help

.PHONY: help
help: ## Muestra esta ayuda
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2}'

# ---------------------------- Entorno --------------------------------
.PHONY: env
env: ## Crea .env a partir de .env.example si no existe
	@test -f .env || (cp .env.example .env && echo "-> .env creado; revisa SECRET_KEY y contrasenas")

.PHONY: up
up: env ## Levanta toda la plataforma
	$(COMPOSE) up -d --build

.PHONY: down
down: ## Detiene la plataforma
	$(COMPOSE) down

.PHONY: reset
reset: ## Detiene y BORRA los volumenes (destruye la base de datos)
	$(COMPOSE) down -v

.PHONY: logs
logs: ## Sigue los logs de todos los servicios
	$(COMPOSE) logs -f

.PHONY: ps
ps: ## Estado de los servicios
	$(COMPOSE) ps

# ---------------------------- Backend --------------------------------
.PHONY: sh-backend
sh-backend: ## Shell dentro del contenedor del backend
	$(COMPOSE) exec backend bash

.PHONY: migrate
migrate: ## Aplica las migraciones pendientes
	$(COMPOSE) exec backend alembic upgrade head

.PHONY: migration
migration: ## Genera una migracion nueva: make migration m="mensaje"
	$(COMPOSE) exec backend alembic revision --autogenerate -m "$(m)"

.PHONY: downgrade
downgrade: ## Revierte la ultima migracion
	$(COMPOSE) exec backend alembic downgrade -1

.PHONY: seed
seed: ## Carga roles, permisos y el superusuario inicial
	$(COMPOSE) exec backend python -m app.cli seed

.PHONY: seed-demo
seed-demo: ## Carga datos de demostracion (personas y titulos ficticios)
	$(COMPOSE) exec backend python -m app.cli seed-demo

.PHONY: test
test: ## Pruebas del backend (las de integracion se omiten: ver test-integracion)
	$(COMPOSE) exec backend pytest -q

# Las pruebas de integracion recrean el esquema entero, asi que se niegan a
# correr contra una base que no termine en `_test`. Este objetivo crea la base
# desechable y apunta ahi, en lugar de arrasar la de desarrollo.
.PHONY: test-integracion
test-integracion: ## Pruebas de integracion, sobre una base desechable
	@U=$${POSTGRES_USER:-ute}; D=$${POSTGRES_DB:-ute_vice}_test; \
	  $(COMPOSE) exec -T postgres createdb -U $$U $$D 2>/dev/null || true; \
	  $(COMPOSE) exec -T postgres psql -U $$U -d $$D -q -c \
	    "CREATE EXTENSION IF NOT EXISTS pgcrypto; CREATE EXTENSION IF NOT EXISTS pg_trgm; CREATE EXTENSION IF NOT EXISTS unaccent;"; \
	  $(COMPOSE) exec -e POSTGRES_DB=$$D backend pytest -q -m integration

.PHONY: lint
lint: ## Ruff + mypy sobre el backend
	$(COMPOSE) exec backend ruff check src tests
	$(COMPOSE) exec backend mypy src

.PHONY: format
format: ## Formatea el codigo del backend
	$(COMPOSE) exec backend ruff format src tests
	$(COMPOSE) exec backend ruff check --fix src tests

# ---------------------------- Frontend -------------------------------
.PHONY: sh-frontend
sh-frontend: ## Shell dentro del contenedor del frontend
	$(COMPOSE) exec frontend sh

.PHONY: test-front
test-front: ## Pruebas unitarias de Angular
	$(COMPOSE) exec frontend npm run test:ci

.PHONY: lint-front
lint-front: ## Linter de Angular
	$(COMPOSE) exec frontend npm run lint

.PHONY: build-front
build-front: ## Build de produccion de Angular
	$(COMPOSE) exec frontend npm run build

# ---------------------------- Base de datos --------------------------
.PHONY: psql
psql: ## Consola psql sobre la base del contenedor
	$(COMPOSE) exec postgres psql -U $${POSTGRES_USER:-ute} -d $${POSTGRES_DB:-ute_vice}

.PHONY: dump
dump: ## Respaldo comprimido en ./backups
	@mkdir -p backups
	$(COMPOSE) exec -T postgres pg_dump -U $${POSTGRES_USER:-ute} -d $${POSTGRES_DB:-ute_vice} \
		| gzip > backups/ute_vice_$$(date +%Y%m%d_%H%M%S).sql.gz
	@echo "-> respaldo escrito en ./backups"
