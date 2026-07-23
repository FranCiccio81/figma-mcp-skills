# 14 — Plan analytics

> Objectif : mesurer les métriques de succès du brief (§8) et instruire H1–H6 (§6), sans jamais collecter de contenu personnel.
> Outil : self-hosted 🟡 type **PostHog EU** (instance hébergée UE, D09), events envoyés côté serveur autant que possible (fiabilité, pas d'adblock).

---

## 1. Principes de collecte

- **Pseudonymisation** : `user_id` analytics = UUID applicatif distinct de l'email, jamais relié en clair dans l'outil ; à la suppression du compte, les événements sont supprimés ou dissociés (alignement purge J+30).
- **Aucun contenu personnel dans les événements** : pas de texte de CV, pas de noms, pas d'intitulés d'expériences, pas de contenu généré, pas de requête de recherche en texte libre (seulement sa longueur et la présence de filtres), pas de salaire exact (tranches).
- **IDs techniques uniquement** : `job_id`, `generation_id`, `source_id` — jamais le titre de l'offre côté propriétés candidat.
- **Server-side d'abord** : les événements métier (import, validation, génération, statut) sont émis par le backend au moment de la transaction ; le front n'émet que les événements de consultation (vue, ouverture, clic).
- **Consentement** : événements produit essentiels (base légale : intérêt légitime, à confirmer par DPO 🟡) ; tout tracking au-delà (session replay — exclu au MVP) exigerait un consentement explicite.

## 2. Taxonomie d'événements (snake_case)

| Événement | Déclencheur | Propriétés (extrait) | Émetteur |
|---|---|---|---|
| `user_signed_up` | compte créé (`POST /auth/register`) | `consents[]` (types cochés), `locale` | serveur |
| `cv_upload_started` | `POST /cv-documents` accepté | `file_type` (pdf/docx), `file_size_kb` | serveur |
| `cv_import_succeeded` | parsing terminé OK | `duration_ms`, `fields_extracted_count`, `low_confidence_fields_count`, `warnings_count` | serveur |
| `cv_import_failed` | parsing en échec | `error_code` (schema_error, unreadable, timeout) | serveur |
| `profile_field_corrected` | édition d'un champ issu de `cv_extraction` | `field_group` (experience/skill/language/education/root), `was_low_confidence` (bool) | serveur |
| `profile_validated` | `POST /profile/validate` OK | `minutes_since_import` (arrondi), `corrected_fields_count`, `skills_count` | serveur |
| `preferences_updated` | `PUT /preferences` | `locations_count`, `remote_pref`, `has_strict_salary` (bool), `contracts_count` | serveur |
| `job_search_performed` | `GET /jobs` (première page) | `has_query` (bool), `query_length`, `filters_used[]` (noms seulement), `sort`, `results_count` | serveur |
| `job_viewed` | ouverture détail offre | `job_id`, `source_id`, `score_bucket` (0–39/40–59/60–79/80–100), `confidence_bucket`, `has_blocking` (bool), `low_data` (bool), `position_in_list` | front |
| `match_explanation_opened` | ouverture panneau explication | `job_id`, `score_bucket`, `llm_reformulation_requested` (bool) | front |
| `job_saved` / `job_hidden` | `PUT /jobs/{id}/saved-state` | `job_id`, `score_bucket`, `has_blocking` | serveur |
| `generation_requested` | `POST /generations` | `doc_type` (email/cover_letter/cv_variant/cv_optimization), `job_id?`, `language`, `tone` | serveur |
| `generation_completed` | brouillon prêt | `generation_id`, `doc_type`, `duration_ms`, `anchoring_status` (passed/failed), `prompt_version` | serveur |
| `generation_edited` | `PATCH /generations/{id}` | `generation_id`, `edit_count_bucket` | serveur |
| `generation_validated` | `POST /generations/{id}/validate` | `generation_id`, `doc_type`, `minutes_since_draft` (arrondi) | serveur |
| `generation_exported` | `POST /generations/{id}/export` | `generation_id`, `doc_type`, `format` (copy/pdf/docx) | serveur |
| `application_created` | `POST /applications` | `application_id`, `is_external` (bool), `has_generation` (bool) | serveur |
| `application_status_updated` | `POST /applications/{id}/status` | `application_id`, `from_status`, `to_status` | serveur |
| `data_export_requested` | `POST /privacy/export` | — | serveur |
| `account_deletion_requested` | `DELETE /account` | `days_since_signup`, `reason_code?` (choix fermé optionnel) | serveur |

Conventions : horodatage UTC serveur ; `schema_version` sur chaque événement ; toute nouvelle propriété passe par revue « pas de donnée personnelle » (checklist PR).

## 3. Mapping événements → métriques du brief (§8) et hypothèses H1–H6

| Métrique / hypothèse | Seuil (brief — inchangé) | Formule de calcul |
|---|---|---|
| **Activation** | ≥ 60 % | `count_distinct(user_id ayant profile_validated)` ÷ `count_distinct(user_id ayant user_signed_up)` — cohorte par semaine d'inscription |
| **Cœur de valeur / H1** | ≥ 40 % des actifs hebdo | `WAU avec ≥ 1 match_explanation_opened` ÷ `WAU` (WAU = ≥ 1 événement quelconque sur 7 j glissants). Vue complémentaire (test H1 du §6) : `count(match_explanation_opened)` ÷ `count(job_viewed)` ≥ 40 % + interviews qualitatives |
| **Qualité matching / H6** | Spearman ≥ 0,6 ; 0 bloquant > 60 sans avertissement | **hors analytics produit** : Spearman issu des runs d'évaluation CI (13 §6) ; le contrôle « 0 offre bloquante > 60 sans avertissement » est un test automatisé + monitoring backend (`match_results` où `score > 60` et `blocking ≠ []` → l'UI doit badger, vérifié en E2E) |
| **H2 — parsing** | ≤ 20 % champs corrigés ; ≥ 70 % validés < 10 min | `sum(corrected_fields_count)` ÷ `sum(fields_extracted_count)` sur `profile_validated` ; part des `profile_validated` avec `minutes_since_import < 10` |
| **H3 — densité** | ≥ 30 offres à score ≥ 60 / profil actif | **métrique backend** (pas un événement) : requête quotidienne sur `match_results` — médiane par profil validé actif du `count(score ≥ 60 AND blocking = [])` ; exposée dans le dashboard |
| **Génération / H4** | ≥ 50 % exportés ; 0 invention | `count_distinct(generation_id avec generation_exported)` ÷ `count_distinct(generation_id avec generation_completed)` , par `doc_type` ; « 0 invention » vient de la CI prompts (13 §7), pas des analytics |
| **H5 — suivi manuel** | ≥ 40 % | `count_distinct(application_id avec ≥ 1 application_status_updated)` ÷ `count_distinct(application_id créées)` , fenêtre 30 j après création |
| **Rétention** | ≥ 25 % en semaine 4 | cohorte hebdo : `users actifs en S+4` ÷ `users de la cohorte S0` (actif = ≥ 1 événement) |
| **Conformité** | suppression ≤ 30 j ; 100 % offres sourcées | tests automatisés (13 Q9/Q10) + compteur `account_deletion_requested` vs purges exécutées (job de réconciliation, alerte si écart) |

Métriques d'exploitation complémentaires : taux `cv_import_failed` (< 5 % 🟡), `anchoring_status=failed` (alerte si > 1 %), latence p95 de génération, répartition `score_bucket` des `job_viewed` (santé de la densité).

## 4. Dashboards MVP et cadence

| Dashboard | Contenu | Audience | Revue |
|---|---|---|---|
| **Funnel d'activation** | signed_up → cv_import_succeeded → profile_validated → première recherche → première explication | PO + équipe | hebdo |
| **Cœur de valeur** | H1 (deux vues), H3 (densité backend), répartition des scores vus, saved/hidden | PO | hebdo |
| **Génération** | H4 par doc_type, taux d'édition avant validation, anchoring failed | PO + QA | hebdo |
| **Candidatures & rétention** | H5, cohortes S1–S4 | PO | hebdo |
| **Santé technique** | imports échoués, schema_error, latences, quota rate-limit atteints | DevOps | quotidien (alertes) + hebdo |

Cadence : revue produit hebdomadaire (30 min, décisions consignées dans `decisions.md`) ; bilan hypothèses H1–H6 à chaque fin de jalon (15-delivery-roadmap) ; en alpha fermée, revue bi-hebdomadaire avec verbatims utilisateurs.

## 5. Gouvernance RGPD des analytics

- **Outil** : PostHog self-hosted 🟡 (ou équivalent) sur infrastructure UE — aucune donnée analytics ne quitte l'UE (D09) ; pas de SaaS US même « EU cloud » sans revue DPO.
- **Base légale** : intérêt légitime pour les événements produit essentiels listés §2 (à confirmer par le DPO 🟡, mention claire dans la politique de confidentialité) ; bannière de consentement requise si ajout de tout traceur non essentiel.
- **Rétention** : événements bruts **13 mois** maximum (aligné `ai_calls`/`audit_log`, 11 §3), agrégats anonymes conservables au-delà.
- **Droits** : suppression de compte → suppression/dissociation des événements dans le job de purge J+30 ; l'export RGPD (art. 20) inclut la liste des types d'événements collectés 🟡.
- **Minimisation** : checklist de revue à chaque nouvel événement (pas de texte libre, pas d'identifiant externe, buckets plutôt que valeurs exactes) ; audit trimestriel d'un échantillon d'événements réels.
- **Documentation** : le traitement analytics figure au registre des traitements et dans la DPIA pré-lancement (D09).

---

## Questions ouvertes

1. Intérêt légitime vs consentement pour les événements produit essentiels : arbitrage DPO requis avant l'alpha (impacte la bannière et le taux de collecte).
2. PostHog self-hosted : qui opère l'instance (charge DevOps réelle) — alternative légère (events en Postgres + Metabase 🟡) acceptable au MVP ?
3. Faut-il inclure `job_id` dans les événements côté candidat, ou un hash, pour réduire encore le risque de ré-identification par croisement ?
4. La métrique H3 (backend) doit-elle être calculée sur tous les profils validés ou seulement les actifs 7 j (définition d'« actif » à figer avant l'alpha) ?
5. `reason_code` à la suppression de compte : liste fermée à définir avec l'UX (valeur produit vs friction au départ).
