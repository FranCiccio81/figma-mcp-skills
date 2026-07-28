# traceability-matrix.md — Matrice de traçabilité

> Relie chaque besoin (feature A–Q) aux règles, spécifications, écrans, endpoints, entités et tests. Conventions d'ID : `F-x` (spec fonctionnelle, doc 05), `RM-x-n` (règles métier, doc 05), `AC-x-n` (critères d'acceptation, doc 05), `SCR-xx` (écrans, docs 03–04), `D01–D15+` (décisions), dimensions du matching (doc 06 §2).

| Feature | Spec | Décisions clés | Endpoints (12 / openapi.yaml) | Entités (11 / initial-schema.sql) | Écrans (03) | Tests attendus (13) |
|---|---|---|---|---|---|---|
| A. Compte & onboarding | F-A | D09, D11 | `POST /auth/register`, `/auth/login`, `/auth/logout`, `GET /me` | `users`, `consents` | SCR onboarding/auth | unit (validation, hash), intégration auth, E2E onboarding, sécurité (rate limit login) |
| B. Import & parsing CV | F-B | D05, D08 | `POST /cv-documents`, `GET /cv-documents/{id}` | `cv_documents`, `extraction_runs` | SCR import CV | unit (validation fichier), intégration worker parsing, prompts `extract_cv` (jeu CV de référence), sécurité upload |
| C. Édition du profil | F-C | D05 | `GET/PATCH /profile`, CRUD sous-ressources, `POST /profile/validate` | `profiles`, `profile_*` | SCR profil | unit (promotion provenance), intégration CRUD, E2E validation profil |
| D. Préférences | F-D | D03 | `GET/PUT /preferences` | `preferences`, `preference_*` | SCR préférences | unit (validation Zod/Pydantic), intégration re-scoring déclenché |
| E. Agrégation d'offres | F-E | D04 | interne + `GET /sources` | `sources`, `job_sources` | SCR à propos des sources | intégration connecteurs mockés, idempotence `(source_id, external_ref)`, monitoring SLO fraîcheur |
| F. Normalisation & dédup | F-F | D13 | interne | `job_postings`, `job_skills`, `job_languages`, `job_locations` | — | unit dédup (hash + trigram + cosinus), fusion des champs, prompts `extract_job` |
| G. Recherche & filtres | F-G | D07 | `GET /jobs` | `job_postings` (tsv, embedding, index) | SCR liste offres | unit requête hybride, intégration filtres, perfs p95 |
| H. Matching | F-H | D02, D03 | `GET /jobs/{id}/match`, `GET /matches` | `match_results` | SCR détail offre | unit par dimension (06 §2), renormalisation, gates jeu annoté (scoring-config `evaluation_gates`), invariance biais |
| I. Indice de confiance | F-I | D03 | inclus dans `/match` | `match_results.confidence` | idem | unit formule confiance, calibration sur jeu annoté |
| J. Explication | F-J | D14 | `POST /jobs/{id}/explanation` | `match_explanations` | panneau explication | unit facts déterministes, prompts `explain_match` (diff numérique = 0 écart), cohérence score/explication |
| K. Sauvegarde & masquage | F-K | — | `PUT/DELETE /jobs/{id}/saved-state` | `saved_jobs` | liste + détail | intégration états, E2E |
| L. Génération e-mails | F-L | D10, D08 | `POST /generations` (`email`), cycle validate/export | `generated_documents` | SCR génération | prompts `generate_email` (0 invention, claims ancrés), intégration cycle draft→validated→exported |
| M. Lettres de motivation | F-M | D10, D08 | idem (`cover_letter`) | idem | idem | prompts `generate_letter`, contrôle d'ancrage, E2E génération complète |
| N. Optimisation CV | F-N | D10 | idem (`cv_optimization`) | idem | SCR optimisation | prompts `optimize_cv` (questions plutôt qu'inventions) |
| O. Adaptation CV à une offre | F-O | D05, D10 | idem (`cv_variant`) | idem (`based_on_profile_version`) | SCR variante CV (diff) | prompts `tailor_cv` (kinds autorisés seulement), unit interdiction de création |
| P. Suivi candidatures | F-P | — | CRUD `/applications`, `POST /applications/{id}/status` | `applications`, `application_events` | SCR kanban/liste | unit transitions, intégration historique, E2E |
| Q. Données & suppression | F-Q | D09 | `POST /privacy/export`, `DELETE /account` | `deletion_requests`, purge jobs | SCR paramètres | intégration purge J+30 (test automatisé), export complet, sécurité |

## Règles transverses → vérification

| Exigence produit | Implémentation | Vérification |
|---|---|---|
| Score jamais généré par le LLM | D02, moteur `matching/` sans appel réseau | revue de code + test « aucun appel IA dans le moteur » |
| Score ≠ confiance | D03, formules 06 §1 | tests unitaires des deux formules |
| Bloquants jamais masqués silencieusement | 06 §3, `include_blocked=true` par défaut | test API défaut + E2E badge |
| Inconnues marquées comme telles | `unknown_dimensions`, seuil confiance extraction 0,5 | tests unitaires + microcopies (04) |
| Source + lien d'origine conservés | `job_sources.original_url NOT NULL` | contrainte SQL + test intégration |
| Aucune invention dans les contenus | schémas claims + contrôle d'ancrage (08) | tests de prompts en CI, gate « 0 invention » |
| Validation humaine avant export | CHECK SQL + 409 `generation_not_validated` | test contrainte + test API |
| Attributs sensibles exclus | listes d'exclusion prompts (08), absents du schéma | revue schémas + test invariance biais |
| Suppression effective ≤ 30 j | `deletion_requests.purge_after`, worker purge | test automatisé de purge |
| Docs importés = données non fiables | délimiteurs + règles anti-injection (08) | jeu adversarial en CI |

*(Les IDs fins RM-x-n / AC-x-n / SCR-xx sont définis dans les docs 03–05 ; cette matrice est mise à jour à chaque revue de phase.)*

---

# État réel d'implémentation (M1 → M6, arrêté au 2026-07-28)

> La matrice ci-dessus décrit l'**intention**. Celle-ci décrit ce qui **existe**. Racine : `boussole/api/`. Préfixe d'API : `/api/v1`. Légende : ✅ livré et testé · 🟡 livré avec réserve explicite · ⛔ non livré.

| Feature | État | Module réel | Endpoints réels | Tests réels |
|---|---|---|---|---|
| A. Compte & onboarding | ✅ | `app/modules/auth/` | `POST /auth/register`, `POST /auth/login`, `POST /auth/logout`, `GET /me` | `tests/unit/test_auth_api.py` (13), `test_security.py` (11 — argon2, sessions, CSRF) |
| B. Import & parsing CV | 🟡 | `app/modules/profiles/cv/`, `app/ai/tasks/extract_cv.py`, `app/workers/cv_tasks.py` (`ai.parse_cv`) | `POST /cv-documents`, `GET /cv-documents/{id}`, `POST /cv-documents/{id}/apply` | `tests/unit/cv/` : `test_upload_api.py` (19), `test_worker_tasks.py` (14), `test_extract_cv.py` (20), `test_apply_api.py` (10), `test_cv_safety.py` (15), `test_purge.py` (4) — 🟡 **antivirus ClamAV absent** (Q16) |
| C. Édition du profil | ✅ | `app/modules/profiles/` | `GET/PATCH /profile`, `POST /profile/validate`, CRUD `experiences`/`educations`/`skills`/`languages` | `tests/unit/profiles/test_profiles_api.py` (24), `test_experience_merge.py` (8) |
| D. Préférences | 🟡 | `app/modules/preferences/` | `GET/PUT /preferences` | `tests/unit/preferences/test_preferences_api.py` (15) — 🟡 **re-scoring asynchrone non implémenté**, recalcul paresseux au prochain accès (17 N11) |
| E. Agrégation d'offres | 🟡 | `app/modules/ingestion/connectors/` (France Travail, Greenhouse, Lever), tâches `ingestion.sync_source`, `ingestion.reconcile`, `maintenance.expire_jobs` | `GET /sources` (servi par le routeur `jobs` — voir 17 N10) | `tests/unit/ingestion/test_connectors.py` (15), `test_ingest_service.py` (25), `test_worker_tasks.py` (9) — 🟡 les trois connecteurs restent derrière **feature flags désactivés** (Q2/Q3) |
| F. Normalisation & dédup | 🟡 | `app/modules/ingestion/{normalize,extract_rules,taxonomy,geocode,service}.py` | interne | `tests/unit/ingestion/test_normalize.py` (21), `test_extract_rules.py` (53), `test_taxonomy.py` (7), `test_dedup_stage2.py` (16) ; `tests/integration/test_ingestion_dedup.py` (8) — 🟡 **étage 2 neutralisé** hors provider sémantique (D28) : seul le hash exact déduplique |
| G. Recherche & filtres | ✅ | `app/modules/jobs/` | `GET /jobs`, `GET /jobs/{id}` | `tests/unit/jobs/test_search_sql.py` (17), `test_search_rerank.py` (23), `test_jobs_api.py` (25), `test_cursor.py` (7) ; `tests/integration/test_jobs_search_pagination.py` (8), `test_jobs_fulltext_trigger.py` (8), `test_jobs_salary_filter.py` (5) |
| H. Matching | ✅ | `app/matching/` (moteur pur) + `app/modules/matching/` (API, adaptateurs, dépôt) | `GET /jobs/{id}/match`, `GET /matches` | `tests/unit/matching/` : `test_dimensions_skills.py` (11), `test_dimensions_profile.py` (20), `test_dimensions_logistics.py` (22), `test_dimensions_terms.py` (22), `test_blocking.py` (6), `test_engine.py` (11), `test_config.py` (9), `test_golden_um.py` (19 — cas d'or UM-01…UM-18), `test_purity.py` (4) ; `tests/unit/matching_api/` (44) |
| I. Indice de confiance | ✅ | `app/matching/engine.py` (`confidence = round(100 × Σ(w·k·q)/Σ(w))`, drapeau `low_data`) | inclus dans `/match` | `tests/unit/matching/test_engine.py` — ⛔ **calibration sur jeu annoté non faite** (Q19/Q20/Q47 : le jeu n'existe pas) |
| J. Explication | ✅ | `app/modules/explanations/` | `POST /jobs/{id}/explanation` | `tests/unit/matching/test_explanations.py` (7), `tests/unit/matching_api/test_explanations_api.py` (9), `test_explanations_event_loop.py` (3) |
| K. Sauvegarde & masquage | ✅ | `app/modules/jobs/` | `PUT /jobs/{id}/saved-state`, `DELETE /jobs/{id}/saved-state`, `saved_only` sur `GET /jobs` | `tests/unit/jobs/test_jobs_api.py`, `tests/unit/privacy/test_jobs_saved_purge.py` (7) |
| L/M/N/O. Générations (e-mail, lettre, optimisation CV, variante CV) | 🟡 | `app/modules/generation/`, `app/ai/tasks/generate.py`, `app/workers/generation_tasks.py` (`ai.generate`) | `POST /generations`, `GET /generations`, `GET /generations/{id}`, `PATCH /generations/{id}`, `POST /generations/{id}/validate`, `POST /generations/{id}/export` | `tests/unit/generation/` : `test_generation_api.py` (27), `test_generation_lifecycle.py` (9), `test_generation_anchoring.py` (19), `test_grounding_unit.py` (11), `test_purge.py` (3) — 🟡 **aucun avertissement serveur sur critère bloquant** (Q27) ; une génération `failed` **consomme le quota**, contre l'hypothèse Q28 (17 N7) |
| P. Suivi candidatures | ✅ | `app/modules/applications/` | `GET/POST /applications`, `GET/PATCH/DELETE /applications/{id}`, `POST /applications/{id}/status` | `tests/unit/applications/test_applications_api.py` (36), `test_cursor.py` (3), `test_purge.py` (3) |
| Q. Données & suppression | 🟡 | `app/modules/privacy/` (registre, `purge_runner`, `export_builder`, `signing`), tâches `maintenance.privacy_export`, `maintenance.purge_due_accounts`, `maintenance.purge_expired_exports` | `POST /privacy/export`, `GET /privacy/exports/{id}`, `GET /privacy/exports/{id}/download`, `DELETE /account` | `tests/unit/privacy/` (57) ; `tests/integration/test_privacy_purge.py` (12), `test_privacy_export.py` (5) — 🟡 **fichiers CV absents de l'export** (17 N8), **rétention 13 mois d'`ai_calls` non implémentée** (17 N4), **compte OAuth non supprimable** (17 N5), **fenêtre de rétractation 7 j absente** (Q30) |

**Couverture** : 970 tests unitaires (72 fichiers) + 61 tests d'intégration (7 fichiers). Migrations `0001` → `0006`. 13 tâches Celery enregistrées.

## Règles transverses → vérification RÉELLE

> Chaque garantie produit est ici rattachée au test qui la vérifie **aujourd'hui**, par son nom de fichier. « Revue de code » n'est plus accepté comme moyen de vérification pour une garantie structurante.

| Exigence produit | Implémentation réelle | Test qui la vérifie aujourd'hui |
|---|---|---|
| Score jamais généré par le LLM | `app/matching/` sans dépendance réseau/DB | `tests/unit/matching/test_purity.py` — vérification par **AST** *et* par **sous-processus** (imports interdits) ; ce n'est plus une revue de code |
| Score ≠ confiance | `app/matching/engine.py`, deux formules distinctes | `tests/unit/matching/test_engine.py` |
| Bloquants jamais masqués silencieusement | 6 codes bloquants, plancher 0,7, rétrogradation ; le score n'est jamais annulé | `tests/unit/matching/test_blocking.py` |
| Inconnues marquées comme telles | `unknown_dimensions` + motifs fermés (`job_missing`, `candidate_missing`, `low_confidence`, `unconvertible_value`) | `tests/unit/matching/test_dimensions_*.py`, `test_engine.py` (`low_data`) |
| Source + lien d'origine conservés | `job_sources.original_url NOT NULL` | `tests/integration/test_sql_constraints.py` — contrainte exercée contre PostgreSQL réel |
| Aucune invention dans les contenus | ancrage + détecteurs de grounding (D33) | `tests/unit/generation/test_grounding_unit.py`, `test_generation_anchoring.py` |
| Validation humaine avant export | contrainte SQL + 409 `generation_not_validated` | `tests/unit/generation/test_generation_lifecycle.py`, `tests/integration/test_sql_constraints.py` |
| Attributs sensibles exclus | listes d'exclusion + schéma fermé | `tests/unit/cv/test_extract_cv.py` |
| Minimisation vers les LLM | `app/ai/scrubbing.py` (barrière déterministe) | `tests/unit/generation/test_grounding_unit.py`, `tests/unit/embeddings/test_text.py` |
| Suppression effective ≤ 30 j | `deletion_requests.purge_after` + `maintenance.purge_due_accounts` | `tests/integration/test_privacy_purge.py` — inventaire depuis `information_schema`, parcours **transitif** des clés étrangères |
| Docs importés = données non fiables | délimiteurs + anti-injection + bornes de fichier | `tests/unit/cv/test_cv_safety.py`, `tests/unit/cv/test_extract_cv.py` |

### Garanties que la revue a montrées **non tenues**, puis corrigées

> Une ligne par garantie qui était annoncée mais ne tenait pas à l'exécution, avec le test de non-régression qui la verrouille désormais. Chacun de ces tests a été validé en **réintroduisant le défaut**.

| Garantie | Ce qui ne tenait pas | Verrouillée par |
|---|---|---|
| Purge RGPD exhaustive (D09/D21) | Le module `jobs` était resté un stub M1 : la purge s'interrompait avant l'anonymisation d'audit, ne marquait jamais les demandes purgées, et `saved_jobs` était conservé indéfiniment | `tests/unit/privacy/test_registry.py` (résout **et appelle** chaque purger), `tests/unit/privacy/test_jobs_saved_purge.py`, `tests/integration/test_privacy_purge.py` |
| Export RGPD réellement constitué | `privacy` déclarait un contrat de stockage **async** contre le contrat **sync** livré en M4 ; les archives survivaient aux comptes supprimés | `tests/unit/privacy/test_storage_contract.py`, `tests/unit/privacy/test_expired_exports.py`, `tests/integration/test_privacy_export.py` |
| Rate limiting effectif (D32) | L'identité venait du cookie **présenté** : un cookie aléatoire créait un seau neuf à chaque requête. Tout le trafic anonyme partageait par ailleurs un seul seau derrière le proxy | `tests/unit/test_hardening.py` (limiteur réellement exercé via fakeredis, et non plus seulement sa branche fail-open) |
| Refus de démarrage sur stockage local (D24) | Le garde-fou du worker Celery était un **no-op** ; `ENV=prod` désactivait silencieusement tous les contrôles ; staging n'était pas couvert | `tests/unit/core/test_startup_guards.py`, `tests/unit/core/test_config_env.py` |
| `NoSuchBucket` ≠ objet absent (D24) | Une clause sur le statut HTTP annulait l'exclusion documentée : la purge RGPD rapportait un **succès complet sans rien supprimer** | `tests/unit/core/test_storage_s3.py` |
| Pas de repli implicite vers le factice (D18/D25) | Une panne LLM produisait un CV « analysé » **vide**, sans erreur ni ligne de journal ; le demi-ouvert du disjoncteur renvoyait toute la charge sur un provider en panne | `tests/unit/ai/test_provider_factory.py`, `tests/unit/ai/test_provider_wiring.py` |
| Journal `ai_calls` réellement écrit (D26) | Écritures planifiées sur une boucle fermée avant exécution (journal **vide** pour tout le volume des workers) ; nom de tâche violant l'enum SQL (100 % du journal des explications perdu) | `tests/unit/ai/test_calls_journal.py`, `tests/unit/matching_api/test_explanations_event_loop.py` |
| Anti-invention non contournable (D10/D33) | Une **liste de `claims` vide** faisait passer un corps entièrement inventé pour ancré, donc validable et exportable ; une PATCH sans changement levait l'ancrage et effaçait le verdict | `tests/unit/generation/test_grounding_unit.py`, `tests/unit/generation/test_generation_anchoring.py` |
| Dédup sans perte de données (D13/D28) | Le seuil 0,92, calibré pour des vecteurs sémantiques, fusionnait des offres distinctes sur vecteurs lexicaux (0,949 ; 1,0000 Paris/Lyon) ; le filtre géographique exigé par la spec n'existait pas | `tests/unit/ingestion/test_dedup_stage2.py` (tests de calibration exerçant le provider **réellement en usage** sur du texte réaliste) |
| Recherche full-text utilisable en français | Le déclencheur `tsv` désaccentuait l'index mais pas la requête : « développeur » ne renvoyait rien | `tests/integration/test_jobs_fulltext_trigger.py` |
| Pagination par date fonctionnelle (D30) | `datetime` naïf mappé sur `timestamptz` : 500 sur toute page 2 paginée par date | `tests/integration/test_jobs_search_pagination.py` |
| Déterminisme des vecteurs (D27) | `hash()` natif, randomisé par processus : API et workers auraient écrit des vecteurs divergents | `tests/unit/embeddings/test_hashing_provider.py` |

## Revue de phase — 2026-07-23

- Docs 02–05, 07–10, 13–16 livrés ; conventions d'ID respectées (F-A…F-Q, RM-x-n, AC-x-n, SCR-01…SCR-92, RM-T-1…RM-T-11 pour les règles transverses de 05).
- Contrats API complétés suite à la revue UX : `GET /generations` (bibliothèque, écrans SCR-30/31/32) et `saved_only` sur `GET /jobs` (feature K).
- Contradiction D13/07 sur la clé de dédup résolue (référence employeur) — voir decisions.md et 17 §Résolues.
- D16–D23 intégrés à decisions.md depuis 10-system-architecture.md.

## Revue post-implémentation — 2026-07-28 (M1 → M6)

- Matrice complétée par l'**état réel** feature par feature (module, endpoints, tests nommés) : la matrice d'origine décrivait l'intention, elle décrit désormais aussi ce qui existe.
- Section « Règles transverses » réécrite : chaque garantie est rattachée à un **fichier de test nommé**. « Revue de code » n'est plus un moyen de vérification accepté pour une garantie structurante — le point « score jamais généré par le LLM » est par exemple désormais tenu par une vérification AST **et** sous-processus.
- Ajout d'une section « garanties non tenues, puis corrigées » : **12 garanties** annoncées ne tenaient pas à l'exécution malgré une suite verte. Chacune est verrouillée par un test de non-régression validé en réintroduisant le défaut.
- D24–D33 ajoutées à decisions.md (décisions prises **dans le code** pendant l'implémentation) ; questions Q1–Q50 reclassées et 12 questions nouvelles (N1–N12) ouvertes dans 17.
- Écarts spec ↔ code non corrigeables par la documentation, reportés en questions ouvertes : quota consommé par une génération `failed` (N7, contredit Q28), export RGPD sans les fichiers CV (N8), rétention 13 mois d'`ai_calls` (N4), compte OAuth non supprimable (N5), re-scoring asynchrone des préférences absent (N11).
