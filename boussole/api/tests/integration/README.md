# Tests d'intégration — PostgreSQL réel

## Pourquoi cette suite existe

La suite unitaire (`tests/unit`, ~750 tests) n'exerce **jamais** de base de
données : elle substitue des repositories en mémoire, ou se contente de
compiler du SQL vers le dialecte PostgreSQL. C'est ce qui la rend rapide — et
c'est aussi ce qui a laissé passer deux bugs critiques.

### Bug 1 — colonnes `datetime` sans fuseau → 500 sur toute pagination par date

Les colonnes horodatées étaient mappées `TIMESTAMP WITHOUT TIME ZONE` alors que
le schéma n'utilise que `timestamptz`. asyncpg refuse alors tout bind d'un
`datetime` *aware* — or le curseur keyset de `GET /jobs` (page 2) et le seuil
`posted_since` en envoient un. Toute pagination par date répondait 500 en
production.

Invisible en unitaire : le repository en mémoire compare des `datetime` Python,
et `test_search_sql.py` ne fait que **compiler** la requête sans jamais
l'envoyer à un serveur.

→ Couvert par `test_jobs_search_pagination.py`.

### Bug 2 — purge RGPD incomplète (`jobs.purge_user` était un stub)

Le module `jobs` ne supprimait pas les `saved_jobs` d'un compte purgé : des
données personnelles survivaient à l'exercice du droit à l'effacement. Les
tests unitaires du registre vérifiaient que chaque module était **appelé** ;
aucun ne vérifiait l'**effet** en base.

→ Couvert par `test_privacy_purge.py`, qui inventorie les tables réelles via
`information_schema` et échoue dès qu'une table portant une colonne `user_id`
conserve la moindre ligne du compte purgé. Aucune liste en dur : une future
table personnelle oubliée dans le registre fera tomber ce test le jour de sa
migration.

## Ce qui est couvert

| Fichier | Ce que seule une vraie base peut prouver |
|---|---|
| `test_jobs_search_pagination.py` | keyset `(last_seen_at, id)` page 2, égalités de dates, `posted_since`, tri `relevance` avec rangs `ts_rank_cd` ex æquo, curseur incohérent → 422 |
| `test_jobs_salary_filter.py` | annualisation SQL des périodes `month`/`day`/`hour`, offres sans salaire incluses (Q32), CHECK `salary_period` |
| `test_jobs_fulltext_trigger.py` | trigger `tsv` (poids A/B/C, `unaccent`, config `french`/`english`), `websearch_to_tsquery`, recalcul à l'UPDATE |
| `test_ingestion_dedup.py` | dédup étage 1 réelle, `dedup_hash` UNIQUE, `(source_id, external_ref)` UNIQUE, `original_url` NOT NULL, SAVEPOINT par item |
| `test_privacy_purge.py` | purge RGPD de bout en bout + inventaire `information_schema`, anonymisation `users`/`audit_log`/`ai_calls`, suppression des objets stockés, idempotence |
| `test_privacy_export.py` | export art. 20 de bout en bout : demande → archive assemblée par le vrai registre → relecture par lien signé → purge des archives expirées |
| `test_sql_constraints.py` | CHECK (`exported ⇒ validated_at`, taille CV, bornes de score, dates d'expérience), `citext`, enums, cascades `ON DELETE` |

## Comment la lancer

Ces tests portent le marqueur `integration` et sont **exclus par défaut**
(`addopts = -m "not integration"` dans `pyproject.toml`) : `pytest` et
`make test` restent rapides et sans Docker.

```bash
make test-integration                     # depuis boussole/
pytest tests/integration -m integration   # depuis boussole/api
```

Deux façons de fournir la base :

1. **par défaut — conteneur éphémère** : `testcontainers` démarre
   `pgvector/pgvector:pg16`, applique `alembic upgrade head`, puis détruit le
   conteneur en fin de session. Docker absent ou injoignable → la suite est
   `skip`ée avec un message explicite (jamais une erreur cryptique) ;
2. **base fournie** : `BOUSSOLE_TEST_DATABASE_URL` court-circuite
   testcontainers.

   ```bash
   BOUSSOLE_TEST_DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/boussole_test" \
     pytest tests/integration -m integration
   ```

   ⚠️ La base est **TRONQUÉE entre chaque test** (`TRUNCATE … RESTART IDENTITY
   CASCADE`) : n'y pointez jamais autre chose qu'une base jetable. Ce mode sert
   la CI (service PostgreSQL du job) et les postes sans Docker.

Dans les deux cas le schéma vient des **migrations Alembic réelles**, jamais
d'un `Base.metadata.create_all` : trigger `tsv`, CHECK, FK `ON DELETE` et
extensions (`vector`, `pg_trgm`, `unaccent`, `citext`) font partie de ce qui
est testé.

## Périmètre et hypothèses 🟡

- PostgreSQL est réel ; **Redis et le stockage objet ne le sont pas** :
  fakeredis (sessions, rate limiting, quotas) et `LocalDiskStorage` sur
  répertoire temporaire. Aucune des régressions visées ne vit dans ces deux
  dépendances.
- Le worker Celery n'est pas démarré : les tâches (`build_export`,
  `purge_due_accounts`) sont appelées directement, comme le fait le worker.
- Un test est marqué `xfail(strict=True)` sur une **anomalie réelle constatée
  ici** (`test_jobs_fulltext_trigger.py`) : le trigger désaccentue le texte
  indexé mais la requête ne l'est pas, si bien qu'une recherche saisie avec
  accents (« développeur ») ne remonte rien. Le test devient vert dès le
  correctif — retirer alors le `xfail`.

## Ajouter un test

- Déclarez `pytestmark = pytest.mark.integration` en tête de module (le
  `conftest.py` le repose de toute façon, par sécurité).
- Utilisez les fixtures du `conftest.py` : `db_session` (session applicative),
  `db_engine` (moteur + substitution du moteur global pour les modules de
  purge), `api_client` (application FastAPI réelle sur la base de test),
  `authenticated_user`, `object_storage`.
- Utilisez les fabriques de `factories.py` plutôt que du SQL brut : elles
  passent par les modèles, donc par les contraintes.
