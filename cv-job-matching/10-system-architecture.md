# 10 — Architecture système

> Conforme à `architecture.mmd` et aux décisions D01–D15 (`decisions.md`) : monolithe modulaire FastAPI + workers Celery/Redis, PostgreSQL 16 (pgvector, pg_trgm, unaccent), S3 UE, couche IA multi-provider. Ce document détaille les modules, les flux, les stratégies d'exécution, l'observabilité, la résilience et les environnements. Les décisions nouvelles sont numérotées **D16–D23** (§10). Hypothèses 🟡.

---

## 1. Vue d'ensemble

Un seul déploiement applicatif en trois rôles de processus, même image :

- **API** (FastAPI, `/api/v1`) — requêtes synchrones, derrière le proxy Next même-origine (D11).
- **Workers Celery** — files `ingestion`, `ai`, `scoring`, `maintenance` (D12 étendue par D16).
- **Beat** — planification (ingestion périodique, purge quotidienne, batch de re-scoring nocturne, expiration d'offres).

Données : PostgreSQL 16 (source de vérité), Redis (broker + sessions + cache + rate limit, séparation logique D17), S3 UE (fichiers CV, payloads bruts, exports). Couche IA : gateway multi-provider à sorties JSON validées (D08).

## 2. Modules du monolithe (D01)

Règle absolue : un module ne lit et n'écrit **que ses propres tables**. Toute donnée d'un autre module s'obtient par sa **fonction publique** (retour en DTO Pydantic, jamais d'objet ORM partagé). Exception unique et explicite : les **référentiels** (`skills`, `skill_aliases`, `sectors`) sont en lecture seule pour tous, possédés par `taxonomy` (sous-module de `jobs` 🟡). Frontières vérifiées par lint d'imports en CI (import-linter 🟡).

| Module | Responsabilités | Tables possédées | Interdits notables |
|---|---|---|---|
| `auth` | comptes, sessions Redis, consentements, reset mot de passe | `users`, `consents` | ne lit jamais le profil ; n'expose que `user_id` et l'état du compte |
| `profiles` | import CV, parsing, profil canonique avec provenance/confiance (D05), validation, versions, embedding profil | `profiles`, `profile_*`, `cv_documents`, `extraction_runs` | ne stocke aucun attribut de la liste d'exclusion (09 §4) ; ne touche pas aux offres |
| `preferences` | critères de recherche | `preferences`, `preference_*` | pas de logique de scoring (fournit des DTO au moteur) |
| `ingestion` | connecteurs par source (D04), planification, fiche de conformité, payloads bruts S3, appel de la normalisation | `sources` | n'écrit **jamais** directement dans `job_postings` : passe par `jobs.upsert_posting()` |
| `jobs` | offre canonique, dédup (D13), recherche hybride (D07), sources et liens d'origine, expiration | `job_postings`, `job_sources`, `job_locations`, `job_skills`, `job_languages` (+ `taxonomy`) | ne connaît pas les utilisateurs (aucune colonne user) |
| `matching` | moteur déterministe (06, D02/D03), `scoring-config.json`, re-scoring, invalidation par `scoring_version` | `match_results` | **aucun appel LLM ni réseau** dans la boucle de calcul ; lit profils/préférences/offres via DTO |
| `explanations` | facts déterministes → reformulation LLM optionnelle (D14), cache | `match_explanations` | le prompt ne reçoit jamais l'offre brute, uniquement `explanation_facts` |
| `generation` | brouillons ancrés (e-mail, lettre, variante CV), contrôle d'ancrage, validation humaine (D10), export | `generated_documents` | ne génère que depuis un profil `validated` ; export impossible sans `validated_at` (contrainte 11 §5) |
| `applications` | suivi de candidatures, statuts historisés, offres sauvegardées/masquées | `applications`, `application_events`, `saved_jobs` | n'envoie rien à l'extérieur (D10) |
| `privacy` | export RGPD, suppression, orchestration de purge | `deletion_requests` | ne touche pas les tables des autres modules : **chaque module implémente `purge_user(user_id)` et `export_user(user_id)`**, `privacy` orchestre (D21) |
| `ai/` (transverse) | gateway `LLMProvider`, validation des sorties, retry/repair, fallback, prompts versionnés, journal | `prompt_versions`, `ai_calls` | seul module autorisé à appeler un provider LLM |
| `platform` (transverse) | audit (`audit.log_event()`), bus d'événements internes, accès S3, trace_id | `audit_log` | `audit_log` en append-only (09 §5.7) |

### Événements internes

Publication en fin de transaction (pattern outbox léger : ligne d'événement commitée avec la transaction, relayée vers Celery 🟡), livraison **at-least-once**, handlers idempotents.

| Événement | Émis par | Consommé par (effet) |
|---|---|---|
| `cv.parsed` | profiles (worker) | profiles (notifie le front via polling ; pas de push MVP) |
| `profile.validated` / `profile.updated` | profiles | profiles (embedding profil), matching (re-scoring du profil) |
| `preferences.updated` | preferences | matching (re-scoring du profil) |
| `job.normalized` | jobs | jobs (embedding), puis matching (scoring contre profils pré-filtrés) |
| `job.expired` | jobs (beat) | matching (exclusion des tris), applications (badge « offre expirée ») |
| `generation.completed` | generation | — (état lu par polling) |
| `account.deletion_requested` | privacy | auth (invalidation sessions), planification purge J+30 |
| `scoring.version_changed` | matching (déploiement) | matching (invalidation paresseuse + batch nocturne) |

## 3. Flux bout-en-bout (séquences numérotées)

### 3.1 Import CV → profil validé

1. `POST /cv-documents` (multipart ≤ 10 Mo) : magic bytes, quota 5/j → objet S3 chiffré → ligne `cv_documents(status=pending)` → `202 {task}`.
2. Worker `ai` : antivirus 🟡 → extraction texte (parseur isolé, 09 §5.3) → texte en S3.
3. Appel gateway `extract_cv` : sortie JSON validée Pydantic (retry → repair → échec propre, D08) ; liste d'exclusion appliquée (schéma sans attributs sensibles) ; `ai_calls` journalisé.
4. Écriture `extraction_runs` + profil brouillon : chaque champ avec `source='cv_extraction'` et `confidence` (D05). `cv_documents.status=parsed`.
5. Front (polling 2 s, backoff ×1,5) affiche l'écran de validation ; l'utilisateur corrige (`PATCH`, provenance → `user_input`).
6. `POST /profile/validate` (≥ 3 compétences, ≥ 1 expérience ou formation) : promotion `cv_extraction` → `user_confirmed`, `profiles.version++`, événement `profile.validated`.
7. Worker `ai` : embedding du profil (intitulés cibles + compétences) ; worker `scoring` : re-scoring (3.2 étape 6).

### 3.2 Ingestion → normalisation → dédup → embedding → scoring

1. Beat déclenche chaque connecteur selon sa fréquence (quota de la fiche de conformité D04) ; payload brut archivé en S3 (`raw_payload_key`).
2. Idempotence : upsert `job_sources(source_id, external_ref)` (index unique 11 §4) ; offre inchangée (hash de contenu) → arrêt.
3. Normalisation (worker `ingestion`) : mapping champs, langue détectée, géocodage, extraction d'attributs par règles puis LLM en secours avec confiance (06 §2) — sanitisation : texte brut, HTML supprimé.
4. **Dédup à deux étages (D13, détail 07)** : étage 1 clé exacte `dedup_hash` ; étage 2 candidats trigram (titre+entreprise) puis cosinus embeddings > 0,92 🟡 → fusion dans `job_postings` canonique, chaque `job_sources.original_url` conservé.
5. `jobs.upsert_posting()` commit + événement `job.normalized` → embedding de l'offre (worker `ai`, batch).
6. Scoring (worker `scoring`) : pré-filtre SQL (pays + contrat) → moteur déterministe → upsert `match_results(profile_id, job_posting_id)` avec `scoring_version` (06 §4).

### 3.3 Consultation offre → match → explication

1. `GET /jobs/{id}` : offre + sources + liens d'origine.
2. `GET /jobs/{id}/match` : lecture `match_results` ; si absent ou `scoring_version` périmée → **calcul synchrone < 50 ms** (aucun appel réseau, D02) + upsert.
3. `POST /jobs/{id}/explanation` : cache `match_explanations` par clé `(profile_version, scoring_version, prompt_version, langue)` ; hit → retour immédiat.
4. Miss → facts déterministes (06 §6) → gateway `explain_match` (timeout court §7) → validation schéma + contrôle « aucun chiffre absent des facts » → cache + retour.
5. Échec LLM → réponse dégradée : facts déterministes rendus tels quels par l'UI (l'explication n'est jamais bloquante, D18).

### 3.4 Génération → validation → export

1. `POST /generations` (`Idempotency-Key` requis) : profil `validated` exigé, quota 10/h–40/j → `generated_documents(status=pending)` → `202`.
2. Worker `ai` : prompt versionné + profil validé (version épinglée `based_on_profile_version`) + faits structurés de l'offre — jamais l'offre brute 🟡 (08).
3. Sortie validée → **contrôle d'ancrage** : extraction des claims, chaque claim rattaché à un `profile_ref` ; claim non ancré → statut `failed_anchoring`, jamais présenté comme valide.
4. `status=draft` ; l'utilisateur relit avec diff, édite (`PATCH`), puis `POST .../validate` (D10).
5. `POST .../export` : exige `validated` (409 sinon, contrainte 11 §5) → rendu PDF/DOCX → lien signé court → `status=exported`, audité.

### 3.5 Suppression de compte → purge

1. `DELETE /account` (mot de passe confirmé) : `users.deleted_at=now()` (soft delete), sessions Redis invalidées, `deletion_requests.purge_after = J+30`, événement `account.deletion_requested`.
2. Pendant 30 j : compte inaccessible ; aucune réactivation au MVP 🟡.
3. Job quotidien `maintenance` : pour chaque demande échue, `privacy` appelle `purge_user(user_id)` de **chaque module** (ordre : applications → generation → matching/explanations → preferences → profiles → auth) — suppression physique des lignes et des objets S3.
4. `ai_calls` et `audit_log` : anonymisation (user_id → NULL, `subject_key` haché) (11 §2).
5. Vérification post-purge automatique : requêtes de comptage sur toutes les tables et préfixes S3 → 0 ; échec → retry + **alerte critique conformité**. Les backups expirent ≤ 30 j après la purge (D19), fermant le cycle « backups purgés au cycle » (D09).

## 4. Synchrone vs asynchrone

Synchrone : tout ce qui doit répondre < 300 ms sans dépendance externe. Asynchrone (Celery) : tout appel LLM/provider externe et tout traitement de masse. Cibles 🟡 à confirmer en alpha.

| Opération | Mode | File | Priorité | Idempotence (clé) | Retries | Délai cible |
|---|---|---|---|---|---|---|
| Recherche `GET /jobs` | sync | — | — | — | — | p95 < 300 ms |
| Scoring à la volée (`GET /jobs/{id}/match`) | sync | — | — | upsert `(profile, job)` | — | < 50 ms |
| Explication LLM | sync (timeout court) | — | — | cache par versions | 0 (dégradation facts) | p95 < 6 s 🟡 |
| Parsing CV | async | `ai` | haute | `cv_document_id` | 3, expo (60 s→) | p95 < 60 s |
| Embedding profil | async | `ai` | haute | `(profile_id, version)` | 3 | < 30 s |
| Extraction LLM d'attributs d'offre | async | `ai` | moyenne | `(job_posting_id, extractor_version)` | 3 | < 30 s |
| Embeddings offres (batch) | async | `ai` | moyenne | `(job_posting_id, content_hash)` | 3 | lot < 5 min |
| Génération de contenu | async | `ai` | haute | `Idempotency-Key` API + `generation_id` | 1 + repair (D08) | p95 < 20 s 🟡 |
| Ingestion connecteur | async (beat) | `ingestion` | basse | `(source_id, external_ref)` | 5, expo + circuit breaker | fraîcheur < 6 h 🟡 |
| Normalisation + dédup | async | `ingestion` | moyenne | `job_source_id` | 3 | < 2 min/offre |
| Re-scoring profil complet | async | `scoring` | haute (déclenché par l'utilisateur) | `(profile_id, version, scoring_version)` | 2 | < 5 min 🟡 |
| Scoring nouvelle offre × profils | async | `scoring` | moyenne | upsert | 2 | < 15 min |
| Batch re-scoring `scoring_version` | async (beat, nuit) | `scoring` | basse | upsert | 2 | < 1 nuit |
| Export RGPD | async | `maintenance` | basse | `Idempotency-Key` | 3 | < 1 h |
| Purge RGPD J+30 | async (beat, quotidien) | `maintenance` | basse | `deletion_request_id` | jusqu'à succès + alerte | échéance J+30 stricte |
| Expiration d'offres | async (beat, quotidien) | `maintenance` | basse | par offre | 2 | quotidien |

Règles générales : `acks_late=true` + tâches idempotentes (at-least-once assumé) ; DLQ par file avec alerte ; aucune tâche ne mélange deux files ; les tâches `ai` portent un budget tokens et un timeout provider propres.

## 5. Stratégies

### 5.1 Indexation (reprise de 11 §4)

| Index | Requêtes servies |
|---|---|
| `users(email)` unique citext ; partiels `deleted_at IS NULL` | login, unicité, exclusion des comptes supprimés partout |
| `job_postings.dedup_hash` unique | dédup étage 1 (insertion idempotente) |
| GIN sur `job_postings.tsv` | étape full-text de la recherche hybride |
| HNSW sur `job_postings.embedding` | rerank vectoriel (D07) + dédup étage 2 |
| trigram `(title, company_name)` | génération de candidats dédup étage 2 |
| b-tree partiel `(country_code, status) WHERE status='active'` | pré-filtre SQL du scoring et de la recherche |
| `match_results(profile_id, score DESC) WHERE blocking='[]'` | tri par défaut de `GET /matches` |
| `job_sources(source_id, external_ref)` unique | idempotence d'ingestion |
| `applications(user_id, status)`, `saved_jobs(user_id, state)` | tableau de bord candidatures, offres sauvegardées/masquées |

Toute nouvelle requête chaude passe par `EXPLAIN ANALYZE` en revue ; pas d'index spéculatif.

### 5.2 Recherche hybride (D07)

Pipeline : **(1) filtres durs SQL → (2) full-text `tsvector` → (3) rerank pgvector → (4) tri final par score de matching** si profil validé. Requête type (paramétrée) :

```sql
WITH filtered AS (                       -- (1) filtres durs, index partiels
  SELECT id, tsv, embedding
  FROM job_postings
  WHERE status = 'active'
    AND country_code = :country
    AND (:contracts::contract_type[] IS NULL OR contract = ANY(:contracts))
    AND (:language IS NULL OR language = :language)
),
ranked AS (                              -- (2) full-text, config par langue
  SELECT f.id,
         ts_rank_cd(f.tsv, websearch_to_tsquery(:ts_config, :q)) AS ftrank
  FROM filtered f
  WHERE :q = '' OR f.tsv @@ websearch_to_tsquery(:ts_config, :q)
  ORDER BY ftrank DESC
  LIMIT 500                              -- borne de candidats 🟡
)
SELECT r.id,                             -- (3) rerank vectoriel
       1 - (jp.embedding <=> :profile_embedding) AS cosine_sim,
       r.ftrank
FROM ranked r JOIN job_postings jp USING (id)
ORDER BY (0.6 * (1 - (jp.embedding <=> :profile_embedding)) + 0.4 * r.ftrank) DESC  -- pondération 🟡
LIMIT :limit;
```

(4) L'API joint ensuite `match_results` pour `sort=match` (offres bloquées reléguées, jamais retirées — 12 §3). Sans `q`, l'étape (2) est sautée et le rerank s'applique aux candidats filtrés les plus récents. Pagination par curseur opaque (12 §1) encodant la dernière valeur de tri.

### 5.3 Déduplication

Spécifiée par D13 (détail opérationnel : 07) : étage 1 hash exact, étage 2 trigram + cosinus > 0,92 🟡, fusion en `job_postings` canonique, tous les `original_url` conservés. Exécution dans le flux 3.2 étape 4, dans la transaction d'upsert (verrou consultatif par `dedup_hash` pour éviter les doubles créations concurrentes 🟡). Faux négatifs préférés aux faux positifs ; taux de doublons résiduels mesuré en alpha.

### 5.4 Matching

Moteur : spécification 06 (déterministe, `scoring-config.json`, score/confiance séparés). Côté architecture :

- **Déclencheurs de re-scoring** : `profile.validated`, `profile.updated`, `preferences.updated` (re-scoring du profil sur offres actives pré-filtrées) ; `job.normalized` (scoring de l'offre contre les profils pré-filtrés) ; consultation d'une paire non scorée (calcul synchrone).
- **Invalidation par `scoring_version`** : un déploiement changeant `scoring-config.json` publie `scoring.version_changed` ; les lectures comparent la version stockée → recalcul **paresseux** au premier accès + **batch nocturne** de rattrapage (06 §4). Aucun résultat périmé n'est jamais servi comme courant.
- Le moteur ne lit que des DTO déjà structurés — zéro I/O réseau dans la boucle (garantie testée : le module `matching` n'importe pas `ai/`).

## 6. Observabilité

- **Logs structurés JSON** : un événement par ligne ; champs standard `timestamp`, `level`, `module`, `trace_id`, `user_id` (si authentifié), `task_id`. `trace_id` généré à l'edge, propagé API → événements → tâches Celery (kwarg réservé), retourné dans les erreurs RFC 9457 (12 §1) — une erreur front est corrélable au log serveur et à la tâche. Jamais de contenu personnel dans les logs (09 §5.7).
- **Error tracking** : Sentry (API + workers + front), release et `scoring_version` taggés.
- **Métriques** (Prometheus/Grafana 🟡, D20) et seuils d'alerte initiaux 🟡 :

| Module | Métriques clés | Alerte si |
|---|---|---|
| API | latence p95 par endpoint, taux 4xx/5xx, req/s | p95 > 500 ms (15 min) ; 5xx > 1 % |
| auth | échecs login/min, resets/h | pic × 10 vs baseline (attaque) |
| ingestion | offres ingérées/h par source, taux d'échec connecteur, âge de la dernière réussite | échec > 20 % ; source silencieuse > 24 h |
| jobs/dédup | taux de fusion, offres actives | dérive de fusion × 3 (seuil déréglé) |
| profiles/parsing | durée p95, taux d'échec validation Pydantic, taux `failed` | échec > 5 % |
| matching | durée re-scoring profil, backlog file `scoring`, part de résultats à `scoring_version` périmée | backlog > 30 min ; périmés > 10 % après batch |
| ai/ | tokens/j et coût/j par tâche, latence provider, taux fallback, taux repair-parse | coût > budget/j ; fallback > 10 % ; repair > 5 % |
| generation | délai p95, taux `failed_anchoring` | ancrage échoué > 2 % (régression prompt) |
| privacy | **deletion_requests dépassant J+30**, exports en retard | > 0 = **alerte critique conformité** |
| Redis | mémoire, évictions, lag par file | éviction sur l'instance persistante > 0 (D17) |

- **Dashboards minimaux** (4) : santé API/produit ; ingestion & fraîcheur par source ; coûts & qualité IA ; conformité (purges, exports, rétentions).

## 7. Résilience

| Panne | Détection | Comportement | Dégradation visible |
|---|---|---|---|
| Provider LLM principal | timeouts/5xx, circuit breaker (5 échecs / 30 s → ouvert 60 s 🟡) | bascule automatique **fallback provider** (D08), même contrat JSON | aucune si le fallback tient |
| Les deux providers | idem | parsing CV et générations : tâches reportées (retry différé), message honnête « en file d'attente » ; explications : **facts déterministes seuls** | **l'app reste pleinement fonctionnelle** : recherche, matching, tris, suivi de candidatures n'utilisent aucun LLM (D02) — cœur du produit préservé (D18) |
| Une source d'ingestion | circuit breaker par connecteur, âge de fraîcheur | backoff, demi-ouverture périodique, alerte > 24 h | offres existantes servies ; fraîcheur par source affichée sur `GET /sources` (transparence 01 §9) |
| Redis cache/rate-limit | erreurs, latence | rate limiting : **fail-closed sur login**, fail-open sur lectures 🟡 ; cache : recomputation | latence accrue |
| Redis broker/sessions (instance persistante, D17) | idem | AOF + `noeviction` ; si indisponible : API sync fonctionne, tâches s'accumulent côté producteurs (outbox) | parsing/génération différés ; sessions perdues = re-login (incident majeur) |
| S3 | erreurs SDK | upload CV → 503 propre + invitation à réessayer ; exports différés ; **aucune lecture S3 sur le chemin de consultation courant** (la base suffit pour recherche/match) | upload/export indisponibles, reste intact |
| PostgreSQL | healthcheck `readyz` | indisponibilité totale assumée (pas de mode dégradé sans base) → bascule réplica/restauration §8 | page d'erreur |

**Timeouts** 🟡 : LLM 30 s par appel (60 s parsing CV) ; embeddings 10 s ; géocodage 3 s (retry 1) ; connecteurs sources 20 s ; `statement_timeout` Postgres 5 s côté API (60 s workers) ; Redis 500 ms.
**Budgets d'erreur (SLO)** 🟡 : disponibilité API 99,5 %/mois ; réussite parsing CV ≥ 95 % ; explications LLM ≥ 99 % hors pannes provider (sinon dégradation facts, non comptée comme erreur utilisateur).

## 8. Sauvegarde / restauration (D19)

- **PostgreSQL** : PITR — archivage continu des WAL + base backup quotidien ; **RPO 1 h / RTO 4 h 🟡** ; rétention des backups **30 j** (condition de la purge RGPD « backups au cycle », 09 §2.3) ; backups chiffrés (KMS UE).
- **Test de restauration mensuel** automatisé : restauration sur environnement isolé, vérification d'intégrité (checksums, comptages sur tables clés, migration Alembic au niveau attendu), rapport archivé ; un test échoué = incident.
- **S3** : versioning activé, chiffrement SSE-KMS, réplication intra-UE 🟡 ; règles de cycle de vie alignées sur les rétentions (exports RGPD supprimés après 7 j, payloads bruts alignés sur la rétention offres, objets CV supprimés par la purge).
- **Redis** : AOF sur l'instance persistante (sessions/broker) ; le cache est reconstructible, non sauvegardé.
- Runbook de restauration versionné (ordre : Postgres → Redis persistant → redéploiement app → vérifications), testé lors de l'exercice mensuel.

## 9. Environnements (D22)

| | local | staging | prod |
|---|---|---|---|
| Infra | docker compose (Postgres+pgvector, Redis, MinIO) | copie réduite de prod, même topologie | UE, réseau privé (09 §6.1) |
| LLM | stub déterministe (fixtures par tâche) + mode réel opt-in | providers réels en mode plafonné (budgets bas) | providers réels |
| Données | **synthétiques uniquement** (seeds versionnés : jeu de CV de référence Phase 8, offres factices) | **synthétiques uniquement — jamais de données réelles ni de dump prod, même « anonymisé »** | données réelles |
| Secrets | fichiers locaux non commités | vault, jeu distinct | vault, jeu distinct, rotation (09 §5.5) |
| E-mail | capture locale (Mailpit 🟡) | sandbox du prestataire | réel |

**Parité** : mêmes images conteneur (un seul build promu local→staging→prod), mêmes migrations Alembic, configuration exclusivement par variables d'environnement (12-factor) ; les écarts autorisés (tailles, plafonds LLM, stubs) sont listés dans un fichier de parité versionné 🟡. Staging rejoue les flux complets (3.1–3.5) sur données synthétiques, y compris un test de purge.

## 10. Décisions d'architecture ajoutées (D16–D23)

Format : décision / justification / alternatives / compromis / réévaluation. Aucune ne contredit D01–D15 ; D16–D19 précisent D12/D09, à consolider dans `decisions.md`.

### D16 — Files Celery, priorités et politique de retry (précise D12)
- **Décision** : 4 files — `ingestion`, `ai`, `scoring` (D12) + **`maintenance`** (purge RGPD, exports, expiration) ; priorités et retries par opération selon la table §4 ; `acks_late=true`, tâches idempotentes, DLQ par file avec alerte.
- **Justification** : isoler les charges (une panne provider ne bloque pas la purge RGPD, échéance légale) ; at-least-once assumé explicitement.
- **Alternatives** : file unique priorisée (rejeté : famine des tâches lentes) ; workers dédiés par module (surdimensionné MVP).
- **Compromis** : quatre pools à dimensionner et surveiller.
- **Réévaluation** : lag récurrent d'une file > 30 min.

### D17 — Deux instances Redis logiques : persistante vs volatile
- **Décision** : instance **persistante** (AOF, `noeviction`) pour broker Celery + sessions ; instance **volatile** (`allkeys-lru`) pour cache et rate limiting.
- **Justification** : une éviction LRU sur le broker ou les sessions serait une perte de données (tâches/déconnexions massives) ; le cache, lui, doit pouvoir évincer.
- **Alternatives** : une seule instance (rejeté : politiques mémoire incompatibles) ; broker RabbitMQ (rejeté : système en plus, D12 impose Redis).
- **Compromis** : deux instances à opérer 🟡 (ou deux bases logiques avec politiques distinctes si l'offre managée le permet).
- **Réévaluation** : volumétrie de tâches ou de sessions dépassant Redis (improbable au MVP).

### D18 — Dégradation gracieuse LLM : l'app fonctionne sans LLM
- **Décision** : circuit breaker par provider, bascule fallback (D08) ; si tous indisponibles : explications servies en facts déterministes, parsing/génération mis en file avec statut honnête ; recherche, matching, tri, suivi restent nominaux.
- **Justification** : le cœur de valeur (score explicable) est déterministe par conception (D02) — l'architecture en fait une garantie de disponibilité.
- **Alternatives** : bloquer les écrans dépendants (rejeté : indisponibilité artificielle) ; cache long des explications comme secours (déjà présent, insuffisant seul).
- **Compromis** : UX à deux niveaux à assumer en design (facts bruts vs prose).
- **Réévaluation** : taux de fallback > 10 % soutenu (renégocier providers).

### D19 — PITR PostgreSQL, RPO 1 h / RTO 4 h 🟡, rétention backups 30 j
- **Décision** : WAL continu + base backup quotidien ; RPO 1 h / RTO 4 h 🟡 ; rétention 30 j **alignée sur la purge RGPD** ; test de restauration mensuel automatisé.
- **Justification** : perte bornée acceptable au MVP ; la rétention 30 j rend la promesse « backups purgés au cycle » (D09) mécaniquement vraie.
- **Alternatives** : réplica synchrone multi-AZ dès le MVP (reporté : coût ; à activer si SLO tenu difficilement) ; rétention backups 90 j (rejeté : contredit la purge ≤ 30 j sans procédure de purge intra-backup complexe).
- **Compromis** : profondeur d'historique limitée à 30 j.
- **Réévaluation** : exigence contractuelle de RPO/RTO plus stricts, ou incident démontrant l'insuffisance.

### D20 — Observabilité : logs JSON + trace_id, Prometheus/Grafana 🟡, Sentry
- **Décision** : logs structurés JSON avec `trace_id` propagé edge→API→Celery et exposé dans les erreurs API ; métriques Prometheus + Grafana 🟡 ; Sentry pour l'error tracking ; 4 dashboards minimaux dont un dédié **conformité**.
- **Justification** : corrélation bout-en-bout requise par le débogage async ; la conformité (purge J+30) doit être observable, pas supposée.
- **Alternatives** : OpenTelemetry complet avec traces distribuées (reporté : un seul service, le trace_id logué suffit au MVP) ; stack ELK (rejeté : opération lourde).
- **Compromis** : pas de flame graphs de traces au MVP.
- **Réévaluation** : extraction d'un premier service hors monolithe → OTel.

### D21 — Purge et export par interface de module, orchestrés par `privacy`
- **Décision** : chaque module implémente `purge_user(user_id)` et `export_user(user_id)` ; `privacy` orchestre, vérifie (comptages post-purge → 0) et journalise ; aucun accès direct de `privacy` aux tables d'autrui.
- **Justification** : respecte la frontière D01 ; un nouveau module ne peut pas être oublié par la purge (test CI : tout module possédant une table à `user_id`/`profile_id` doit exposer l'interface).
- **Alternatives** : `ON DELETE CASCADE` global (rejeté : ne couvre ni S3 ni l'anonymisation sélective de `ai_calls`/`audit_log`, et masque les oublis) ; script SQL central (rejeté : viole les frontières, fragile aux migrations).
- **Compromis** : un peu de code par module.
- **Réévaluation** : jamais — invariant de conformité tant que D01 tient.

### D22 — Trois environnements, données synthétiques hors prod
- **Décision** : local / staging / prod à parité (même image promue, mêmes migrations, config par env) ; **jamais de données réelles hors prod**, y compris sous forme de dump « anonymisé » ; seeds synthétiques versionnés (jeu de CV de référence, offres factices) ; secrets distincts par environnement.
- **Justification** : D09 (minimisation) — un staging avec données réelles doublerait la surface RGPD ; l'anonymisation de CV est notoirement fragile (données textuelles riches ré-identifiantes).
- **Alternatives** : staging sur dump pseudonymisé (rejeté : risque de ré-identification, coût de la chaîne d'anonymisation) ; pas de staging (rejeté : flux async intestables autrement).
- **Compromis** : bugs dépendants des données réelles découverts plus tard — compensé par l'échantillonnage debug consenti (09 §2.2) et le jeu annoté.
- **Réévaluation** : besoin d'un environnement de répétition d'incident (restauration isolée ponctuelle, accès contrôlé, purge immédiate).

### D23 — Secrets par vault de plateforme, clés par KMS cloud UE
- **Décision** : secrets dans le gestionnaire de la plateforme 🟡, injectés en variables d'environnement au déploiement ; chiffrement au repos par KMS géré en UE, rotation annuelle des clés, rotation des secrets applicatifs (09 §5.5) ; scan anti-fuite en CI.
- **Justification** : D09 (chiffrement, UE) ; pas d'infrastructure de secrets à opérer nous-mêmes au MVP.
- **Alternatives** : Vault auto-hébergé (rejeté MVP : opération lourde) ; secrets chiffrés en repo type SOPS (rejeté : rotation et audit plus faibles).
- **Compromis** : dépendance au cloud provider pour la cryptographie.
- **Réévaluation** : exigence de HSM dédié ou multi-cloud.

---

## Questions ouvertes

1. **Pondération du rerank hybride** (0,6 vectoriel / 0,4 full-text 🟡) et borne de 500 candidats : à calibrer sur le jeu annoté — qui arbitre et avec quelle métrique (NDCG@10 de 06 §5 ?) ?
2. **Outbox événements** : implémentation exacte (table outbox + relayeur vs publication post-commit best-effort) — arbitrer fiabilité vs simplicité avant la Phase ingestion.
3. **Redis managé** : l'offre de l'hébergeur UE retenu permet-elle deux instances (ou deux politiques mémoire) ? Sinon, quel plan B pour D17 ?
4. **RPO 1 h / RTO 4 h 🟡** : validés par le produit ? Un RPO 1 h peut perdre jusqu'à 1 h d'édition de profil — acceptable au MVP ?
5. **Priorités Celery** : Redis ne gère pas nativement les priorités fines — files dédiées suffisantes ou sous-files par priorité nécessaires (à trancher à l'implémentation) ?
6. **Fenêtre du batch nocturne** de re-scoring : durée réelle sur 500k offres × profils actifs — le pré-filtre SQL suffit-il à tenir « < 1 nuit » ?
7. **Géocodage** : provider UE exact et stratégie de cache des lieux (les libellés d'offres se répètent massivement) — cache partagé sans données personnelles à spécifier.
8. **Fichier de parité d'environnements** : format et propriétaire (checklist versionnée vs test automatisé de config).
9. **Scaling API vs workers** : le monolithe se déploie en trois rôles — seuils d'autoscaling par rôle à définir avant l'alpha ouverte.
10. **Multi-AZ PostgreSQL** : réplica en attente dès le MVP (coût) ou accepté comme risque jusqu'aux premiers utilisateurs payants ?
