# 13 — Stratégie de test

> Couvre le monolithe FastAPI + workers Celery (D01, D12), le moteur déterministe (D02, 06), la couche IA (D08) et le front Next.js (D11).
> Principe directeur : **tout ce qui est déterministe est testé de façon déterministe** (moteur, dédup, normalisation) ; **tout ce qui passe par un LLM est testé par jeux de référence avec seuils** (jamais d'assertion d'égalité exacte sur du texte généré).

---

## 1. Pyramide et responsabilités

| Niveau | Part cible 🟡 | Durée cible CI | Responsable | Quand |
|---|---|---|---|---|
| Unitaires (backend + front) | ~70 % des tests | < 3 min | dev auteur | chaque PR |
| Intégration (API + DB réelle, workers, ingestion) | ~20 % | < 10 min | dev auteur + QA | chaque PR |
| E2E Playwright (parcours critiques) | ~8 % | < 15 min | QA Lead | chaque PR sur `main`, sinon nightly |
| Évaluation matching + prompts (jeux de référence) | ~2 % en CI (échantillon) | < 10 min CI / complet nightly | QA Lead + PO | PR touchant `matching/`, `ai/`, `scoring-config.json`, prompts ; nightly complet |
| Charge (k6 🟡) et sécurité dynamique | hors pyramide | — | DevOps | pré-release + hebdo |

**Outillage** : `pytest` + `pytest-cov` (coverage), `mypy --strict` sur `matching/` et `ai/` (graduel ailleurs), `ruff` (lint + format), `testcontainers-python` (PostgreSQL 16 + pgvector, Redis), `Playwright` (E2E, traces activées), `schemathesis` 🟡 contre `openapi.yaml`, `k6` 🟡 pour la charge, `pip-audit` + `npm audit` en CI. Front : `vitest` + Testing Library pour les composants, Zod testé par mêmes fixtures que Pydantic (contrats partagés).

---

## 2. Tests unitaires

### 2.1 Moteur de matching (`matching/engine.py`) — cas de référence chiffrés

Chaque dimension a sa suite avec des cas **calculés à la main et gelés** (golden cases). La config chargée est `scoring-config.json` réel — les tests cassent si un seuil change sans mise à jour assumée. Extraits obligatoires :

| ID | Cas | Entrées | Attendu |
|---|---|---|---|
| UM-01 | Score parfait | 12 dimensions connues, s=1,0, q=1,0 | `score=100`, `confidence=100`, 0 bloquant |
| UM-02 | Renormalisation sur le connu | connues : skills_required s=0,8 (w25), title s=1,0 (w15), location s=1,0 (w8) ; reste k=0 | `score = round(100×43/48) = 90` ; `unknown_dimensions` = 9 entrées ; `low_data=false` (48 ≥ 40) |
| UM-03 | `low_data` | seule skills_required connue (Σw·k = 25 < 40) | `low_data=true`, score calculé et retourné quand même |
| UM-04 | Confiance | mêmes connues qu'UM-02, q = 0,9 / 1,0 / 0,8 | `confidence = round(22,5+15+6,4) = 44` |
| UM-05 | Plancher d'extraction | séniorité offre extraite avec conf. 0,45 (< `extraction_confidence_floor` 0,5) | dimension traitée `k=0`, jamais utilisée comme fait |
| UM-06 | Couverture compétences | 4 requises : 2 exactes, 1 proche (cos ≥ 0,75), 1 absente | `s = (2 + 0,5)/4 = 0,625` ; details `matched/related/missing` nominatifs |
| UM-07 | Similarité métier (affine) | sim = 0,675 | `s = (0,675−0,55)/0,25 = 0,5` ; bornes : 0,55→0 ; 0,80→1 |
| UM-08 | Séniorité | offre senior(3), candidat lead(4) → Δ=−1 | `s = 0,8` ; offre senior(3), candidat confirmé(2) → Δ=+1 → `s = 0,6` |
| UM-09 | Expérience sous le min | 3 ans pour min 5 | `s = max(0 ; 3/5 − 0,2) = 0,4` |
| UM-10 | Expérience au-dessus du max | 10 ans, max 7 | `s = max(0,7 ; 1 − 0,05×3) = 0,85` |
| UM-11 | Localisation décroissance | d = 45 km, rayon 30 | `s = (60−45)/30 = 0,5` ; d = 70 km + sur-site strict → `s=0` + bloquant `location_incompatible` |
| UM-12 | Matrice télétravail | candidat `requis` × offre `onsite` | `s=0` + bloquant `remote_required` ; candidat `indifférent` → toujours 1,0 |
| UM-13 | Langues | requis EN C1, candidat B2 → 0,5 ; candidat B1 → 0 + bloquant `language_missing` |
| UM-14 | Salaire recouvrement | candidat [45–55 k€], offre [50–60 k€] | `s = 5/10 = 0,5` ; max offre 45 k€ < min strict 50 k€ → bloquant `salary_below_minimum` |
| UM-15 | Bloquant ≠ score nul | UM-02 + bloquant contrat strict | score inchangé (90), bloquant listé séparément |
| UM-16 | Plancher bloquant | politique `onsite` extraite avec conf. 0,65 (< `blocking_confidence_floor` 0,7) | rétrogradé en avertissement, jamais bloquant |
| UM-17 | Profil sans donnée d'un côté | offre sans `skills_required` | `k=0` (jamais s=0) — donnée manquante ≠ mauvais match |
| UM-18 | `scoring_version` | tout résultat | estampillé `1.0.0`, égal à la config chargée |

Compléments : tests par propriétés (`hypothesis` 🟡) — le score reste dans [0,100], la renormalisation est invariante à l'ordre des dimensions, retirer une dimension inconnue ne change rien.

### 2.2 Autres unités backend
- **Déduplication (D13)** : étage 1 — même hash pour casse/accents/espaces variables (`unaccent` + normalisation) ; étage 2 — paire au cosinus 0,93 fusionnée, 0,91 non fusionnée (seuil 0,92 🟡) ; fusion conserve **tous** les `original_url` ; idempotence par `(source_id, external_ref)`.
- **Normalisation** : mapping alias→taxonomie (`React.js`→`react`), CECRL (natif=C2), séniorité par règles multilingues FR/EN, conversion salaire EUR annuel (fourchette ouverte ±15 %), fusion des chevauchements d'expériences (arrondi 0,5 an).
- **Validation Pydantic** : chaque schéma de `ai-output-schemas.json` — payload valide accepté, champ additionnel rejeté (`additionalProperties: false`), `evidence.quote` obligatoire, dates au motif `^\d{4}(-\d{2})?$`, séquence retry→repair→échec propre simulée.
- **Règles d'explication (06 §6)** : `strength` ssi s ≥ 0,8 et w ≥ 6 ; `gap` ssi s ≤ 0,4 ; bloquants toujours en tête.
- **Front** : composants score/confiance/badges (états low_data, bloquant, inconnu), schémas Zod, machines d'état de génération (draft→validated→exported).

---

## 3. Tests d'intégration

Environnement : `testcontainers` (PostgreSQL 16 + `pgvector`/`pg_trgm`/`unaccent`, Redis) ; migrations appliquées à chaque run ; Celery en mode worker réel dédié aux tests (pas `task_always_eager` pour les suites de fiabilité).

- **API contre base réelle** : chaque endpoint de `12-api-contracts.md` — CRUD profil avec provenance, `POST /profile/validate` (refus si < 3 compétences ; promotion `cv_extraction`→`user_confirmed`), pagination par curseur stable, idempotence (`Idempotency-Key` rejouée → `Idempotent-Replay: true`), erreurs RFC 9457 avec `trace_id`, contrainte SQL `status <> 'exported' OR validated_at IS NOT NULL`.
- **`schemathesis` 🟡 contre `openapi.yaml`** : conformité réponses/schémas, fuzzing des paramètres de `GET /jobs`, absence de 500 non contrôlé. Exécution nightly + pré-release (trop long pour chaque PR).
- **Workers Celery** : parsing CV bout-en-bout (upload → 202 → statut), retries exponentiels sur échec provider simulé, idempotence des tâches (re-livraison Redis), files séparées `ingestion`/`ai`/`scoring` respectées, invalidation `scoring_version` → re-scoring paresseux + batch.
- **Pipeline d'ingestion, sources mockées** : connecteurs France Travail / Greenhouse / Lever 🟡 avec fixtures de payloads réels anonymisés — normalisation, dédup inter-sources, `original_url NOT NULL`, offre conservée tant qu'une source la référence, gestion quota/erreurs source (backoff, pas de perte).
- **Recherche hybride (D07)** : filtres SQL + `tsvector` fr/en + rerank pgvector sur corpus de 200 offres de test ; `include_blocked=true` par défaut (badgées, jamais retirées).

---

## 4. E2E (Playwright)

Parcours critiques, données seedées, LLM remplacé par un **provider factice déterministe** derrière l'interface `LLMProvider` (mêmes schémas de sortie) — aucun appel LLM réel en E2E :

| ID | Parcours | Assertions clés |
|---|---|---|
| E2E-01 | Inscription → consentements → upload CV → correction 2 champs → validation profil | provenance/badges visibles, profil `validated` |
| E2E-02 | Recherche + filtres → vue offre → score + confiance → ouverture explication | deux chiffres distincts affichés, source + lien d'origine présents, bloquant badgé jamais masqué silencieusement |
| E2E-03 | Génération lettre → diff/relecture → édition → validation → export PDF | export impossible avant validation (409 relayé), claims d'ancrage affichés |
| E2E-04 | Création candidature → transitions de statut → historique | historisation `application_events` |
| E2E-05 | Export RGPD → suppression de compte (mot de passe) → login refusé | soft delete immédiat, `deletion_requests.purge_after` = J+30 |

Navigateurs : Chromium en PR ; +Firefox/WebKit en nightly. Accessibilité : axe-core intégré aux parcours (0 violation critique WCAG 2.1 AA).

---

## 5. Tests de sécurité

- **Authorization** : suite systématique « utilisateur B accède aux ressources de A » sur **tous** les endpoints scopés → 404 attendu (jamais 403, anti-énumération, 12 §5). Générée depuis l'inventaire OpenAPI pour ne rater aucun endpoint nouveau.
- **Rate limiting** : dépassement des quotas (60/min global, 30/min recherche, 10/h générations, 5/j upload, 2/j export) → 429 + `Retry-After` ; vérif par utilisateur puis par IP ; non-contournement via nouvelles sessions.
- **Upload malveillant** : polyglottes (PDF+HTML), magic bytes falsifiés, zip bomb DOCX, > 10 Mo, EICAR (scan ClamAV 🟡), PDF chiffré, XML externe (XXE) dans DOCX → rejet propre, aucun crash worker.
- **Injection de prompt (jeu adversarial, R5)** : corpus versionné de CV et d'offres piégés (« ignore les instructions », exfiltration du system prompt, instructions cachées en blanc/métadonnées PDF, HTML dans description d'offre). Attendu : sortie toujours conforme au schéma, aucune instruction exécutée, aucun contenu du system prompt dans la sortie. Taux de résistance cible : 100 % sur le jeu connu, gate bloquant.
- **Dépendances (CI)** : `pip-audit`/`npm audit` bloquants sur CVE critique/haute sans correctif appliqué ; images Docker scannées (trivy 🟡).
- **Divers** : CSRF (mutation sans token → 403), cookies `httpOnly Secure SameSite=Lax`, aucune donnée personnelle dans les URLs ni les logs (assertion sur logs capturés en intégration).

---

## 6. Tests du matching (jeu annoté — réf. 06 §5)

- **Jeu** : `eval-set-v1` gelé — 500 paires (20 profils × 25 offres), 3 annotateurs/paire, pertinence 0–4, Krippendorff α ≥ 0,65, stratifié verticales × présence de données.
- **Gates CI** (source : `scoring-config.json#evaluation_gates` — inchangés, bloquants) :

| Gate | Seuil |
|---|---|
| Spearman(score, médiane annotateurs) | ≥ 0,60 |
| NDCG@10 (classement par profil) | ≥ 0,75 |
| Précision bloquants | ≥ 0,95 |
| Rappel bloquants | ≥ 0,85 |
| Régression Spearman vs run de référence | ≤ 0,02 |

- **Déclenchement** : toute PR modifiant `matching/`, `scoring-config.json` ou les normalisations → run complet en CI, rapport archivé (artefact) référencé `scoring_version` + `eval-set-vX`.
- **Calibration de la confiance** : les paires du quartile bas de `confidence` doivent concentrer les erreurs — |erreur| moyenne du quartile bas > quartile haut 🟡 (test statistique, alerte non bloquante au MVP).
- **Invariance biais (R8)** : test automatique — retirer/permuter prénom, nom, adresse, photo des profils du jeu → **scores strictement identiques au bit près** (trivialement vrai car hors entrées du moteur ; le test garantit que ça le reste). Gate bloquant : 0 différence. Complément : équilibre des prénoms F/H dans les profils synthétiques vérifié à la constitution du jeu.

---

## 7. Tests des prompts (couche IA, D08)

Un jeu de référence versionné **par tâche** (`extract_cv`, `extract_job`, `explain_match`, `generate_letter`, `generate_email`, `tailor_cv`, `optimize_cv`) :

| Tâche | Jeu | Contrôles automatiques |
|---|---|---|
| `extract_cv` | 60 CV 🟡 : FR/EN, 1–3 colonnes, PDF scannés/difficiles, DOCX, juniors/seniors/reconversions | F1 champs vs annotation ≥ 0,85 🟡 ; **0 attribut sensible extrait** ; `evidence.quote` présent et retrouvé dans le texte source |
| `extract_job` | 80 offres 🟡 FR/EN, avec/sans salaire/séniorité | exactitude des champs critiques (contrat, remote, langues) ≥ 0,9 🟡 ; jamais d'exigence inférée présentée comme un fait |
| `explain_match` | 40 jeux d'`explanation_facts` | **0 chiffre ou fait absent des facts** (diff des valeurs numériques, 06 §6) |
| `generate_letter` / `email` / `tailor_cv` / `optimize_cv` | 30 couples (profil validé, offre) par tâche 🟡 | extraction de claims + contrôle d'ancrage : **0 invention détectée** ; langue de sortie = langue demandée |
| Toutes | + cas adversariaux (§5) | `schema_error < 5 %` après retry/repair ; résistance injection 100 % |

**Seuils bloquants release** : `0 invention détectée` et `schema_error < 5 %` (alignés brief §8). Exécution : **CI sur échantillon** (10 cas/tâche, sélection fixe) à chaque PR touchant `ai/` ou `prompt_versions` ; **nightly complet** sur tout le jeu, avec suivi de tendance par `prompt_version` × `model` (détection de dérive provider). Chaque run journalise coût et latence (budget nightly < 15 € 🟡).

---

## 8. Jeux de données de référence

| Jeu | Contenu | Taille | Anonymisation | Versionnement |
|---|---|---|---|---|
| `eval-set-vX` | paires (profil, offre) annotées | 500 paires | profils synthétiques + volontaires anonymisés (nom/coordonnées fictifs) | gelé par version, guide d'annotation inclus |
| `cv-corpus-vX` | CV réels difficiles + synthétiques | 60 🟡 | consentement écrit des volontaires, remplacement nom/adresse/téléphone/email par valeurs fictives cohérentes | git LFS 🟡, checksum |
| `job-corpus-vX` | offres réelles des connecteurs | 200 (80 annotées) | données publiques ; licence par source vérifiée (R1) | snapshot daté |
| `adversarial-vX` | injections, uploads malveillants | ≥ 40 cas, enrichi en continu | contenu synthétique | ajout = jamais de suppression |
| Fixtures intégration | payloads connecteurs, profils seed | ~50 | synthétiques | dans le repo |

Règles : aucun jeu ne contient de donnée personnelle réelle non consentie ; stockage UE ; revue à chaque ajout ; toute évolution d'un jeu = nouvelle version (jamais de modification en place) pour garder les comparaisons de runs valides.

---

## 9. Seuils de qualité bloquants pour la release

| # | Contrôle | Seuil bloquant | Vérifié par |
|---|---|---|---|
| Q1 | Couverture `matching/`, dédup, normalisation | ≥ 90 % lignes 🟡 | pytest-cov |
| Q2 | Couverture backend global | ≥ 80 % 🟡 | pytest-cov |
| Q3 | `mypy` (`matching/`, `ai/`) + `ruff` | 0 erreur | CI |
| Q4 | Gates matching (§6) | Spearman ≥ 0,6 ; NDCG@10 ≥ 0,75 ; précision bloquants ≥ 0,95 ; rappel ≥ 0,85 ; régression ≤ 0,02 | run éval CI |
| Q5 | Invariance biais | 0 différence de score | run éval CI |
| Q6 | Prompts | 0 invention ; schema_error < 5 % ; injection 100 % résistée | nightly + pré-release |
| Q7 | E2E-01…05 | 100 % verts, Chromium+Firefox | Playwright |
| Q8 | Authz croisée | 100 % des endpoints scopés → 404 | suite sécurité |
| Q9 | Suppression compte | purge effective simulée J+30 vérifiée (brief §8) | test automatisé dédié |
| Q10 | Offres affichées | 100 % avec source + `original_url` | intégration + E2E |
| Q11 | Charge k6 🟡 | p95 `GET /jobs` < 500 ms à 50 VU ; p95 `GET /jobs/{id}/match` < 200 ms 🟡 ; 0 erreur 5xx | k6 pré-release |
| Q12 | Dépendances | 0 CVE critique/haute sans correctif | pip-audit / npm audit |
| Q13 | Accessibilité | 0 violation axe-core critique | E2E |

---

## Questions ouvertes

1. Le scan antivirus (ClamAV 🟡) est-il exigé dès l'alpha fermée ou seulement à l'ouverture publique ?
2. Quel budget mensuel LLM pour les runs nightly de prompts (échantillonnage vs jeu complet quotidien) ?
3. Les CV volontaires anonymisés nécessitent-ils une revue DPO avant intégration au corpus (statut juridique de l'anonymisation) ?
4. Le seuil F1 ≥ 0,85 sur `extract_cv` est-il compatible avec H2 (≤ 20 % de champs corrigés) — à recaler après les 20 premiers CV réels ?
5. schemathesis en PR (plus lent) ou uniquement nightly — décision après mesure du temps réel de run ?
6. Faut-il un environnement de staging avec vraies clés provider pour un smoke test LLM pré-release, et qui le paie ?
