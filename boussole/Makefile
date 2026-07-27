# Boussole — commandes de développement (annexe Phase 10 §E).
# Prérequis : Docker + Python 3.12 (venv dans api/.venv).

COMPOSE := docker compose -f infra/docker-compose.dev.yml
API_DIR := api
PY := .venv/bin/python
ALEMBIC := .venv/bin/alembic

.PHONY: up down migrate seed seed-demo test test-integration lint typecheck api-dev openapi-gen

up: ## Démarre postgres, redis ×2, minio, mailpit, api, web
	$(COMPOSE) up -d --build

down: ## Arrête et supprime les conteneurs
	$(COMPOSE) down

migrate: ## alembic upgrade head
	cd $(API_DIR) && $(ALEMBIC) -c alembic/alembic.ini upgrade head

seed: ## Référentiels idempotents (sectors, skills, prompt_versions, sources)
	cd $(API_DIR) && $(PY) -m app.seeds

seed-demo: ## Données de démo (dev/staging uniquement — D22)
	cd $(API_DIR) && $(PY) -m app.seeds demo

test: ## Tests unitaires (rapides, sans Docker — l'intégration est exclue par défaut)
	cd $(API_DIR) && $(PY) -m pytest tests/unit

test-integration: ## Tests d'intégration : PostgreSQL RÉEL (pgvector) + migrations Alembic
	@echo "PostgreSQL éphémère via testcontainers (image pgvector/pgvector:pg16)."
	@echo "Sans Docker : BOUSSOLE_TEST_DATABASE_URL=postgresql+asyncpg://… (base JETABLE,"
	@echo "tronquée entre chaque test). Voir api/tests/integration/README.md."
	cd $(API_DIR) && $(PY) -m pytest tests/integration -m integration

lint: ## Ruff
	cd $(API_DIR) && .venv/bin/ruff check .

typecheck: ## Mypy (strict sur app/core et futur app/matching)
	cd $(API_DIR) && .venv/bin/mypy

api-dev: ## API en rechargement à chaud (hors Docker)
	cd $(API_DIR) && .venv/bin/uvicorn app.main:app --reload --port 8000

openapi-gen: ## Génération du client TS depuis openapi.yaml (stub M1)
	@echo "openapi-gen : sera branché avec web/ (openapi-typescript) — voir ../cv-job-matching/openapi.yaml"
