# Boussole — monorepo

Assistant de candidature (matching CV ↔ offres, explicable et respectueux du RGPD).

**État : six jalons livrés et mergés** — M1 fondations + auth, M2 ingestion + recherche,
M3 matching + explications, M4 CV + générations + candidatures, M5 privacy + durcissement,
M6 mise en service (S3, provider LLM réel, embeddings, tests d'intégration PostgreSQL).

L'application fonctionne de bout en bout : compte → import CV → profil validé →
préférences → recherche d'offres → score expliqué → génération ancrée → suivi de
candidature → export / suppression RGPD.

> **Avant tout déploiement, lire les deux documents d'exploitation** :
> - [18-deployment-runbook.md](../cv-job-matching/18-deployment-runbook.md) — prérequis,
>   inventaire complet des variables, garde-fous de démarrage, séquence de déploiement,
>   **opérations post-déploiement obligatoires**, planification beat, rollback ;
> - [19-mvp-status.md](../cv-job-matching/19-mvp-status.md) — ce qui est réellement
>   implémenté, ce qui est inactif par défaut et pourquoi, ce qui manque, et ce qui reste
>   avant une alpha fermée.
>
> Deux points d'attention immédiats, détaillés dans le runbook : **exactement un**
> processus `celery beat` doit tourner (deux dupliquent chaque tâche planifiée, purges
> comprises), et le changement de tokenisation de M6 impose un **backfill forcé des
> embeddings**.
>
> ⚠️ Ce bloc portait jusqu'ici trois avertissements dont **deux étaient faux** — et
> faux dans le sens qui inquiète : « le compose ne contient pas de service `celery
> beat` » (il en porte un depuis la finalisation) et « `PRIVACY_SIGNING_KEY` a une
> valeur par défaut qu'aucun garde-fou ne vérifie » (`app/core/secrets.py` refuse le
> démarrage hors développement). Le runbook disait l'inverse des deux. C'est le
> document qu'on lit EN PREMIER qui était périmé, et il envoyait chercher des
> problèmes résolus tout en laissant croire que la documentation d'exploitation était
> approximative.

## Arborescence réelle

```
boussole/
├── api/                          # FastAPI (Python 3.12)
│   ├── app/
│   │   ├── core/                 # config, db, redis, security, storage, ratelimit, problems
│   │   ├── matching/             # moteur déterministe PUR (aucun import hors stdlib)
│   │   ├── ai/
│   │   │   ├── providers/        # base, fake, anthropic, factory (+ circuit breaker)
│   │   │   ├── embeddings/       # base, hashing (défaut), managed (squelette), factory, backfill
│   │   │   ├── tasks/            # extract_cv, extract_job, generate
│   │   │   ├── calls.py          # journal ai_calls (métadonnées uniquement)
│   │   │   └── scrubbing.py      # barrière PII déterministe avant prompt
│   │   ├── modules/              # auth, profiles(+cv), preferences, jobs, ingestion,
│   │   │                         # matching, explanations, generation, applications,
│   │   │                         # privacy, ai_calls, referentials
│   │   ├── workers/              # celery_app (files + beat_schedule) + tâches par domaine
│   │   ├── seeds.py              # référentiels idempotents + données de démo
│   │   └── main.py               # middlewares, /healthz, /readyz, montage des routers
│   ├── alembic/versions/         # 0001 → 0007 (voir runbook §4.1)
│   ├── config/scoring-config.json
│   └── tests/
│       ├── unit/                 # suite rapide — sans Docker (repos en mémoire + fakeredis)
│       └── integration/          # PostgreSQL 16 + pgvector RÉEL
├── web/                          # Next.js 15 (App Router), TypeScript, Tailwind
│   ├── app/(auth)/               # inscription, connexion
│   ├── app/(main)/               # tableau-de-bord, offres, profil, preferences,
│   │                             # candidatures, parametres
│   ├── app/api/[...path]/        # proxy BFF même origine (cookies, CSRF, Accept-Language)
│   ├── components/               # ui, jobs, match, profile, generation, dashboard, layout
│   ├── lib/api/                  # clients typés par domaine
│   └── messages/                 # fr.json, en.json (parité vérifiée par script)
├── infra/
│   ├── docker-compose.dev.yml    # postgres, redis ×2, minio(+init), mailpit, api, worker, web
│   ├── Dockerfile.api            # multi-stage, non-root, uvicorn --proxy-headers
│   ├── Dockerfile.web
│   └── github-workflows/         # boussole-ci.yml — À DÉPLACER vers .github/workflows/
├── Makefile
└── .env.example                  # valeurs de dev — aucun secret réel (D23)
```

## Démarrage rapide

### 1. Venv de développement

```bash
cd boussole/api
python3.12 -m venv .venv
.venv/bin/pip install -e ".[dev]"
cp ../.env.example .env
```

### 2. Infrastructure

```bash
cd boussole
make up            # postgres, redis ×2, minio (+ bucket), mailpit, api, worker, web
```

Le compose de dev tourne **délibérément** avec le même backend de stockage que la
production (`STORAGE_BACKEND=s3`, ici MinIO) et avec l'API et le worker Celery dans
**deux conteneurs distincts** — c'est l'écart inverse (dev mono-processus sur disque
local) qui avait masqué le fait que l'export RGPD répondait 404 en multi-conteneur.

> ⚠️ Le compose **ne démarre pas de `celery beat`**. Aucune tâche planifiée ne s'exécute
> tant qu'on ne le lance pas soi-même (voir plus bas).

### 3. Schéma et référentiels

```bash
make migrate       # alembic upgrade head — révisions 0001 → 0007
make seed          # secteurs NACE, compétences + alias, prompt_versions, sources (inactives)
make seed-demo     # 3 profils synthétiques — dev/staging uniquement, refusé si ENV=production
```

### 4. Développement

```bash
make api-dev       # uvicorn --reload sur :8000 — docs sur /api/v1/docs (masquées en production)

# Worker Celery — les quatre files
cd api && .venv/bin/celery -A app.workers.celery_app worker -Q ingestion,ai,scoring,maintenance

# Celery beat — INDISPENSABLE : ingestion, expiration d'offres, backfills et PURGE RGPD
cd api && .venv/bin/celery -A app.workers.celery_app beat

# Front
cd web && npm install && npm run dev    # http://localhost:3000
```

Sondes : `GET /healthz` (liveness, inconditionnelle) et `GET /readyz` (readiness réelle :
base, deux Redis, **et** joignabilité du stockage objet par `HeadBucket`).

## Tests

Deux suites, volontairement séparées.

### Suite unitaire — rapide, sans Docker

```bash
make test                     # depuis boussole/
# ou : cd api && .venv/bin/python -m pytest tests/unit
```

Aucune base de données : repositories en mémoire, `fakeredis`, stockage sur répertoire
temporaire. ~86 s. C'est la suite qu'on lance en boucle.

### Suite d'intégration — PostgreSQL 16 + pgvector **réel**

```bash
make test-integration         # depuis boussole/
# ou : cd api && .venv/bin/python -m pytest tests/integration -m integration
```

Exclue par défaut (`addopts = -m "not integration"` dans `pyproject.toml`). Deux modes :

1. **conteneur éphémère** (défaut) : `testcontainers` démarre `pgvector/pgvector:pg16`,
   applique les **vraies migrations Alembic**, détruit le conteneur en fin de session.
   Docker absent → la suite est `skip`ée avec un message explicite ;
2. **base fournie** :

   ```bash
   BOUSSOLE_TEST_DATABASE_URL="postgresql+asyncpg://…/boussole_test" \
     .venv/bin/python -m pytest tests/integration -m integration
   ```

   ⚠️ La base est **tronquée entre chaque test** — n'y pointer qu'une base jetable.

Cette suite existe parce que la suite unitaire n'exerce jamais de base : c'est ainsi
qu'un bug de fuseau horaire (500 sur toute pagination par date) et une purge RGPD
incomplète avaient été livrés. Détail : [`api/tests/integration/README.md`](api/tests/integration/README.md).

### Lint et types

```bash
make lint          # ruff — E, F, W, I, UP, B, SIM, RUF
make typecheck     # mypy — strict sur app.core.* et app.matching.*
```

### Front

```bash
cd web
npm run lint       # next lint
npm run typecheck  # tsc --noEmit
npm run i18n:check # parité fr.json / en.json
```

🟡 Le front n'a **aucune suite de tests automatisés** à ce jour.

## Variables d'environnement

L'inventaire **complet et normatif** (63 champs `Settings` + 5 `INGESTION_*` +
`FORWARDED_ALLOW_IPS`), avec pour chacun son rôle, son défaut, son caractère obligatoire
en production et sa sensibilité, est dans
**[18-deployment-runbook.md §2](../cv-job-matching/18-deployment-runbook.md)**.
[`.env.example`](.env.example) donne les valeurs de développement.

Extrait — les variables qu'on touche en premier :

| Variable | Rôle | Défaut dev |
|---|---|---|
| `ENV` | `development` / `staging` / `production` — **vocabulaire fermé**, toute autre valeur fait échouer le démarrage | `development` |
| `DATABASE_URL` | PostgreSQL 16 + pgvector, driver **asyncpg** obligatoire | `postgresql+asyncpg://boussole:boussole@localhost:5432/boussole` |
| `REDIS_PERSISTENT_URL` | sessions + broker Celery — AOF, `noeviction` | `redis://localhost:6379/0` |
| `REDIS_CACHE_URL` | cache + rate limiting + quotas — `allkeys-lru` | `redis://localhost:6380/0` |
| `STORAGE_BACKEND` | `local` \| `s3` — **`local` fait échouer le démarrage dès `staging`** | `local` (`s3` dans le compose) |
| `S3_SSE` | `none` \| `AES256` \| `aws:kms` — **`none` fait échouer le démarrage dès `staging`** | `AES256` (`none` dans le compose) |
| `PRIVACY_SIGNING_KEY` | HMAC des liens d'export RGPD — 🔴 **défaut public, aucun garde-fou** | `boussole-dev-privacy-signing` |
| `FORWARDED_ALLOW_IPS` | proxies de confiance pour `X-Forwarded-For` (uvicorn **et** application) | `127.0.0.1` |
| `AI_PROVIDER` | `fake` \| `anthropic` — le provider réel n'est jamais actif implicitement | `fake` |
| `EMBEDDINGS_PROVIDER` | `hashing` (local, déterministe) \| `managed` (squelette, Q11) | `hashing` |
| `FEATURE_SOURCE_*` | connecteurs d'offres derrière flags (Q2/Q3 non tranchées) | `false` |
| `SCORING_CONFIG_PATH` | config de scoring versionnée | `config/scoring-config.json` |
| `SENTRY_DSN` / `OTEL_EXPORTER_OTLP_ENDPOINT` | 🟡 déclarés mais **jamais lus par le code** — sans effet | vide |

## Garde-fous de démarrage

L'application **refuse de démarrer** — API *et* workers Celery, à l'import — plutôt que
de perdre des données en silence :

- `ENV` hors `{development, staging, production}` ;
- `STORAGE_BACKEND=local` hors développement (l'API et les workers ne partagent pas de
  disque : exports RGPD introuvables, CV perdus au redémarrage) ;
- `S3_SSE=none` hors développement (chiffrement au repos exigé) ;
- `STORAGE_BACKEND=s3` sans `S3_BUCKET`.

Justification détaillée de chaque refus : [runbook §3](../cv-job-matching/18-deployment-runbook.md).

## CI

✅ **Active.** [`.github/workflows/boussole-ci.yml`](../.github/workflows/boussole-ci.yml)
définit quatre jobs sur PR touchant `boussole/` : **lint** (ruff + mypy), **tests
unitaires**, détection de changement `api/`, et **tests d'intégration** sur un service
`pgvector/pgvector:pg16`.

Le fichier a passé six jalons dans `infra/github-workflows/` avec une note demandant de
le déplacer : aucune vérification automatique n'a tourné sur les PR de tout le projet.

## Spécifications

Tout est dans [`../cv-job-matching/`](../cv-job-matching/) :

| Document | Contenu |
|---|---|
| [01-product-brief](../cv-job-matching/01-product-brief.md) → [05-functional-specifications](../cv-job-matching/05-functional-specifications.md) | Vision, personas, IA/flux, specs fonctionnelles F-A…F-Q |
| [06-matching-specification](../cv-job-matching/06-matching-specification.md) | Les 12 dimensions, score, confiance, bloquants |
| [07-job-ingestion-specification](../cv-job-matching/07-job-ingestion-specification.md) | Connecteurs, normalisation, dédup, expiration |
| [08-ai-specification](../cv-job-matching/08-ai-specification.md) | Prompts, schémas de sortie, ancrage, journalisation |
| [09-security-and-privacy](../cv-job-matching/09-security-and-privacy.md) · [10-system-architecture](../cv-job-matching/10-system-architecture.md) | RGPD, chiffrement, architecture |
| [11-data-model](../cv-job-matching/11-data-model.md) · [initial-schema.sql](../cv-job-matching/initial-schema.sql) | Modèle de données (source de la migration 0001) |
| [12-api-contracts](../cv-job-matching/12-api-contracts.md) · [openapi.yaml](../cv-job-matching/openapi.yaml) | Contrats d'API |
| [13-testing-strategy](../cv-job-matching/13-testing-strategy.md) → [16-risk-register](../cv-job-matching/16-risk-register.md) | Tests, analytics, roadmap, risques |
| [17-open-questions](../cv-job-matching/17-open-questions.md) | Questions non tranchées — dont les préalables juridiques |
| **[18-deployment-runbook](../cv-job-matching/18-deployment-runbook.md)** | **Runbook d'exploitation** |
| **[19-mvp-status](../cv-job-matching/19-mvp-status.md)** | **État réel du MVP** |
| [decisions.md](../cv-job-matching/decisions.md) · [traceability-matrix.md](../cv-job-matching/traceability-matrix.md) | Décisions D01–D23, traçabilité besoin → test |
