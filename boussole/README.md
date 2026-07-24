# Boussole — monorepo

Assistant de candidature (matching CV ↔ offres, explicable et respectueux du RGPD).
**Spécifications complètes** : [`../cv-job-matching/`](../cv-job-matching/) — notamment
[15-delivery-roadmap.md](../cv-job-matching/15-delivery-roadmap.md) (annexe Phase 10),
[12-api-contracts.md](../cv-job-matching/12-api-contracts.md),
[openapi.yaml](../cv-job-matching/openapi.yaml),
[initial-schema.sql](../cv-job-matching/initial-schema.sql) et
[decisions.md](../cv-job-matching/decisions.md).

État : **jalon M1 (fondations)** — auth complète (register/login/logout/me,
sessions Redis, CSRF, rate limiting, erreurs RFC 9457), migration 0001, seeds,
Celery (files D16), Docker Compose dev, CI. Les autres modules sont des stubs
501 documentés (M2+).

## Arborescence

```
boussole/
├── api/          # FastAPI (Python 3.12) — app/core, app/modules/*, alembic, tests
├── infra/        # docker-compose.dev.yml, Dockerfiles, workflow CI
├── Makefile      # up, migrate, seed, test, lint, typecheck, api-dev…
└── .env.example  # variables de dev (aucun secret réel — D23)
```

## Démarrage rapide

```bash
cd boussole

# 1. Infrastructure complète (postgres, redis ×2, minio, mailpit, api, web)
make up

# 2. Schéma de base (migration 0001 = initial-schema.sql)
make migrate

# 3. Référentiels (secteurs NACE, skills, prompt_versions, sources inactives)
make seed          # + make seed-demo pour 3 profils synthétiques (dev only, D22)

# 4. API en rechargement à chaud, hors Docker (nécessite le venv ci-dessous)
make api-dev       # http://localhost:8000/api/v1/docs
```

Venv de développement :

```bash
cd api
python3.12 -m venv .venv
.venv/bin/pip install -e ".[dev]"
cp ../.env.example .env
```

Vérifications : `make lint` (ruff), `make typecheck` (mypy, strict sur
`app/core` et le futur `app/matching`), `make test` (pytest — unitaires sans
Postgres : repository en mémoire + fakeredis).

Workers Celery (files `ingestion`/`ai`/`scoring`/`maintenance`, D16) :

```bash
cd api && .venv/bin/celery -A app.workers.celery_app worker -Q ingestion,ai,scoring,maintenance
```

## Variables d'environnement

Voir [.env.example](.env.example) pour les valeurs de dev.

| Variable | Rôle | Défaut dev |
|---|---|---|
| `ENV` | `development` / `staging` / `production` | `development` |
| `DATABASE_URL` | PostgreSQL 16 + pgvector, driver **asyncpg** (D06) | `postgresql+asyncpg://boussole:boussole@localhost:5432/boussole` |
| `REDIS_PERSISTENT_URL` | sessions + broker Celery — AOF, noeviction (D17) | `redis://localhost:6379/0` |
| `REDIS_CACHE_URL` | cache + rate limiting — allkeys-lru (D17) | `redis://localhost:6380/0` |
| `S3_ENDPOINT` / `S3_BUCKET` / `S3_REGION` | stockage objet UE (D09), MinIO en dev | `http://localhost:9000` / `boussole-dev` / `eu-west-1` |
| `S3_ACCESS_KEY` / `S3_SECRET_KEY` | identifiants MinIO dev (vault en prod, D23) | `boussole-dev` / `boussole-dev-secret` |
| `SESSION_TTL_DAYS` | TTL glissant des sessions | `30` |
| `ANTHROPIC_API_KEY` / `FALLBACK_LLM_API_KEY` | providers LLM (D08) — via vault (D23) | vide |
| `EMBEDDINGS_MODEL` / `EMBEDDINGS_DIM` | embeddings 🟡 Q11 | `voyage-3-large` / `1024` |
| `SCORING_CONFIG_PATH` | config de scoring versionnée (D02) | `config/scoring-config.json` |
| `FEATURE_SOURCE_*` | connecteurs derrière flags (D04) | `false` |
| `SENTRY_DSN` / `OTEL_EXPORTER_OTLP_ENDPOINT` | observabilité (D20) | vide |

## CI

Le workflow GitHub Actions est fourni dans
[`infra/github-workflows/boussole-ci.yml`](infra/github-workflows/boussole-ci.yml) —
à déplacer vers `.github/workflows/` (voir le README de ce dossier).
Jobs sur PR touchant `boussole/` : **lint** (ruff + mypy) et **test** (pytest).
