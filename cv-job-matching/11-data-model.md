# 11 — Modèle de données

> PostgreSQL 16 + extensions `pgvector`, `pg_trgm`, `unaccent` (D06). Schéma SQL exécutable : `initial-schema.sql`. Diagramme : `data-model.mmd`.
> Dimension d'embedding : 1024 🟡 (dépend du modèle retenu, voir 08 ; changer la dimension = migration).

## 1. Entités et responsabilités

| Groupe | Tables | Rôle |
|---|---|---|
| Identité | `users`, `consents`, `deletion_requests`, `audit_log` | compte, consentements, droit à l'effacement, traçabilité |
| Profil | `profiles`, `profile_experiences`, `profile_educations`, `profile_skills`, `profile_languages`, `cv_documents`, `extraction_runs` | profil canonique versionné avec provenance par champ (D05) |
| Référentiels | `skills`, `skill_aliases`, `sectors` | taxonomie compétences (base ESCO 🟡) et secteurs (NACE simplifié) |
| Préférences | `preferences`, `preference_locations`, `preference_titles`, `preference_sectors`, `preference_companies`, `preference_keywords` | critères de recherche de l'utilisateur |
| Offres | `sources`, `job_postings`, `job_sources`, `job_locations`, `job_skills`, `job_languages` | offre canonique dédupliquée, N sources conservées avec lien original (D13) |
| Matching | `match_results`, `match_explanations` | résultats du moteur + cache des reformulations LLM |
| Actions | `saved_jobs`, `applications`, `application_events`, `generated_documents` | sauvegarde/masquage, suivi de candidatures, contenus générés |
| IA | `prompt_versions`, `ai_calls` | versionnement des prompts, journal d'appels (D08) |

## 2. Décisions de modélisation

- **Provenance par champ** : les tables de profil portent `source` (`cv_extraction`/`user_input`/`user_confirmed`) et `confidence numeric(3,2)`. Un profil ne passe à `status='validated'` que si tous les champs affichés ont `source != 'cv_extraction'` **ou** ont été confirmés en bloc à la validation (l'action de validation promeut `cv_extraction` → `user_confirmed`).
- **Offre canonique vs sources** : `job_postings` est l'entité dédupliquée ; `job_sources` garde une ligne par (source, référence externe) avec `original_url` obligatoire — exigence produit. La suppression d'une source n'efface pas l'offre tant qu'une autre source la référence.
- **`match_results`** : clé `(profile_id, job_posting_id)`, colonne `scoring_version` ; upsert au re-scoring. Détails par dimension en `jsonb` (`dimension_scores`, `blocking_criteria`, `unknown_dimensions`) — lus tels quels par l'API, jamais requêtés analytiquement (un export vers l'entrepôt est prévu post-MVP).
- **Contenus générés** : `generated_documents.content` en `jsonb` (structure par type, validée par l'app) + `based_on_profile_version` pour prouver l'ancrage anti-invention ; `status` ∈ draft/validated/exported.
- **Texte brut des CV et payloads sources** : stockés en objet S3 (`file_key` / `raw_payload_key`), pas en base — la base ne garde que les clés. Justification : volumétrie, purge simple.
- **Suppression de compte** : `users.deleted_at` (soft delete immédiat, compte inaccessible) + `deletion_requests.purge_after` (J+30) ; un job purge physiquement toutes les lignes liées et les objets S3. Les `ai_calls` et `audit_log` sont conservés **anonymisés** (user_id → NULL, hash irréversible en `subject_key`) pour les statistiques.

## 3. Données sensibles et rétention

| Donnée | Sensibilité | Rétention | Notes |
|---|---|---|---|
| CV (fichier + texte extrait) | haute (données personnelles riches) | vie du compte ; purge J+30 après suppression | jamais transmis à un LLM hors tâche d'extraction |
| Profil structuré | haute | idem | attributs sensibles (âge, genre, photo, état civil, santé…) **jamais extraits** — liste d'exclusion au parsing (08 §7) |
| Préférences (salaire, mobilité) | moyenne | idem | |
| Offres publiques | faible | 12 mois après expiration, puis archivage/suppression | données publiques mais licence par source respectée |
| `match_results` | moyenne (dérivée du profil) | purgé avec le compte | |
| Contenus générés | haute | vie du compte ; purge J+30 | |
| `ai_calls` (métadonnées) | faible | 13 mois | sans contenu de prompt ; contenu échantillonné 30 j max pour debug, avec consentement |
| `audit_log` | moyenne | 13 mois | anonymisé à la suppression du compte |

## 4. Index clés (détail dans le SQL)

- `users(email)` unique (citext) ; partout `deleted_at IS NULL` en index partiels.
- `job_postings` : `dedup_hash` unique ; GIN sur `tsv` ; HNSW sur `embedding` ; b-tree partiel `(country_code, status)` WHERE `status='active'` ; trigram sur `(title, company_name)` pour la dédup étage 2.
- `match_results(profile_id, score DESC)` partiel WHERE `blocking = '[]'` pour le tri par défaut.
- `job_sources(source_id, external_ref)` unique — idempotence d'ingestion.
- `applications(user_id, status)` ; `saved_jobs(user_id, state)`.

## 5. Contraintes d'intégrité notables

- `profile_skills` : unique `(profile_id, skill_id)` ; `confidence BETWEEN 0 AND 1`.
- `job_sources.original_url NOT NULL` — garantie produit « lien d'origine toujours conservé ».
- `generated_documents` : CHECK `status <> 'exported' OR validated_at IS NOT NULL` — un export exige une validation (D10).
- `applications` : CHECK qu'une candidature référence soit `job_posting_id`, soit un couple (`external_title`, `external_company`) pour les offres hors plateforme.
- Enums PostgreSQL natifs pour tous les vocabulaires fermés (statuts, contrats, remote, CECRL, séniorité) — la validation applicative Pydantic reste la première ligne.
