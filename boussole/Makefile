# Boussole — commandes de développement (annexe Phase 10 §E).
#
# Prérequis : Docker + Python 3.12. Premier passage sur un clone neuf :
#
#     make venv
#
# Toutes les cibles Python d'en dessous supposent `api/.venv` — l'en-tête le
# disait déjà (« venv dans api/.venv ») mais AUCUNE cible ne le créait. Un
# clone neuf tombait sur « .venv/bin/ruff: No such file or directory » dès le
# premier `make lint`, sans que rien n'indique la commande manquante.

COMPOSE := docker compose -f infra/docker-compose.dev.yml
API_DIR := api
PY := .venv/bin/python
ALEMBIC := .venv/bin/alembic

.PHONY: venv up down migrate seed seed-demo test test-integration evaluate demo lint typecheck api-dev openapi-gen

venv: ## Crée api/.venv et installe l'API + ses outils de développement
	@command -v python3.12 >/dev/null 2>&1 || { \
	  echo "python3.12 introuvable — voir les prérequis en tête de ce fichier"; \
	  exit 1; }
	cd $(API_DIR) && python3.12 -m venv .venv
	cd $(API_DIR) && .venv/bin/pip install --upgrade pip
	# `observability` est installé ici comme dans l'image (infra/Dockerfile.api) :
	# sans lui, poser SENTRY_DSN en local fait échouer le démarrage, et on
	# cherche longtemps.
	cd $(API_DIR) && .venv/bin/pip install -e ".[dev,observability]"
	@echo "Prêt : make test, make lint, make typecheck."

up: ## Démarre postgres, redis ×2, minio, mailpit, api, worker, beat, web
	$(COMPOSE) up -d --build

down: ## Arrête et supprime les conteneurs
	$(COMPOSE) down

migrate: ## alembic upgrade head
	cd $(API_DIR) && $(ALEMBIC) -c alembic/alembic.ini upgrade head

seed: ## Référentiels idempotents (sectors, skills, prompt_versions, sources)
	cd $(API_DIR) && $(PY) -m app.seeds

seed-demo: ## Données de démo (dev/staging uniquement — D22)
	cd $(API_DIR) && $(PY) -m app.seeds demo

demo: ## Base VIDE → application utilisable (migrations + corpus + compte validé)
	@echo "Amorçage complet : migrations, référentiels, ingestion du corpus de"
	@echo "démonstration (offres FICTIVES, D34), embeddings, compte au profil"
	@echo "validé. Refusé hors développement. Sortie non nulle si le résultat"
	@echo "n'est pas une application réellement utilisable."
	cd $(API_DIR) && $(ALEMBIC) -c alembic/alembic.ini upgrade head
	cd $(API_DIR) && $(PY) -m app.demo

test: ## Tests unitaires (rapides, sans Docker — l'intégration est exclue par défaut)
	cd $(API_DIR) && $(PY) -m pytest tests/unit

test-integration: ## Tests d'intégration : PostgreSQL RÉEL (pgvector) + migrations Alembic
	@echo "PostgreSQL éphémère via testcontainers (image pgvector/pgvector:pg16)."
	@echo "Sans Docker : BOUSSOLE_TEST_DATABASE_URL=postgresql+asyncpg://… (base JETABLE,"
	@echo "tronquée entre chaque test). Voir api/tests/integration/README.md."
	cd $(API_DIR) && $(PY) -m pytest tests/integration -m integration

evaluate: ## Mesure la qualité du matching contre les evaluation_gates
	@echo "Jeu de CAS DE RÉFÉRENCE CONSTRUITS, pas d'annotations humaines"
	@echo "d'offres réelles : ce rapport dit si le moteur se comporte comme"
	@echo "attendu, pas si le matching est bon (Q19/Q20/Q47)."
	cd $(API_DIR) && $(PY) -m app.evaluation

lint: ## Ruff
	cd $(API_DIR) && .venv/bin/ruff check .

typecheck: ## Mypy (strict sur app/core et futur app/matching)
	cd $(API_DIR) && .venv/bin/mypy

api-dev: ## API en rechargement à chaud (hors Docker)
	cd $(API_DIR) && .venv/bin/uvicorn app.main:app --reload --port 8000

openapi-gen: ## Génération du client TS depuis openapi.yaml (stub M1)
	@echo "openapi-gen : sera branché avec web/ (openapi-typescript) — voir ../cv-job-matching/openapi.yaml"
