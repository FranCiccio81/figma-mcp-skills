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
