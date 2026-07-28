# 18 — Runbook de déploiement et d'exploitation

> Document **opérationnel**. Tout ce qui suit a été vérifié dans le code de `boussole/` — rédigé au commit `811d4d1` (merge M6), tenu à jour depuis (dernier passage : lot post-M6 n° 1). Les commandes citées existent dans le `Makefile`, le `docker-compose.dev.yml`, le `Dockerfile.api` ou sont directement dérivables des tâches Celery enregistrées. Les incertitudes et les points non vérifiables depuis le code portent 🟡.
>
> Ce document ne tranche **aucune** question juridique. Les points de conformité renvoient à [17-open-questions.md](17-open-questions.md).

---

## 1. Prérequis d'infrastructure

| Composant | Version / caractéristique exigée | Preuve dans le code |
|---|---|---|
| **PostgreSQL 16 + pgvector** | extensions `vector`, `pg_trgm`, `unaccent`, `citext` ; colonnes `vector(1024)` + index HNSW cosinus | `alembic/versions/sql/0001_initial.sql`, image `pgvector/pgvector:pg16` (compose dev + CI) |
| **Driver applicatif** | `postgresql+asyncpg://…` — **obligatoire** | `app/core/db.py`, `alembic/env.py` (`create_async_engine`) |
| **Redis « persistant »** | sessions + broker Celery + backend de résultats. AOF activé, `maxmemory-policy noeviction` | `celery_app.py` (`broker=` et `backend=` = `redis_persistent_url`), compose dev |
| **Redis « cache »** | cache, rate limiting, quotas de génération et d'export. LRU (`allkeys-lru`), perte acceptable | `app/core/ratelimit.py`, `app/modules/generation/service.py`, compose dev |
| **Stockage objet S3 UE** | bucket dédié, versionnement recommandé, **SSE obligatoire** hors développement | `app/core/storage.py::S3ObjectStorage`, `check_storage_configuration` |
| **Broker + workers Celery** | 4 files : `ingestion`, `ai`, `scoring`, `maintenance` (`acks_late`, `prefetch=1`) | `app/workers/celery_app.py` |
| **Celery beat** | **processus séparé**, indispensable (voir §6) | `beat_schedule` dans `celery_app.py` |
| **Front Next.js** | proxy BFF même origine ; son adresse doit figurer dans `FORWARDED_ALLOW_IPS` de l'API | `web/app/api/[...path]/route.ts`, `app/main.py::trusted_proxies` |

> ⚠️ **Deux Redis logiques distincts** (D17). Une éviction LRU sur l'instance persistante détruirait des sessions ou des messages de broker. La faisabilité chez l'hébergeur UE retenu est **Q40, non tranchée**.

### Ce que l'infrastructure ne fournit **pas** aujourd'hui

- **Aucun envoi d'e-mail transactionnel.** Aucun module SMTP/mailer n'existe dans `api/app` (vérifié : aucune occurrence de `smtp`, `mailer`, `send_email`). `mailpit` est présent dans le compose de dev mais **rien ne lui écrit**. Conséquence : pas d'e-mail de confirmation de suppression de compte (hypothèse Q30), pas de digest (Q9).
- **Aucun antivirus à l'upload.** ClamAV (Q16) est explicitement hors périmètre (`app/modules/profiles/cv/router.py`). Les protections en place sont structurelles (magic bytes, bornes anti-bombe de décompression) — pas un scan de contenu.
- **Aucune exportation d'observabilité.** `SENTRY_DSN` et `OTEL_EXPORTER_OTLP_ENDPOINT` sont **déclarés dans la configuration mais jamais lus par le code applicatif** (vérifié par recherche exhaustive sur `app/`). Les renseigner n'a aucun effet. Seuls existent : logs JSON structurés sur stdout avec `trace_id` (`app/main.py::JsonLogFormatter`) et les sondes HTTP.

---

## 2. Inventaire complet des variables d'environnement

Source de vérité : `boussole/api/app/core/config.py` (classe `Settings`, 63 champs) + `app/modules/ingestion/settings.py` (préfixe `INGESTION_`, 5 champs) + `FORWARDED_ALLOW_IPS`, lue directement dans l'environnement par `app/main.py`.

Légende : **Prod** = doit être positionnée explicitement en production ; **Secret** = ne doit jamais transiter par un fichier committé ni un manifeste en clair (D23, vault).

### 2.1 Environnement et exposition

| Variable | Rôle | Défaut | Prod | Secret |
|---|---|---|---|---|
| `ENV` | `development` \| `staging` \| `production`. **Vocabulaire fermé** : toute autre valeur fait échouer le démarrage | `development` | **Oui** | Non |
| `DEBUG` | Indicateur applicatif | `false` | Recommandé `false` | Non |
| `API_PREFIX` | Préfixe des routes | `/api/v1` | Non | Non |
| `FORWARDED_ALLOW_IPS` | Liste (virgules, pas de CIDR) des proxies de confiance pour `X-Forwarded-For`. Lue **deux fois** : par uvicorn (`--forwarded-allow-ips`) et par l'application | `127.0.0.1` | **Oui** | Non |

> ⚠️ `FORWARDED_ALLOW_IPS` mal réglée n'empêche pas le démarrage mais dégrade le rate limiting : soit tous les anonymes partagent un seul seau de 60 req/min (auto-DoS), soit — avec `*` — l'identité de limitation devient falsifiable par n'importe quel client.

### 2.2 Base de données et files

| Variable | Rôle | Défaut | Prod | Secret |
|---|---|---|---|---|
| `DATABASE_URL` | PostgreSQL, driver `asyncpg` obligatoire | `postgresql+asyncpg://boussole:boussole@localhost:5432/boussole` | **Oui** | **Oui** (mot de passe inclus) |
| `REDIS_PERSISTENT_URL` | Sessions + broker + backend Celery | `redis://localhost:6379/0` | **Oui** | **Oui** si authentifié |
| `REDIS_CACHE_URL` | Cache, rate limiting, quotas | `redis://localhost:6380/0` | **Oui** | **Oui** si authentifié |

### 2.3 Stockage objet

| Variable | Rôle | Défaut | Prod | Secret |
|---|---|---|---|---|
| `STORAGE_BACKEND` | `local` \| `s3`. **`local` fait échouer le démarrage dès `staging`** | `local` | **Oui → `s3`** | Non |
| `STORAGE_LOCAL_PATH` | Racine disque du backend `local` (dev/tests seulement) | `.storage` | Non | Non |
| `S3_ENDPOINT` | Endpoint S3 ; vide ⇒ endpoint AWS par défaut de la région | `http://localhost:9000` | **Oui** | Non |
| `S3_BUCKET` | Bucket. Vide + `STORAGE_BACKEND=s3` ⇒ refus de démarrage | `boussole-dev` | **Oui** | Non |
| `S3_REGION` | Région (UE — D09) | `eu-west-1` | **Oui** | Non |
| `S3_ACCESS_KEY` | Identifiant | `boussole-dev` | **Oui** | **Oui** |
| `S3_SECRET_KEY` | Secret | `boussole-dev-secret` | **Oui** | **Oui** |
| `S3_SSE` | `none` \| `AES256` \| `aws:kms`. **`none` fait échouer le démarrage dès `staging`** | `AES256` | **Oui → `aws:kms`** | Non |
| `S3_KMS_KEY_ID` | Clé KMS UE ; vide ⇒ clé gérée par le fournisseur | `""` | Recommandé | Non |
| `S3_ADDRESSING_STYLE` | `auto` \| `path` \| `virtual`. `auto` ⇒ `path` dès qu'un endpoint explicite est donné | `auto` | Non | Non |
| `S3_CONNECT_TIMEOUT_SECONDS` | Borne réseau botocore | `5.0` | Non | Non |
| `S3_READ_TIMEOUT_SECONDS` | Borne réseau botocore | `30.0` | Non | Non |
| `S3_MAX_ATTEMPTS` | Retries botocore bornés | `3` | Non | Non |

### 2.4 Sécurité, sessions, signature

| Variable | Rôle | Défaut | Prod | Secret |
|---|---|---|---|---|
| `PRIVACY_SIGNING_KEY` | Clé HMAC-SHA256 des liens de téléchargement d'export RGPD | `boussole-dev-privacy-signing` | **Oui — critique** | **Oui** |
| `SESSION_TTL_DAYS` | TTL glissant des sessions | `30` | Non | Non |
| `SESSION_COOKIE_NAME` | Nom du cookie de session | `boussole_session` | Non | Non |
| `CSRF_COOKIE_NAME` | Cookie CSRF double-submit | `boussole_csrf` | Non | Non |
| `CSRF_HEADER_NAME` | En-tête CSRF attendu | `X-CSRF-Token` | Non | Non |
| `LOGIN_RATE_LIMIT` | Tentatives de login par fenêtre | `5` | Non | Non |
| `LOGIN_RATE_WINDOW_SECONDS` | Fenêtre de login | `60` | Non | Non |

> ⚠️ **`PRIVACY_SIGNING_KEY` signe seule l'accès à `GET /privacy/exports/{id}/download`** — une archive contenant l'intégralité des données personnelles d'un compte. Sa valeur par défaut est dans le dépôt, donc publique : laissée en place, n'importe qui ayant lu le code peut forger un lien valide pour un `export_id` deviné.
>
> Depuis la finalisation, `app/core/secrets.py` **refuse le démarrage** hors développement tant que cette valeur (et `S3_SECRET_KEY`) n'a pas été remplacée — côté API comme côté workers, à l'import du module, avant qu'une seule tâche ne soit acceptée. Le remplacement lui-même reste un geste de déploiement (checklist §8), mais il ne peut plus être oublié en silence : le service ne démarre pas.

### 2.5 Providers LLM

| Variable | Rôle | Défaut | Prod | Secret |
|---|---|---|---|---|
| `AI_PROVIDER` | `fake` \| `anthropic`. Le provider réel n'est **jamais** actif implicitement | `fake` | Choix explicite | Non |
| `AI_FALLBACK_PROVIDER` | Second provider (D18). Vide = pas de repli | `""` | Non | Non |
| `ANTHROPIC_API_KEY` | Clé du provider Anthropic | `""` | Si `anthropic` | **Oui** |
| `FALLBACK_LLM_API_KEY` | Clé du provider de repli | `""` | Si utilisé | **Oui** |
| `AI_MODEL_EXTRACT_CV` | Modèle de la tâche `extract_cv` | `claude-sonnet-5` | Non | Non |
| `AI_MODEL_EXTRACT_JOB` | Modèle de `extract_job` (plus gros volume) | `claude-haiku-4-5` | Non | Non |
| `AI_MODEL_EXPLAIN_MATCH` | Modèle de `explain_match` | `claude-haiku-4-5` | Non | Non |
| `AI_MODEL_GENERATE_EMAIL` | Modèle de `generate_email` | `claude-sonnet-5` | Non | Non |
| `AI_MODEL_GENERATE_LETTER` | Modèle de `generate_letter` | `claude-sonnet-5` | Non | Non |
| `AI_MODEL_TAILOR_CV` | Modèle de `tailor_cv` | `claude-sonnet-5` | Non | Non |
| `AI_MODEL_OPTIMIZE_CV` | Modèle de `optimize_cv` | `claude-sonnet-5` | Non | Non |
| `AI_MODEL_DEFAULT` | Garde-fou, tâche hors table | `claude-sonnet-5` | Non | Non |
| `AI_MAX_OUTPUT_TOKENS` | Plafond de tokens de sortie | `8000` | Non | Non |
| `AI_TIMEOUT_SECONDS` | Timeout par appel ; `None` ⇒ cibles p95 par tâche | `None` | Non | Non |
| `AI_MAX_RETRIES` | Retries provider bornés | `3` | Non | Non |
| `AI_RETRY_AFTER_MAX_SECONDS` | Plafond d'attente honorée sur un `Retry-After` 429 | `30.0` | Non | Non |
| `AI_CIRCUIT_BREAKER_THRESHOLD` | Échecs consécutifs avant ouverture du circuit | `5` | Non | Non |
| `AI_CIRCUIT_BREAKER_RESET_SECONDS` | Délai avant essai « demi-ouvert » | `60.0` | Non | Non |
| `AI_STRUCTURED_OUTPUTS` | Sortie JSON contrainte côté provider (dégradation auto vers repair-parse) | `true` | Non | Non |

> Changer un modèle = **nouvelle version de prompt** (08 §7.1). Ce n'est pas un simple réglage d'exploitation.

### 2.6 Embeddings

| Variable | Rôle | Défaut | Prod | Secret |
|---|---|---|---|---|
| `EMBEDDINGS_PROVIDER` | `hashing` (local, déterministe) \| `managed` (squelette **non implémenté** — Q11) | `hashing` | Choix explicite | Non |
| `EMBEDDINGS_FALLBACK_PROVIDER` | Second provider d'embeddings | `""` | Non | Non |
| `EMBEDDINGS_MODEL` | Identifiant de modèle du provider managé | `voyage-3-large` 🟡 | Si `managed` | Non |
| `EMBEDDINGS_DIM` | Dimension produite. **Doit valoir 1024** (colonnes `vector(1024)`) | `1024` | Ne pas changer | Non |
| `EMBEDDINGS_API_KEY` | Clé du provider managé | `""` | Si `managed` | **Oui** |
| `EMBEDDINGS_API_BASE_URL` | Endpoint du provider managé (UE — Q11/Q38) | `""` | Si `managed` | Non |
| `EMBEDDINGS_TIMEOUT_SECONDS` | Timeout par appel | `20.0` | Non | Non |
| `EMBEDDINGS_BATCH_SIZE` | Textes par appel provider | `64` | Non | Non |
| `EMBEDDINGS_BACKFILL_BATCH_SIZE` | Lignes traitées par exécution de `ai.embeddings.backfill_*` | `200` | Voir §5 | Non |

### 2.7 Seuils dépendants des embeddings (Q12 — à calibrer)

| Variable | Rôle | Défaut | Prod | Secret |
|---|---|---|---|---|
| `DEDUP_STAGE2_COSINE_THRESHOLD` | Seuil de fusion de l'étage 2 de dédup. **Sans effet tant que `EMBEDDINGS_PROVIDER=hashing`** (§7.4) | `0.92` | Non | Non |
| `SEARCH_RERANK_ENABLED` | Rerank vectoriel de la recherche hybride | `true` | Non | Non |
| `SEARCH_RERANK_FULLTEXT_WEIGHT` | Poids du rang full-text (Q41) | `0.5` | Non | Non |
| `SEARCH_RERANK_VECTOR_WEIGHT` | Poids du cosinus (Q41) | `0.5` | Non | Non |

### 2.8 Matching, connecteurs, observabilité

| Variable | Rôle | Défaut | Prod | Secret |
|---|---|---|---|---|
| `SCORING_CONFIG_PATH` | Config de scoring versionnée (chemin relatif à `api/`) | `config/scoring-config.json` | Non | Non |
| `FEATURE_SOURCE_FRANCE_TRAVAIL` | Active le connecteur France Travail | `false` | **Voir §8.2** | Non |
| `FEATURE_SOURCE_GREENHOUSE` | Active le connecteur Greenhouse | `false` | **Voir §8.2** | Non |
| `FEATURE_SOURCE_LEVER` | Active le connecteur Lever | `false` | **Voir §8.2** | Non |
| `SENTRY_DSN` | 🟡 **Déclaré, jamais lu par le code** — aucun effet | `""` | Sans effet | **Oui** si un jour branché |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | 🟡 **Déclaré, jamais lu par le code** — aucun effet | `""` | Sans effet | Non |
| `INGESTION_FRANCE_TRAVAIL_CLIENT_ID` | OAuth2 client_credentials France Travail | `""` | Si source active | **Oui** |
| `INGESTION_FRANCE_TRAVAIL_CLIENT_SECRET` | Secret OAuth2 | `""` | Si source active | **Oui** |
| `INGESTION_GREENHOUSE_BOARDS` | `"token:Nom,token2:Nom2"` — boards activés **explicitement** | `""` | Si source active | Non |
| `INGESTION_LEVER_SITES` | Même format | `""` | Si source active | Non |
| `INGESTION_NOMINATIM_BASE_URL` | Géocodage de repli 🟡 (Q14) | `https://nominatim.openstreetmap.org` | À revoir (Q14) | Non |

`BOUSSOLE_TEST_DATABASE_URL` existe également mais concerne **uniquement** la suite d'intégration (`tests/integration/conftest.py`) : elle ne doit jamais être positionnée sur un environnement applicatif, la base ciblée étant tronquée entre chaque test.

---

## 3. Garde-fous de démarrage — ce qui fait volontairement échouer le boot

Ces refus sont **délibérés**. Chacun corrige une perte de données ou une dégradation silencieuse constatée en revue. Ils sont vérifiés par `tests/unit/core/test_startup_guards.py` et `tests/unit/core/test_config_env.py`, dont plusieurs lancent un vrai sous-processus.

### 3.1 `ENV` hors vocabulaire → `ValidationError` pydantic

`Settings.env` est un `Literal["development","staging","production"]`. `ENV=prod`, `ENV=preprod`, `ENV=local` **refusent le démarrage**.

**Pourquoi.** `env` était auparavant une chaîne libre comparée par égalité exacte. `ENV=prod` désactivait donc d'un seul coup, et en silence : le refus du stockage local, l'exigence de chiffrement au repos, le masquage des docs OpenAPI et la garde D22 des seeds. Une faute de frappe dans un manifeste valait désactivation complète de la sécurité.

**Tolérance bornée et assumée** : casse et espaces sont normalisés (`" Production "` → `production`), parce qu'un copier-coller depuis un fichier de secrets ne change pas le *sens* de la valeur. Les alias, eux, restent refusés.

### 3.2 `STORAGE_BACKEND=local` hors `development` → `StorageConfigurationError`

Le seuil est `env != "development"` : **staging est couvert**, pas seulement production.

**Pourquoi.** Le backend `local` écrit sur le disque **du conteneur courant**. Dès que l'API et les workers Celery sont deux processus distincts, le worker écrit l'archive d'export RGPD sur son disque, l'API la relit depuis le sien : tout téléchargement d'export répond 404 et les CV disparaissent au redémarrage. Refuser de démarrer est strictement préférable à perdre des exports en silence. Le seuil a été élargi à staging parce qu'un staging multi-conteneurs perdait exactement les mêmes données sans qu'aucun contrôle ne se déclenche.

**Où le contrôle s'exécute** — trois points, volontairement :
- `app/main.py::create_app` (démarrage API) ;
- **au niveau module** de `app/workers/celery_app.py` : l'exception remonte à l'import, `celery -A app.workers.celery_app worker` s'arrête avant d'avoir accepté une seule tâche ;
- `/readyz`.

> ⚠️ **Ne jamais redéplacer la garde du worker sur `@worker_ready.connect`.** `celery.utils.dispatch.Signal.send` attrape les exceptions des receveurs, les journalise et poursuit ; et `worker_ready` est émis *après* le début de la consommation de la file. C'était un no-op vérifié : un worker en production sur stockage local démarrait normalement.

### 3.3 `S3_SSE=none` hors `development` → `StorageConfigurationError`

**Pourquoi.** Le chiffrement au repos est exigé (D09, 09 §5.6). `none` n'est toléré qu'en dev, où MinIO sans KES ne sait pas chiffrer côté serveur. Cible : `aws:kms` + `S3_KMS_KEY_ID` (clé UE) ; `AES256` (SSE-S3) est le minimum acceptable 🟡.

### 3.4 `STORAGE_BACKEND=s3` sans `S3_BUCKET` → `StorageConfigurationError`

Évite un démarrage nominal suivi d'un `NoSuchBucket` au premier upload de CV, erreur difficile à relier à l'infrastructure.

### 3.5 Backend de stockage inconnu → `StorageConfigurationError`

`check_storage_configuration` refuse tout backend hors `{local, s3}`. En pratique, le `Literal` de pydantic intercepte d'abord la valeur : cette branche protège les appels avec un double de configuration partiel (tests) et un éventuel élargissement futur du type. Elle est donc une ceinture, pas la bretelle.

### 3.6 Ce qui n'est **pas** gardé au démarrage (à surveiller manuellement)

| Point | Statut réel |
|---|---|
| `PRIVACY_SIGNING_KEY` laissée au défaut | 🔴 **Aucun contrôle.** Vérification manuelle obligatoire (§8.1) |
| `S3_ACCESS_KEY` / `S3_SECRET_KEY` laissées aux valeurs MinIO de dev | 🔴 Aucun contrôle ; l'échec n'apparaîtra qu'au premier appel S3 (`/readyz` le verra, §7.1) |
| `DATABASE_URL` pointant sur les identifiants de dev | 🔴 Aucun contrôle |
| Dimension d'embeddings ≠ 1024 | 🟠 Contrôlé, mais **paresseusement** : `check_embedding_dimension` est appelé par `build_embedding_provider`, donc au **premier usage** du provider (ingestion, backfill, recherche), pas au boot. L'erreur est bloquante et bruyante mais arrive tard |
| `EMBEDDINGS_PROVIDER=managed` | 🟠 Se construit si clé + endpoint + modèle sont fournis, puis **échoue à chaque appel** (`ManagedEmbeddingProvider.embed_texts` lève). La fabrique dégrade alors sur `hashing` en journalisant `embedding_provider_fallback_to_hashing` |

---

## 4. Séquence de déploiement

### 4.1 Migrations Alembic

Six révisions, chaînées `0001 → 0006`. Toutes sont appliquées par un unique `upgrade head`.

| Rev | Objet réel |
|---|---|
| `0001_initial` | Schéma complet : exécute `alembic/versions/sql/0001_initial.sql` (copie conforme de `initial-schema.sql`) — extensions `vector`/`pg_trgm`/`unaccent`/`citext`, toutes les tables, enums, CHECK, index, et le trigger `tsv`. Le script est découpé instruction par instruction (asyncpg refuse le multi-commande), en respectant les blocs `$$ … $$` |
| `0002_connector_state` | Table `connector_state` : curseur de fetch incrémental par source (`cursor`, `last_sync_at`, `updated_at`) |
| `0003_absence_counters` | Colonne `connector_state.absence_counters` (jsonb). Les compteurs d'absence du mécanisme d'expiration par disparition du flux vivaient en mémoire du worker : ils ne survivaient ni au redémarrage ni à la rotation des workers, rendant le seuil de 2 réconciliations consécutives inopérant |
| `0004_generation_processing` | Colonnes applicatives de `generated_documents` : `processing_status` (`pending`/`processing`/`ready`/`failed` + CHECK), `error_code`, `anchoring_check` (jsonb), `manually_edited`, `options` (jsonb), et l'index keyset `idx_generated_docs_user_created`. Additif : l'enum SQL `generated_doc_status` n'est pas altéré |
| `0005_privacy_exports` | Table `privacy_exports` (`status` ∈ `pending`/`ready`, `file_key`, `expires_at`, FK `ON DELETE CASCADE`) + index par utilisateur. Écart assumé : `initial-schema.sql` ne prévoyait aucune table pour les demandes d'export |
| `0006_ai_calls` | **N'ajoute pas la table `ai_calls`** (elle vient de 0001). Ajoute la contrainte `ck_ai_calls_status` (`success`/`schema_retry`/`failed`) et l'index partiel `ix_ai_calls_user_id WHERE user_id IS NOT NULL`, nécessaire à la purge RGPD par utilisateur |

**Commande** (depuis `boussole/`) :

```bash
make migrate        # = cd api && alembic -c alembic/alembic.ini upgrade head
```

L'URL vient de `DATABASE_URL` via `alembic/env.py` — elle n'est jamais dans `alembic.ini`.

> **0006 est conçue pour ne pas bloquer les écritures** : `ADD CONSTRAINT … NOT VALID` puis `VALIDATE CONSTRAINT` (scan sous `SHARE UPDATE EXCLUSIVE`), et `CREATE INDEX CONCURRENTLY` dans un `autocommit_block`. `ai_calls` est la table la plus volumineuse du système (≤ 10 k lignes/jour pour `extract_job` seule) ; écrite naïvement, la migration aurait bloqué toute journalisation d'appel IA pendant plusieurs minutes.
>
> 🟡 `CREATE INDEX CONCURRENTLY` via asyncpg dans un `autocommit_block` n'a pas été exercé sur un volume de production. À surveiller au premier passage sur une base chargée : un index laissé `INVALID` par un échec doit être supprimé puis recréé.

### 4.2 Seeds

```bash
make seed           # = cd api && python -m app.seeds
```

Idempotent (`INSERT … ON CONFLICT DO NOTHING`). Contenu : ~10 sections NACE simplifiées, 20 compétences tech + alias, `prompt_versions` v1 (inactives), `sources` (**inactives**).

`make seed-demo` (3 profils synthétiques) **lève une `RuntimeError` si `ENV=production`** (D22). Ne jamais l'exécuter ailleurs qu'en dev/staging.

### 4.3 Ordre de démarrage

1. **PostgreSQL**, **les deux Redis**, **le bucket S3** (créé et accessible) — les trois doivent être sains avant tout le reste ;
2. **Migrations** (`upgrade head`) puis **seeds**, depuis un job éphémère utilisant l'image API ;
3. **API** — refuse de démarrer si la configuration de stockage est invalide (§3) ;
4. **Workers Celery** — même refus, à l'import :

   ```bash
   celery -A app.workers.celery_app worker -Q ingestion,ai,scoring,maintenance --loglevel=info
   ```

5. **Celery beat** — **processus séparé, à provisionner** :

   ```bash
   celery -A app.workers.celery_app beat --loglevel=info
   ```

> ℹ️ Le `docker-compose.dev.yml` porte un service `beat` depuis la finalisation. Il en était absent pendant six jalons : un déploiement calqué sur le compose n'exécutait **aucune** tâche planifiée — ni ingestion, ni expiration d'offres, ni **purge RGPD** (§6). Le commentaire au-dessus du service dit pourquoi il n'est pas optionnel ; ne pas le supprimer.

> ⚠️ **L'image `Dockerfile.api` ne lance pas les migrations.** Sa commande par défaut est uvicorn. Les migrations doivent être un job explicite (le binaire `alembic` est présent dans `/opt/venv/bin`, et `api/alembic` est copié dans l'image).

> ⚠️ **Exactement un processus beat.** Deux beats sur le même broker dupliquent chaque tâche planifiée — y compris les purges et les backfills.

---

## 5. ⚠️ Opérations post-déploiement obligatoires

### 5.1 Backfill **forcé** des embeddings après M6 — bloquant

Le jalon M6 a changé la **tokenisation** du provider d'embeddings local : `_WORD_RE` est passée de `[0-9a-z]+` à `\.?[0-9a-z]+[+#]*` pour que `C`, `C++`, `C#` (et `.NET` / `NET`) cessent de produire des jetons identiques. `HASHING_MODEL_VERSION` est passée de `hashing-ngram-v1` à `hashing-ngram-v2`.

**Conséquence : tous les vecteurs calculés avant M6 sont incomparables avec ceux calculés après.** Ils ne sont pas « un peu décalés » — ils ne vivent plus dans le même espace. Sont affectés : `job_postings.embedding`, `profiles.embedding`, `preference_titles.embedding`, `skills.embedding`. Tant que le backfill forcé n'est pas fait, la similarité d'intitulé (15 % du poids de matching), le crédit « compétence proche » et le rerank de recherche mélangent deux générations de vecteurs.

**Aucune colonne ne stocke la version de modèle** (`embedding_model_version` n'existe pas au schéma) : rien ne détecte cette incohérence automatiquement. C'est une opération manuelle.

#### Commandes

Les tâches sont enregistrées sous les noms `ai.embeddings.backfill_jobs`, `ai.embeddings.backfill_profiles`, `ai.embeddings.backfill_skills`, et acceptent `(batch: int | None = None, force: bool = False)`.

```bash
# Depuis un conteneur portant l'image API, avec l'environnement de production.
celery -A app.workers.celery_app call ai.embeddings.backfill_jobs     --kwargs '{"force": true, "batch": 100000}'
celery -A app.workers.celery_app call ai.embeddings.backfill_profiles --kwargs '{"force": true, "batch": 100000}'
celery -A app.workers.celery_app call ai.embeddings.backfill_skills   --kwargs '{"force": true, "batch": 100000}'
```

Forme équivalente par le client Python, si l'on préfère lire le rapport :

```bash
python -c "from app.workers.embedding_tasks import backfill_jobs; \
print(backfill_jobs.delay(batch=100000, force=True))"
```

#### ⚠️ Piège vérifié : `force=True` **ne progresse pas** entre deux exécutions

Les requêtes de sélection (`_job_targets`, `_profile_targets`, `_preference_title_targets`, `_skill_targets` dans `app/workers/embedding_tasks.py`) filtrent `embedding IS NULL` **uniquement quand `force=False`**. Avec `force=True`, il ne reste qu'un `LIMIT batch` — sans curseur, sans exclusion des lignes déjà retraitées. Les offres sont en plus triées `last_seen_at DESC`.

**Rejouer `force=True` avec un `batch` inférieur au volume retraite donc indéfiniment les mêmes N lignes** et ne couvre jamais le corpus.

Deux procédures correctes, au choix :

**A — un seul passage, `batch` couvrant tout le corpus.** Mesurer d'abord :

```sql
SELECT count(*) FROM job_postings WHERE status = 'active';
SELECT count(*) FROM profiles WHERE status = 'validated';
SELECT count(*) FROM preference_titles;
SELECT count(*) FROM skills;
```

puis passer un `batch` strictement supérieur au plus grand de ces comptes. À réserver aux volumes modestes : tout le lot est chargé en mémoire du worker et persisté par `UPDATE` ligne à ligne.

**B — invalidation SQL puis rattrapage progressif** (recommandée sur volume réel) :

```sql
UPDATE job_postings     SET embedding = NULL WHERE status = 'active';
UPDATE profiles         SET embedding = NULL WHERE status = 'validated';
UPDATE preference_titles SET embedding = NULL;
UPDATE skills           SET embedding = NULL;
```

Puis rejouer les trois tâches **sans `force`**, autant de fois que nécessaire : le filtre `embedding IS NULL` fait avancer le lot naturellement, chaque exécution est idempotente, et le beat quotidien (§6) finit le travail seul. Vérifier la convergence :

```sql
SELECT count(*) FROM job_postings WHERE status = 'active' AND embedding IS NULL;
```

Pendant la fenêtre où des vecteurs sont NULL, la dégradation est explicite et documentée : `title_similarity` reste inconnue (`k=0`), le crédit « proche » est désactivé, le rerank est neutre. Aucune erreur utilisateur, mais des scores moins informés.

### 5.2 Vérifier que beat tourne

Voir §6 — et §7.3 pour la conséquence RGPD s'il ne tourne pas.

### 5.3 Vérifier `/readyz` sur **chaque** instance API

`/readyz` sonde le stockage objet pour de vrai (`HeadBucket`). Une instance dont les identifiants S3 sont mal injectés le dira ; une instance non sondée ne le dira pas.

### 5.4 Ce qu'il **ne faut pas** faire après déploiement

- Ne pas exécuter `make seed-demo` (refusé en production, mais l'intention est déjà une erreur) ;
- Ne pas exécuter `alembic downgrade` sur `0001` : sa fonction `downgrade()` fait `DROP SCHEMA public CASCADE` et est explicitement marquée **DEV-ONLY** (voir §9) ;
- Ne pas activer un `FEATURE_SOURCE_*` sans la validation de §8.2.

---

## 6. Planification beat réelle

Lue dans `app/workers/celery_app.py` (`timezone="UTC"`, `enable_utc=True` — **toutes les heures ci-dessous sont UTC**).

| Entrée | Tâche | Horaire (UTC) | Ce qu'elle fait | Ce qui casse si elle ne tourne pas |
|---|---|---|---|---|
| `embeddings-backfill-jobs` | `ai.embeddings.backfill_jobs` | 02:10 quotidien | Vecteurs des offres actives sans embedding | Trous de vecteurs persistants après une panne du provider : `title_similarity` reste inconnue, rerank neutre |
| `embeddings-backfill-profiles` | `ai.embeddings.backfill_profiles` | 02:25 quotidien | Vecteurs des profils validés **et** des intitulés cibles | Un changement d'intitulés cibles via `PUT /preferences` n'est jamais reflété (voir 🟡 ci-dessous) |
| `embeddings-backfill-skills` | `ai.embeddings.backfill_skills` | 02:40 quotidien | Vecteurs des libellés de compétences | Crédit « compétence proche » (06 §2.1) inopérant |
| `ingestion-sync-france-travail` | `ingestion.sync_source("france-travail")` | toutes les 2 h, à :00 | Cycle incrémental : fetch → normalisation → dédup → avance du curseur (uniquement après succès complet) | Fraîcheur des offres FT dégradée |
| `ingestion-reconcile-france-travail` | `ingestion.reconcile("france-travail")` | 03:00 quotidien | Réconciliation complète + détection d'expiration par disparition du flux | Offres mortes conservées comme actives |
| `ingestion-reconcile-greenhouse` | `ingestion.reconcile("greenhouse")` | toutes les 6 h, à :15 | Fetch complet des boards Greenhouse déclarés + expiration par absence | Idem, côté Greenhouse. **Aucun `sync_source` n'est planifié pour les ATS** : la réconciliation est leur seul mode d'alimentation |
| `ingestion-reconcile-lever` | `ingestion.reconcile("lever")` | toutes les 6 h, à :30 | Idem, sites Lever | Idem |
| `maintenance-expire-jobs` | `maintenance.expire_jobs` | 03:45 quotidien | Expiration par `expires_at` dépassé | Offres périmées encore proposées et scorées |
| `maintenance-purge-due-accounts` | `maintenance.purge_due_accounts` | **04:15 quotidien** | **Purge RGPD** des comptes dont `purge_after` est échu | 🔴 **Voir ci-dessous** |
| `maintenance-purge-expired-exports` | `maintenance.purge_expired_exports` | 04:45 quotidien | Suppression des archives d'export dont le lien signé a expiré (objet **et** ligne) | 🔴 Des dumps personnels complets survivent sans finalité au-delà de leurs 7 jours (D09, minimisation) |
| `maintenance-check-purge-backlog` | `maintenance.check_purge_backlog` | 05:15 quotidien | **Surveillance** : journalise en ERROR toute demande échue depuis plus de 26 h et toujours `pending` ; journalise `purge_backlog_ok` sinon | Une purge qui échoue en boucle redevient invisible — c'est l'état d'avant (voir ci-dessous) |
| `maintenance-purge-ai-calls` | `maintenance.purge_ai_calls` | 05:30 quotidien | **Rétention 13 mois** du journal `ai_calls`, par lots de 5 000 bornés à 20 lots | La rétention annoncée n'est pas tenue, et la table qui croît le plus vite ne décroît jamais |

Les tâches d'ingestion planifiées sur une source dont le `FEATURE_SOURCE_*` est `false` sont des **no-op logués** — c'est le comportement attendu tant que §8.2 n'est pas levé.

### 🔴 Si `maintenance.purge_due_accounts` ne tourne pas

C'est la conséquence la plus grave d'un beat absent. `DELETE /account` ne fait qu'un **soft delete** et pose `deletion_requests.purge_after = now + 30 jours` (`PURGE_DELAY_DAYS = 30`). La suppression physique — données de tous les modules du registre, objets stockés, anonymisation de `users`/`audit_log`/`ai_calls` — est **entièrement portée par cette tâche beat**. Rien d'autre ne la déclenche : ni l'API, ni un trigger SQL, ni un `ON DELETE` en cascade.

Sans beat, l'engagement « suppression effective ≤ 30 jours » (D09, RM-T) est rompu **en silence** : l'utilisateur a reçu son 204, la demande reste `pending`, les données restent.

### Surveillance : `maintenance.check_purge_backlog`

Depuis le lot post-M6 n° 1, la requête de §7.3 est exécutée automatiquement à 05:15 — une heure après la purge, dont elle vérifie l'effet. Ce qu'elle trouve encore `pending` au-delà de 26 heures est ce que la purge n'a pas su traiter : un module du registre qui lève à chaque passage, par exemple, laisse la demande en attente indéfiniment, avec un `account_purge_partial` par tentative et rien au-dessus.

**Deux limites, à connaître avant de s'y fier.**

1. **Un beat arrêté reste invisible de l'intérieur.** La surveillance est elle-même une tâche beat : si l'ordonnanceur meurt, ni la purge ni son contrôle ne tournent, et le silence est total. D'où le battement `purge_backlog_ok` journalisé même quand tout va bien — **c'est son absence qu'il faut alerter**, pas seulement la présence d'un ERROR. Une alerte « aucun `purge_backlog_ok` depuis 26 h » est la seule qui attrape ce cas.
2. **La marge de 26 h autorise une purge au 31ᵉ jour.** `purge_after` est J+30 et la purge tourne une fois par jour : l'engagement est tenu à un cycle près par construction. La surveillance rend ce dépassement visible ; elle ne le corrige pas. Le fond se règle en posant `purge_after` à J+29 — modification de D09, non faite.

### 🟡 Trou connu — préférences modifiées sans re-validation du profil

Documenté en tête de `app/workers/embedding_tasks.py`. `profiles.embedding` agrège les intitulés cibles ; un `PUT /preferences` ne re-valide pas le profil et n'enfile donc pas `ai.embeddings.embed_profile`. Le vecteur agrégé reste périmé. **Atténuation en place** : `PUT /preferences` remplace les `preference_titles` en bloc, les nouvelles lignes naissent `embedding NULL` et sont rattrapées par le beat de 02:25 sous 24 h — et c'est ce vecteur *par intitulé* que le moteur utilise (max des cosinus, 06 §2.3). La dimension métier converge donc, mais avec **jusqu'à 24 h de latence** après un changement de préférences.

---

## 7. Exploitation courante

### 7.1 Sondes

**`GET /healthz`** — liveness. Retourne `{"status":"ok"}` inconditionnellement, sans toucher aucune dépendance. À utiliser pour le redémarrage de conteneur, **jamais** pour le routage de trafic.

**`GET /readyz`** — readiness. Quatre contrôles, tous réels :

| Clé | Ce qui est réellement fait |
|---|---|
| `database` | `SELECT 1` sur le moteur applicatif |
| `redis_persistent` | `PING` |
| `redis_cache` | `PING` |
| `storage` | `check_storage_configuration()` **puis** une sonde de joignabilité : `HeadBucket` en S3 (ou contrôle de racine en local), exécutée dans un threadpool (boto3 est bloquant) et bornée à `READYZ_STORAGE_TIMEOUT_SECONDS = 3.0` s |

Tout vert → `200 {"status":"ready","checks":{…}}`. Sinon → `503 problem+json` `not_ready`, avec la liste des dépendances en défaut.

À savoir :
- la sonde stockage a été ajoutée parce que la précédente ne relisait que la **configuration** : un bucket supprimé, une clé révoquée ou un MinIO éteint laissaient `/readyz` vert pendant que tous les imports de CV et exports RGPD échouaient ;
- le timeout de 3 s est **fail-closed** mais n'interrompt pas le thread boto3 sous-jacent : sur un backend lent, des sondes peuvent s'accumuler en arrière-plan. À surveiller si `/readyz` est appelée agressivement ;
- `/readyz` **ne vérifie ni le broker Celery côté worker, ni la présence de beat, ni le provider LLM**. Une application « ready » peut n'avoir aucun worker.

Les deux sondes sont exclues du rate limiting et du schéma OpenAPI.

### 7.2 Points de surveillance

| À surveiller | Comment | Seuil / réaction |
|---|---|---|
| `/readyz` par instance | HTTP | 503 → retirer du pool |
| Profondeur des 4 files Celery | Redis persistant (`LLEN` par file) | `ai` qui gonfle = provider en difficulté ; `maintenance` qui gonfle = purges en retard |
| Présence du processus beat | Superviseur | 🔴 critique — §6 |
| Journaux `embedding_provider_circuit_open`, `embedding_provider_fallback_to_hashing` | logs JSON | Le provider d'embeddings configuré n'est pas celui réellement utilisé |
| Journaux `rate_limit_unavailable`, `rate_limit_session_lookup_failed` | logs JSON | Redis cache ou persistant en difficulté ; le rate limiting est **fail-open** (assumé, D18) |
| `storage_misconfigured`, `storage_unreachable`, `storage_probe_timeout` | logs JSON | Précèdent immédiatement les 404 d'export |
| `ai_calls.status = 'schema_retry'` | SQL | > 5 % sur 1 h = dérive de prompt ou de modèle (08 §7.3) |
| `deletion_requests` échues non purgées | SQL, §7.3 | 🔴 critique |
| Croissance de `ai_calls` | SQL | **Aucune purge par âge n'existe** — §7.4 |

Requête de suivi des appels IA :

```sql
SELECT task, status, count(*)
FROM ai_calls
WHERE created_at > now() - interval '1 hour'
GROUP BY task, status;
```

### 7.3 Que faire si la purge RGPD prend du retard

**Détection automatique** : `maintenance.check_purge_backlog` exécute ce contrôle chaque jour à 05:15 (§6) et journalise `purge_backlog_detected` en **ERROR** avec le nombre de demandes et l'âge de la plus ancienne. À câbler sur deux alertes, pas une :

| Alerte | Condition | Ce qu'elle attrape |
|---|---|---|
| Retard de purge | un log `purge_backlog_detected` | Une purge qui échoue en boucle |
| **Absence de battement** | aucun log `purge_backlog_ok` ni `purge_backlog_detected` depuis 26 h | **Un ordonnanceur arrêté** — que la première alerte ne peut pas voir, puisqu'elle est elle-même une tâche beat |

**Détection manuelle**, pour instruire une alerte ou vérifier après coup :

```sql
SELECT id, user_id, purge_after, now() - purge_after AS retard
FROM deletion_requests
WHERE status = 'pending' AND purge_after <= now()
ORDER BY purge_after;
```

Toute ligne dont le retard dépasse ~26 h est un dépassement de l'engagement des 30 jours. En deçà, c'est l'attente normale du prochain passage quotidien.

**Marche à suivre** :

1. **Vérifier que beat tourne** et qu'il n'y en a qu'un. C'est la cause la plus fréquente et la plus silencieuse.
2. **Vérifier qu'un worker consomme la file `maintenance`.** Un worker démarré avec `-Q ingestion,ai` uniquement laisse les purges en file indéfiniment.
3. **Déclencher la purge à la main**, sans attendre 04:15 :

   ```bash
   celery -A app.workers.celery_app call maintenance.purge_due_accounts
   ```

   La tâche est **idempotente** : les demandes déjà `purged` ne sont pas resélectionnées.
4. **Lire le compte rendu.** La tâche retourne une liste d'objets `{deletion_id, purged, failed_modules}`. Un `purged: false` avec des `failed_modules` non vides signale une purge **partielle** : la demande reste `pending` et sera retentée au passage suivant. Le module en échec est nommé — c'est lui qu'il faut instruire.
5. **Cause fréquente d'échec partiel : le stockage objet.** `S3ObjectStorage.delete` remonte désormais `NoSuchBucket` / `AccessDenied` en `StorageConfigurationError` au lieu de les avaler. C'est délibéré : ces codes avaient été traduits en « objet absent », et la purge rapportait un **succès complet en n'ayant rien supprimé**. Un échec bruyant ici veut dire droits IAM ou bucket — pas données manquantes.
6. **Vérifier l'effet, pas seulement le statut.** Le test d'intégration `test_privacy_purge.py` inventorie les tables via `information_schema` et suit les clés étrangères transitivement ; en production, le contrôle équivalent doit être fait à la main sur le `user_id` concerné avant de clore l'incident.
7. **Ne jamais marquer une demande `purged` manuellement en base** pour éteindre l'alerte. Le statut est le seul témoin de l'obligation.

Le ménage des archives d'export (`maintenance.purge_expired_exports`, 04:45) suit exactement la même logique et se relance de la même façon.

### 7.4 Points d'exploitation à connaître

- **`ai_calls` est bornée depuis le lot post-M6 n° 1.** La rétention de 13 mois (11 §3) est appliquée par `maintenance.purge_ai_calls` (05:30). Elle était jusque-là documentée et non implémentée : la table qui croît le plus vite du système ne décroissait jamais, et la durée de conservation annoncée n'était tenue par rien. Deux choses à savoir pour l'exploiter :
  - la suppression est **bornée** — lots de 5 000, 20 lots maximum par exécution. Un `DELETE` global verrouillerait la table, donc l'écriture du journal, donc les appels IA en cours. Le premier passage après une longue période sans rétention journalisera `ai_calls_retention_truncated` et reprendra le lendemain ; c'est normal, et c'est visible exprès ;
  - à ne pas confondre avec la purge RGPD **par utilisateur**, qui est une *anonymisation* (`user_id → NULL`) et jamais une suppression : les métadonnées agrégées de coût et de latence doivent survivre à la suppression d'un compte.
- **La dédup étage 2 est neutralisée** tant que `EMBEDDINGS_PROVIDER` n'est pas `managed` : `_stage2_threshold()` retourne `STAGE2_DISABLED_THRESHOLD = 1.5`, inatteignable. Seul l'étage 1 (hash exact) déduplique. C'est délibéré (§ M6 a mesuré des fusions d'offres réellement distinctes à 0,955 et 1,0000 avec les vecteurs lexicaux ; la fusion est irréversible pour l'utilisateur). Ne pas « réactiver » en baissant `DEDUP_STAGE2_COSINE_THRESHOLD` : le seuil n'est simplement pas consulté.
- **Le rerank de recherche est local à la page** 🟡 : il réordonne à l'intérieur d'une page sans altérer le curseur keyset, donc sans doublon ni saut, mais une offre ne « remonte » pas d'une page à l'autre.
- **Le lien d'export RGPD est un HMAC applicatif**, pas encore un pré-signé S3 (`app/modules/privacy/signing.py`, marqué stub 🟡). D'où la criticité de `PRIVACY_SIGNING_KEY`.
- **L'idempotence de `POST /applications` est en mémoire de processus** 🟡 : elle ne survit ni au redémarrage ni au multi-instance.
- **Aucun verrou anti-chevauchement d'ingestion** (`ingestion:lock:{slug}`) ni circuit breaker par source 🟡 — documenté comme non implémenté en tête de `app/workers/ingestion_tasks.py`. Deux cycles concurrents sur la même source sont possibles si un cycle dépasse son intervalle.

---

## 8. Checklist « avant toute mise en production »

### 8.1 Technique — vérifiable, opposable, à cocher

| # | Contrôle | Comment vérifier |
|---|---|---|
| T1 | `ENV=production` (valeur exacte, pas d'alias) | L'API démarre ; sinon `ValidationError` |
| T2 | `STORAGE_BACKEND=s3`, `S3_BUCKET` renseigné, bucket existant | API et worker démarrent ; `/readyz` → `storage: true` |
| T3 | `S3_SSE=aws:kms` + `S3_KMS_KEY_ID` (clé UE) | Démarrage ; `AES256` accepté mais dégradé 🟡 |
| T4 | 🔴 `PRIVACY_SIGNING_KEY` **remplacée** par une valeur aléatoire longue, issue du vault | **Aucun garde-fou — vérification manuelle obligatoire.** Comparer avec `boussole-dev-privacy-signing` |
| T5 | `DATABASE_URL`, `REDIS_*_URL`, `S3_ACCESS_KEY`/`S3_SECRET_KEY` ne sont plus les valeurs de dev | Inspection du secret injecté |
| T6 | Les deux Redis sont bien **deux instances** aux politiques distinctes (AOF/noeviction vs LRU) | Configuration hébergeur (Q40) |
| T7 | `FORWARDED_ALLOW_IPS` = adresse(s) réelle(s) du proxy front, **jamais `*`** | Variable du conteneur API |
| T8 | `alembic upgrade head` appliqué → révision courante `0006` | `alembic current` |
| T9 | `make seed` exécuté ; `make seed-demo` **non** exécuté | Contenu de `sectors`/`skills`/`sources` |
| T10 | 🔴 **Un** processus `celery beat` provisionné et actif | Superviseur + apparition des tâches planifiées dans les logs |
| T11 | Workers consommant les **quatre** files (`-Q ingestion,ai,scoring,maintenance`) | Ligne de commande du worker |
| T12 | 🔴 **Backfill forcé des embeddings exécuté** (§5.1) et convergé | `SELECT count(*) … WHERE embedding IS NULL` |
| T13 | `/readyz` vert sur **chaque** instance API | Sonde HTTP |
| T14 | Sauvegardes PITR actives, rétention 30 j alignée sur la fenêtre de purge, **restauration testée** (D19) | Console hébergeur + exercice de restauration |
| T15 | Supervision en place sur : `purge_backlog_detected`, **absence de `purge_backlog_ok` depuis 26 h** (§7.3), profondeur des files, présence de beat | Alertes créées sur les deux conditions, pas seulement la première |
| T16 | Décision consciente sur `AI_PROVIDER` et `EMBEDDINGS_PROVIDER` ; si `fake`/`hashing`, les limites de §7.4 sont acceptées et documentées | Configuration + note d'exploitation |
| T17 | Conscience que `SENTRY_DSN` / `OTEL_EXPORTER_OTLP_ENDPOINT` **n'ont aucun effet** ; l'observabilité repose sur les logs stdout | — |
| T18 | Conscience qu'aucun e-mail transactionnel n'est envoyé et qu'aucun antivirus ne scanne les uploads | — |
| T19 | Rotation prévue de `PRIVACY_SIGNING_KEY` — noter qu'une rotation **invalide immédiatement les liens d'export en cours** | Procédure écrite |
| T20 | Suites vertes sur le commit déployé : `make lint`, `make typecheck`, `make test`, `make test-integration` | CI |

### 8.2 Juridique et conformité — **rien n'est tranché ici**

Ces points ne sont **pas** des tâches techniques et ce runbook **ne les arbitre pas**. Ils conditionnent la mise en production au même titre que la checklist technique, et relèvent des décideurs désignés dans [17-open-questions.md](17-open-questions.md).

| # | Point | Question ouverte | Décideur désigné (17) |
|---|---|---|---|
| J1 | **Sources d'offres — France Travail.** Conditions exactes d'utilisation de l'API (quota, mention obligatoire, restrictions de réutilisation). Le connecteur est développé et **derrière `FEATURE_SOURCE_FRANCE_TRAVAIL=false`** ; l'activation était prévue « après signature/validation » | **Q2** | Juridique + Data Eng |
| J2 | **Sources d'offres — Greenhouse / Lever.** L'agrégation des flux publics par entreprise nécessite-t-elle un accord par employeur ? Hypothèse en attente : activation entreprise par entreprise après vérification des ToS de chaque board. Les boards sont déclarés explicitement (`INGESTION_GREENHOUSE_BOARDS`, `INGESTION_LEVER_SITES`) — aucune découverte automatique | **Q3** | Juridique |
| J3 | **AI Act.** Boussole relève-t-il des systèmes à haut risque de l'annexe III (emploi) ? La conception suit les obligations haut-risque par précaution, **sans auto-classification** | **Q1** | Conseil juridique + CPO |
| J4 | **Art. 22 RGPD** (décision individuelle automatisée) appliqué au score — analyse à formaliser avec Q1 | **Q37** | Juridique |
| J5 | **Localisation UE des providers LLM** : traitement et non-entraînement contractuels. `AI_PROVIDER=fake` par défaut ; l'activation d'un provider réel était explicitement conditionnée à cette résolution | **Q4** | Security/Privacy Eng |
| J6 | **SCC + TIA** si le provider LLM traite hors UE (complète Q4) | **Q38** | Privacy |
| J7 | **Provider d'embeddings** : modèle, dimension, **hébergement UE**. `EMBEDDINGS_PROVIDER=managed` reste un squelette qui ne nomme aucun fournisseur et n'affirme aucune conformité — délibérément | **Q11** | ML Eng |
| J8 | **Géocodage** : Nominatim self-hosted vs API commerciale, et conformité associée. Le défaut pointe aujourd'hui sur l'instance publique OpenStreetMap 🟡 | **Q14** | DevOps |
| J9 | **DPO désigné** dès le MVP ? | **Q5** | CPO |
| J10 | **DPIA signée** — critère de sortie explicite du jalon M5 (15 §2) | — | Privacy + CPO |
| J11 | **Analytics** : base légale (consentement vs intérêt légitime) | **Q49** | DPO |

> La règle d'exploitation est simple et ne demande aucun arbitrage : **tant que J1/J2 ne sont pas levés par leurs décideurs, les `FEATURE_SOURCE_*` restent `false`** — c'est l'état par défaut du code. Tant que J5/J6 ne sont pas levés, `AI_PROVIDER` reste `fake`. Le code a été écrit pour que l'inaction soit l'option sûre.

---

## 9. Restauration et rollback

### 9.1 Base de données — **par restauration, jamais par `downgrade`**

**`alembic downgrade` vers `0001` exécute `DROP SCHEMA public CASCADE`** : la fonction `downgrade()` de `0001_initial` est explicitement marquée **DEV-ONLY** et détruit tout le schéma, données comprises. Elle ne doit jamais être exécutée en production.

Les révisions `0002` à `0006` ont des `downgrade()` propres et ciblés (drop de table, de colonne, d'index, de contrainte). Un retour de `0006` vers `0005` est techniquement sûr — mais **perd la contrainte `ck_ai_calls_status` et l'index de purge**, avec pour effet secondaire une purge RGPD par utilisateur qui scanne toute la table `ai_calls`.

Procédure de retour arrière sur incident de données :

1. **Arrêter les écritures** : couper le trafic API, arrêter les workers **et beat** (sinon une purge ou une ingestion écrit pendant la restauration) ;
2. **Restaurer par PITR** au point antérieur à l'incident (D19 : RPO 1 h / RTO 4 h 🟡, rétention 30 j alignée sur la fenêtre de purge RGPD) ;
3. **Redéployer l'image applicative correspondant à la révision Alembic restaurée** — c'est le point le plus facile à rater : une image `0006` sur une base restaurée à `0005` ne démarre pas correctement, et l'inverse écrit dans des colonnes inexistantes ;
4. **Rejouer les backfills d'embeddings** (§5.1) si la restauration ramène des vecteurs antérieurs au changement de tokenisation ;
5. Redémarrer dans l'ordre de §4.3.

> ⚠️ **Une restauration PITR peut ressusciter des comptes déjà purgés.** Après toute restauration, rejouer `maintenance.purge_due_accounts` et vérifier les `deletion_requests` échues (§7.3) : la promesse des 30 jours court toujours.

### 9.2 Images applicatives

- **API et workers partagent la même image** (`infra/Dockerfile.api`, multi-stage, exécution non-root sous `boussole`). Un rollback d'image doit être appliqué **aux deux**, à la même version : une API et un worker de versions différentes se partagent la même base et le même broker.
- Déployer par **tag immuable**, jamais `latest` : le rollback consiste à re-pointer le tag précédent.
- **Le rollback d'image ne défait pas une migration.** Les migrations `0002`–`0006` sont additives : une image N-1 tourne sur un schéma N sans erreur dans le cas général (colonnes ignorées). L'inverse est faux. **Règle : migrer en avant, puis déployer ; rollback d'image seul si possible, restauration de base seulement si le schéma est en cause.**
- `Dockerfile.web` construit le front séparément ; il est indépendant du schéma et se rollback seul.
- Après tout rollback : `/readyz` sur chaque instance, présence de beat, et §7.3.

### 9.3 Objets stockés

Le compose de dev active le versionnement du bucket MinIO (`mc version enable`). **Faire de même en production** : c'est le seul filet contre une suppression d'objet erronée par la purge, celle-ci étant conçue pour être irréversible.

---

## 10. Références

- Configuration : `boussole/api/app/core/config.py`, `boussole/.env.example`
- Garde-fous : `boussole/api/app/core/storage.py`, `boussole/api/app/main.py`, `boussole/api/app/workers/celery_app.py`
- Planification : `boussole/api/app/workers/celery_app.py` (`beat_schedule`)
- Backfill embeddings : `boussole/api/app/workers/embedding_tasks.py`, `boussole/api/app/ai/embeddings/`
- Purge RGPD : `boussole/api/app/modules/privacy/purge_runner.py`, `boussole/api/app/workers/privacy_tasks.py`
- Migrations : `boussole/api/alembic/versions/`
- Infra : `boussole/infra/docker-compose.dev.yml`, `boussole/infra/Dockerfile.api`, `.github/workflows/boussole-ci.yml`
- Tests : `boussole/api/tests/integration/README.md`
- État du MVP : [19-mvp-status.md](19-mvp-status.md)
- Questions ouvertes : [17-open-questions.md](17-open-questions.md) — décisions : [decisions.md](decisions.md)
