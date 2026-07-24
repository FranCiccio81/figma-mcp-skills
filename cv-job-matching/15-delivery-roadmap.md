# 15 — Roadmap de delivery

> Organisation en epics alignés sur les features A–Q (brief §4), séquencés en 5 jalons 🟡 exprimés en **semaines relatives** (S1 = première semaine de dev). Pas de dates calendaires. Équipe de référence 🟡 : 3–4 devs (2 back, 1 front, 1 fullstack/DevOps), 1 PO, QA Lead partagé.

---

## 1. Epics et user stories clés

### E1 — Fondations techniques (lot transverse)
Repo monorepo (api/, web/, infra/), CI/CD (lint+mypy+tests+build, déploiement staging auto), Docker Compose dev, PostgreSQL 16 + extensions, Redis, Celery (files `ingestion`/`ai`/`scoring`), migrations Alembic depuis `initial-schema.sql`, observabilité de base (logs structurés, Sentry 🟡, métriques), gestion des secrets, hébergement UE provisionné.
- US-1.1 : en tant que dev, je pousse une PR et la CI exécute lint, types, tests et déploie sur staging en < 15 min.
- US-1.2 : en tant que DevOps, je vois erreurs et latences p95 par endpoint sans SSH.
- **Dépendances** : aucune. **Sortie** : `healthz`/`readyz` verts en staging.

### E2 — Compte & onboarding (A)
Register/login/logout (cookies httpOnly, sessions Redis), CSRF, consentements stockés, `GET /me` avec état d'onboarding, rate limiting global, shell front (layout, i18n FR avec next-intl 🟡).
- US-2.1 : je crée un compte, mes consentements sont enregistrés horodatés.
- US-2.2 : accès croisé à une ressource d'autrui → 404 (posé comme middleware dès cet epic).
- **Dépend de** : E1.

### E3 — Import CV & profil (B, C)
Upload PDF/DOCX (validation magic bytes, ≤ 10 Mo, S3), pipeline Celery de parsing, couche IA v1 (`LLMProvider`, `extract_cv`, validation Pydantic contre `ai-output-schemas.json`, retry/repair, `prompt_versions`, `ai_calls`), liste d'exclusion des attributs sensibles, écran de revue avec provenance/confiance par champ, CRUD profil, `POST /profile/validate` (promotion des provenances).
- US-3.1 : j'importe mon CV et j'obtiens un profil pré-rempli avec badges de confiance en < 60 s.
- US-3.2 : je corrige un champ mal extrait et sa provenance devient `user_input`.
- US-3.3 : je ne peux pas valider un profil avec < 3 compétences.
- **Dépend de** : E1, E2. **Risques liés** : R3, R4, R5.

### E4 — Préférences (D)
`GET/PUT /preferences` (payload unique), géocodage des lieux 🟡 (Nominatim self-hosted ou BAN pour la France), UI multi-étapes.
- US-4.1 : je définis métiers cibles, lieux + rayon, télétravail, contrats, salaire, langues, secteurs (dont exclusions).
- **Dépend de** : E2 (peut avancer en parallèle d'E3).

### E5 — Ingestion & normalisation (E, F)
Framework connecteurs + fiches de conformité (D04), connecteur France Travail puis Greenhouse/Lever 🟡, normalisation (langue, contrat, lieu géocodé, salaire, séniorité par règles), `extract_job` LLM avec cache, dédup deux étages (D13), embeddings pgvector, planification Celery beat, registre des sources exposé (`GET /sources`).
- US-5.1 : une offre présente sur deux sources apparaît une fois, avec ses deux liens d'origine.
- US-5.2 : en tant qu'ops, je vois fraîcheur et volumétrie par source.
- **Dépend de** : E1. **Risques** : R1, R6, R7.

### E6 — Recherche & consultation (G)
Recherche hybride (filtres SQL + tsvector fr/en + rerank vectoriel), pagination curseur, détail offre avec source(s) et lien d'origine, tri `relevance`/`date`.
- US-6.1 : je filtre par lieu/rayon, remote, contrat, langue et j'obtiens des résultats < 500 ms p95.
- **Dépend de** : E4, E5.

### E7 — Matching & confiance (H, I)
`matching/engine.py` (12 dimensions, renormalisation, bloquants, confiance, `low_data`), chargement `scoring-config.json` versionné, pipeline de scoring (triggers profil/offre/consultation, upsert `match_results`), tri `match`, badges UI score+confiance+bloquants+inconnues.
- US-7.1 : chaque offre affiche score ET confiance distincts, jamais fusionnés (D03).
- US-7.2 : une offre bloquante reste visible, badgée, reléguée dans le tri.
- **Dépend de** : E3 (profil validé), E4, E5. **Gate associé** : cas UM-01…18 (13 §2.1) verts.

### E8 — Explication (J)
`explanation_facts` déterministes, panneau d'explication UI (forces/lacunes/inconnues), reformulation LLM à la demande (`explain_match`, cache `match_explanations`, contrôle « aucun chiffre hors facts »).
- US-8.1 : j'ouvre l'explication et je vois dimension par dimension pourquoi 72/100.
- **Dépend de** : E7.

### E9 — Sauvegarde & masquage (K)
`saved_jobs` (états saved/hidden), filtres associés.
- US-9.1 : une offre masquée n'apparaît plus sauf si je l'affiche explicitement.
- **Dépend de** : E6. (Petit epic, peut se glisser en parallèle.)

### E10 — Génération ancrée (L, M, N, O)
`POST /generations` (4 doc_types), prompts ancrés au profil validé uniquement, extraction de claims + contrôle d'ancrage, écran diff/relecture, validation humaine (D10), export copie/PDF/DOCX, idempotence, quotas LLM.
- US-10.1 : je génère une lettre ; chaque affirmation est reliée à un élément de mon profil.
- US-10.2 : impossible d'exporter sans avoir validé (contrainte SQL + API 409).
- US-10.3 : j'adapte mon CV à une offre ; le canonique n'est jamais modifié (variante, D05).
- **Dépend de** : E3, E7 (contexte offre). **Risques** : R4, R7.

### E11 — Suivi des candidatures (P)
CRUD applications (internes + externes), transitions de statut historisées, tableau de bord.
- US-11.1 : je passe une candidature en « entretien » avec une note, l'historique est conservé.
- **Dépend de** : E2 (léger ; lien vers offres si E6 livré).

### E12 — Privacy & conformité (Q)
Export RGPD (archive JSON, lien signé 7 j), suppression de compte (soft delete + purge J+30 + objets S3 + anonymisation `ai_calls`/`audit_log`), registre des traitements, DPIA, pages légales.
- US-12.1 : je supprime mon compte ; test automatisé prouvant la purge complète à J+30 (13 Q9).
- **Dépend de** : E2 (le job de purge doit couvrir toutes les tables → finalisé après E10/E11).

### E13 — Qualité matching & prompts (transverse, démarre tôt)
Constitution `eval-set-v1` (500 paires, 3 annotateurs, guide versionné), harnais d'évaluation + gates CI (`evaluation_gates`), corpus CV/offres/adversarial, harnais prompts CI+nightly, test d'invariance biais.
- US-13.1 : en tant que QA Lead, toute PR touchant le scoring montre son delta Spearman avant merge.
- **Dépend de** : E5 (offres réelles) et E7 (moteur) pour les runs ; l'**annotation démarre dès S6** 🟡 (chemin critique humain, 3 annotateurs à recruter).

### E14 — Durcissement & alpha (transverse final)
Suite sécurité complète (13 §5), k6 🟡, schemathesis 🟡, accessibilité AA, analytics (14), runbooks, sauvegardes/restauration testées, digest e-mail simple 🟡 (si temps), onboarding des utilisateurs alpha.
- **Dépend de** : tout.

## 2. Jalons 🟡 (semaines relatives)

| Jalon | Semaines 🟡 | Contenu | Critère de passage |
|---|---|---|---|
| **M1 — Fondations + profil** | S1–S4 | E1, E2, E3, E4 (début) | CV importé → profil validé en staging ; CI complète ; authz 404 en place ; 0 attribut sensible extrait sur 10 CV de test |
| **M2 — Ingestion + recherche** | S4–S7 | E4 (fin), E5, E6, E9 | ≥ 2 connecteurs actifs avec fiches de conformité signées ; dédup mesurée sur corpus réel ; recherche p95 < 500 ms |
| **M3 — Matching + explication** | S7–S10 | E7, E8, E13 (harnais + début annotation) | UM-01…18 verts ; scores visibles en staging ; `eval-set-v1` ≥ 50 % annoté |
| **M4 — Génération + candidatures** | S10–S13 | E10, E11, E13 (gates actifs) | 0 invention sur le jeu prompts ; export bloqué sans validation ; gates matching passés (Spearman ≥ 0,6, NDCG@10 ≥ 0,75, bloquants 0,95/0,85) |
| **M5 — Privacy + durcissement + alpha** | S13–S16 | E12, E14 | Checklist §3 à 100 % ; DPIA signée ; alpha fermée ouverte (20–50 utilisateurs 🟡) |

Chevauchements assumés : E13 court de S6 à S13 (l'annotation humaine est le chemin critique du gate H6) ; E11 est une soupape de charge (parallélisable à tout moment après M1).

## 3. Critères de sortie du MVP (checklist mesurable)

**Qualité (reprend 13 §9 — seuils inchangés) :**
- [ ] Q1–Q13 de `13-testing-strategy.md` tous verts (couverture, gates matching, 0 invention, schema_error < 5 %, authz 404, purge J+30, sources 100 %, charge, CVE, AA).
- [ ] Spearman ≥ 0,6 · NDCG@10 ≥ 0,75 · précision bloquants ≥ 0,95 · rappel ≥ 0,85 sur `eval-set-v1` (α ≥ 0,65).
- [ ] Test d'invariance biais : 0 différence de score.
- [ ] 0 offre à critère bloquant présentée > 60 sans avertissement (test automatisé + E2E).

**Produit (métriques brief §8, mesurées sur l'alpha fermée) :**
- [ ] Activation ≥ 60 % des inscrits alpha (profil validé).
- [ ] H1 : ≥ 40 % des actifs hebdo ouvrent ≥ 1 explication.
- [ ] H2 : ≤ 20 % de champs corrigés ; ≥ 70 % des profils validés < 10 min.
- [ ] H3 : ≥ 30 offres à score ≥ 60 par profil actif (médiane).
- [ ] H4 : ≥ 50 % des générations exportées.
- [ ] H5 : ≥ 40 % des candidatures avec ≥ 1 mise à jour de statut.
- [ ] Rétention S4 ≥ 25 % (mesurable seulement 4 semaines après ouverture alpha — critère de **sortie d'alpha**, pas de gel du code).

**Conformité :**
- [ ] DPIA réalisée et registre des traitements à jour ; analyse AI Act documentée (R2).
- [ ] Fiches de conformité signées pour 100 % des connecteurs actifs (R1).
- [ ] Suppression de compte et export RGPD démontrés en conditions réelles.

## 4. Risques de delivery et arbitrages assumés

| Risque delivery | Signal | Arbitrage |
|---|---|---|
| Annotation du jeu (500 paires × 3) en retard | < 50 % annoté à S10 | réduire à 300 paires 🟡 en gardant la stratification ; gates calculés sur 300, complétés post-alpha |
| Parsing CV sous H2 | > 30 % de champs corrigés en interne à M3 | itérer prompts plutôt que d'ajouter des features ; M4 glisse d'une semaine max |
| Connecteur partenaire non signé | pas de contrat à S6 | lancer avec France Travail + 1 flux ATS seulement (H3 surveillée de près) |
| Charge Celery/infra sous-estimée | p95 ingestion > cible à M2 | réduire la fréquence de rafraîchissement des sources (fraîcheur 24 h au lieu de 6 h 🟡) |
| Retard global | M4 non atteint à S14 | **ordre de coupe assumé** : 1) digest e-mail, 2) `optimize_cv` (N) puis `tailor_cv` (O) — L/M suffisent à tester H4, 3) reformulation LLM de l'explication (J garde sa couche déterministe), 4) export DOCX (garder copie+PDF). **Jamais coupés** : validation humaine (D10), privacy (Q), gates qualité, transparence des sources |

---

## Questions ouvertes

1. Taille et profil exacts de l'équipe (l'hypothèse 3–4 devs 🟡 conditionne S1–S16 ; à 2 devs, prévoir +4 semaines).
2. Qui sont les 3 annotateurs du jeu d'évaluation (internes, freelances ?) et quel budget — chemin critique de M4.
3. Le partenaire « source 3 » (D04) est-il en discussion ? Date butoir de signature pour intégration avant M2 ?
4. L'alpha fermée : recrutement des 20–50 testeurs 🟡 (canal, incitation) — à lancer dès M3 pour ne pas bloquer M5.
5. La revue juridique AI Act (R2) doit-elle être rendue avant l'ouverture de l'alpha ou avant le lancement public ?
6. Faut-il un jalon M4.5 de « gel des prompts » (version figée pour l'alpha) pour stabiliser les mesures H2/H4 ?

---

## Annexe — Phase 10 : Préparation de l'implémentation

### A. Arborescence du repository (monorepo)

```
boussole/
├── api/                          # FastAPI (Python 3.12)
│   ├── app/
│   │   ├── modules/              # frontières D01 — un package par module
│   │   │   ├── auth/  profiles/  preferences/  ingestion/
│   │   │   ├── jobs/  matching/  explanations/  generation/
│   │   │   ├── applications/  privacy/
│   │   │   └── (chaque module : router.py, service.py, repository.py, schemas.py, purge.py)
│   │   ├── ai/                   # LLM gateway (providers/, tasks/, schemas/, anchoring.py)
│   │   ├── core/                 # config, db, redis, sécurité, observabilité
│   │   └── workers/              # tâches Celery par file (ingestion, ai, scoring, maintenance)
│   ├── alembic/                  # migrations (0001 = initial-schema.sql)
│   ├── config/scoring-config.json
│   ├── prompts/                  # templates versionnés (source des template_key)
│   └── tests/  (unit/ integration/ prompts/ eval/)
├── web/                          # Next.js App Router (TS, Tailwind, shadcn/ui)
│   ├── app/  (auth)/ (main)/dashboard offres candidatures profil preferences parametres
│   ├── components/  lib/api/     # client typé généré depuis openapi.yaml
│   └── messages/fr.json en.json  # i18n (D15)
├── infra/                        # docker-compose.dev.yml, Dockerfiles, IaC 🟡, CI
├── docs/                         # les présents livrables 01–17 + artefacts
└── datasets/                     # jeux de référence versionnés (eval-set-vX, prompts)
```

### B. Conventions

- **Python** : ruff + mypy strict sur `matching/` et `ai/` ; imports inter-modules uniquement via `modules/<x>/service.py` (contrôlé par import-linter — D01) ; le module `matching/` n'importe jamais `ai/` (gate CI, D02).
- **TypeScript** : ESLint + Prettier ; types API générés depuis `openapi.yaml` (openapi-typescript) — jamais écrits à la main ; Zod pour les formulaires (RHF).
- **Git** : trunk-based, branches courtes `feat/…`, revue obligatoire, Conventional Commits ; un changement de `scoring-config.json` ou `prompts/` exige le label `needs-eval` (déclenche le run d'évaluation).
- **API** : tout endpoint nouveau = mise à jour d'`openapi.yaml` dans la même PR (schemathesis nightly le vérifie).

### C. Variables d'environnement (extrait normatif)

| Variable | Exemple | Notes |
|---|---|---|
| `DATABASE_URL` | postgres://…  | jamais committée (D23) |
| `REDIS_PERSISTENT_URL` / `REDIS_CACHE_URL` | redis://… | deux instances (D17) |
| `S3_ENDPOINT` / `S3_BUCKET` / `S3_REGION` | … | stockage UE (D09) |
| `ANTHROPIC_API_KEY` / `FALLBACK_LLM_API_KEY` | … | via vault (D23) |
| `EMBEDDINGS_MODEL` / `EMBEDDINGS_DIM` | …/1024 | 🟡 Q11 |
| `SCORING_CONFIG_PATH` | config/scoring-config.json | version chargée au boot |
| `SESSION_TTL_DAYS` | 30 | |
| `FEATURE_SOURCE_FRANCE_TRAVAIL` etc. | false | connecteurs derrière flags (Q2/Q3) |
| `SENTRY_DSN`, `OTEL_EXPORTER_OTLP_ENDPOINT` | … | observabilité (D20) |

### D. Migrations initiales et données de démo

1. `alembic upgrade head` → 0001 (extensions + schéma complet de `initial-schema.sql`).
2. Seeds idempotents : `sectors` (NACE simplifié), `skills`+`skill_aliases` (sous-ensemble ESCO tech 🟡), `prompt_versions` (v1 de chaque tâche), `sources` (inactives par défaut).
3. Données de démo (dev/staging uniquement — D22) : `make seed-demo` génère 3 profils synthétiques, 200 offres synthétiques FR/EN, scores pré-calculés. Jamais exécutable en prod (garde sur `ENV`).

### E. Commandes de développement

```
make up            # docker compose : postgres, redis ×2, minio, mailpit, api, web, workers
make migrate       # alembic upgrade head
make seed / seed-demo
make test          # unit + integration (testcontainers)
make eval-matching # jeu annoté → gates de scoring-config.json
make eval-prompts  # jeux prompts (échantillon) — complet en nightly
make lint typecheck openapi-gen
```

### F. Pipeline CI/CD

1. **PR** : lint + typecheck (py/ts) → tests unitaires → intégration (testcontainers) → build images → `eval-matching` si `scoring-config.json`/`matching/` touchés → `eval-prompts` (échantillon) si `prompts/` touché → scan dépendances + secrets (gate bloquante).
2. **main** : E2E Playwright sur environnement éphémère → déploiement staging auto → smoke tests.
3. **prod** : déploiement manuel approuvé (tag), migrations auto avec verrou, rollback = image précédente + `alembic downgrade` documenté.
4. **Nightly** : schemathesis contre staging, eval-prompts complet, test de restauration backup (mensuel), audit dépendances.

### G. Definition of Done (par user story)

- Critères d'acceptation (AC-x-n de 05) automatisés ou explicitement testés en manuel documenté ;
- Tests unitaires + intégration verts, couverture du module ≥ seuils de 13 ;
- `openapi.yaml` et docs impactées mises à jour ; i18n externalisée ; a11y AA vérifiée sur les écrans touchés ;
- Pas de secret/donnée personnelle en logs ; événements analytics de 14 émis ;
- Revue de code approuvée ; feature flag si la fonctionnalité dépend d'une validation juridique ouverte (17).
