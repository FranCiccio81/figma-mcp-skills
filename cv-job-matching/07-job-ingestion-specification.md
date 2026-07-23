# 07 — Spécification de l'ingestion des offres

> Périmètre : modules `ingestion` et `jobs` (D01). Connecteurs explicitement autorisés uniquement (D04), déduplication déterministe à deux étages (D13), zéro LLM dans la boucle chaude sauf extraction de secours (voir 08).
> Statut : v1.0 — 2026-07-23. Hypothèses de travail marquées 🟡.

---

## 1. Principes directeurs

1. **Un connecteur = une source homologuée** : aucune source n'est activée (`sources.active = true`) sans fiche de conformité approuvée (§3). Pas de crawler générique (D04, risque R1).
2. **Idempotence par clé naturelle** : `(source_id, external_ref)` — contrainte UNIQUE sur `job_sources` (schéma SQL). Ré-ingérer un flux entier ne crée jamais de doublon.
3. **Payload brut conservé** : chaque réponse d'API est archivée en S3 (`job_sources.raw_payload_key`) avant toute transformation — rejouabilité et audit.
4. **Lien d'origine toujours conservé** : `job_sources.original_url NOT NULL` — garantie produit (100 % des offres affichées avec source + lien, métrique de conformité du brief §8).
5. **Aucune affirmation juridique dans le code** : la base légale de chaque source est documentée dans `sources.legal_basis` et fait l'objet d'une revue juridique — ce document ne se substitue pas à cette revue.

---

## 2. Registre des sources MVP 🟡

La liste initiale des connecteurs est une hypothèse de travail (D04 🟡). Chaque fiche ci-dessous est un **résumé** ; la fiche de conformité complète (S3, référencée par `sources.legal_basis`) fait foi.

### 2.1 API France Travail — Offres d'emploi (connecteur prioritaire, R6)

| Champ | Valeur |
|---|---|
| Slug | `france-travail` |
| Nature | API publique conventionnée (`kind = 'public_api'`), accès via la plateforme francetravail.io, authentification OAuth2 client_credentials |
| Base légale / licence | Accès soumis à l'acceptation des CGU de la plateforme et, selon le volume, à une convention. Conditions exactes de réutilisation des données (affichage, cache, durée de rétention, mention de la source) **à confirmer par revue juridique** avant activation |
| Quota | Défini par les CGU/convention de l'API 🟡 — hypothèse de dimensionnement : quelques requêtes/seconde avec pagination ~150 offres/page ; le connecteur lit dynamiquement les en-têtes de rate-limit et s'y adapte |
| Fraîcheur | Filtres de recherche par date de création/actualisation → fetch incrémental natif ; objectif : offre visible chez nous < 6 h après publication 🟡 |
| Champs disponibles | intitulé, description, entreprise (nom, parfois SIRET/secteur ROME), lieu (code INSEE + libellé + lat/lon souvent fournis), type de contrat (CDI/CDD/MIS…), expérience exigée, salaire (libellé semi-structuré), qualification, langues, compétences (référentiel ROME), télétravail (champ dédié partiel), dates de création/actualisation, URL d'origine |
| Couverture | France entière, forte densité hors tech pur — cœur du lancement vertical FR |

### 2.2 Greenhouse Job Board API (flux ATS publics)

| Champ | Valeur |
|---|---|
| Slug | `greenhouse` |
| Nature | `kind = 'ats_feed'`. API JSON publique par employeur : `GET https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs?content=true`. **Chaque board (= chaque entreprise) est activé explicitement** : table de configuration `connector_boards` (board_token, entreprise, date d'activation, référence de la vérification) — jamais d'énumération/découverte automatique de boards |
| Base légale / licence | Les offres sont exposées publiquement par l'employeur via une API documentée par Greenhouse à des fins d'intégration. Le droit de ré-agréger et réafficher ces offres (ToS Greenhouse + position de chaque employeur) est **à confirmer par revue juridique** ; en cas de doute sur un employeur : opt-in explicite demandé à l'employeur |
| Quota | Pas de quota contractuel connu 🟡 — politesse imposée par nous : ≤ 1 requête/s par board, 1 fetch complet par board et par cycle |
| Fraîcheur | Pas de filtre incrémental → fetch complet du board à chaque cycle (volume faible par board : 10–500 offres) ; champ `updated_at` par offre utilisé pour ne re-normaliser que le modifié |
| Champs disponibles | `id` (external_ref), `title`, `content` (HTML), `location.name` (texte libre), `departments`, `offices`, `absolute_url` (original_url), `updated_at`, métadonnées custom variables selon l'employeur. **Pas** de salaire ni de type de contrat structurés dans la plupart des cas → extraction §5.2 |

### 2.3 Lever Postings API (flux ATS publics)

| Champ | Valeur |
|---|---|
| Slug | `lever` |
| Nature | `kind = 'ats_feed'`. API JSON publique par employeur : `GET https://api.lever.co/v0/postings/{site}?mode=json`. Même règle que Greenhouse : **chaque site/entreprise est activé explicitement** dans `connector_boards`, pas de découverte automatique |
| Base légale / licence | Flux exposé publiquement par l'employeur pour intégration ; conditions de ré-agrégation **à confirmer par revue juridique** (ToS Lever + employeur) |
| Quota | Pas de quota contractuel connu 🟡 — ≤ 1 requête/s, 1 fetch complet par site et par cycle |
| Fraîcheur | Fetch complet par cycle ; `createdAt` (epoch ms) par offre pour datation |
| Champs disponibles | `id` (external_ref), `text` (titre), `descriptionPlain`/`description`, `categories` (`location`, `commitment` ≈ type de contrat, `team`), `workplaceType` (`remote`/`hybrid`/`onsite` — structuré, fiable), `hostedUrl` (original_url), `createdAt`, parfois `salaryRange` structuré |

### 2.4 Option partenaire (si signé avant le lancement)

| Champ | Valeur |
|---|---|
| Slug | `partner-<nom>` |
| Nature | `kind = 'partner'` — flux fourni contractuellement (API dédiée, dump S3/SFTP quotidien, ou webhook) |
| Base légale / licence | Contrat de partenariat : périmètre d'usage, durée de rétention, attribution, résiliation — **rédigé et validé par revue juridique** avant tout développement |
| Quota / fraîcheur / champs | Définis au contrat ; le connecteur est développé après signature, en suivant le processus §3 |

---

## 3. Homologation d'une nouvelle source

### 3.1 Fiche de conformité (obligatoire, une par source)

Document versionné (repo + résumé dans `sources.legal_basis`), contenant :

1. **Identité** : nom, éditeur, URL, type (API publique / flux ATS / partenaire / autre).
2. **Base légale d'accès** : CGU/ToS (copie datée archivée), convention ou contrat, mentions robots.txt le cas échéant. Toute conclusion juridique porte la mention « validé par revue juridique le JJ/MM/AAAA » ou « à confirmer ».
3. **Droits d'usage** : réaffichage autorisé ? cache autorisé et durée ? attribution exigée ? restrictions commerciales ?
4. **Contraintes techniques** : authentification, quotas, pagination, format, incrémental possible.
5. **Qualité attendue** : champs disponibles vs champs `job_postings`, taux estimé de champs manquants (impacte l'indice de confiance, D03).
6. **Volumétrie estimée** : offres actives, offres nouvelles/jour.
7. **Risques et plan de retrait** : que faire si la source révoque l'accès (les offres passent `withdrawn`, les `job_postings` multi-sources survivent).

### 3.2 Checklist d'activation

- [ ] Fiche de conformité complète
- [ ] **Revue juridique : avis écrit favorable** (bloquant — R1)
- [ ] Revue technique : connecteur implémenté avec les 6 obligations du §4 (incrémental si possible, idempotence, payload S3, retries, circuit breaker, détection d'expiration)
- [ ] Mapping de normalisation (§5.1) revu par le Data Engineer référent
- [ ] Test d'ingestion sur environnement de staging : ≥ 100 offres, 0 doublon intra-source, échantillon de 20 offres vérifié manuellement
- [ ] Métriques et alertes de la source branchées (§7.3)
- [ ] Approbation finale : Product + Engineering + Juridique → `sources.active = true` (opération tracée dans `audit_log`)

### 3.3 Revue périodique

- Trimestrielle (cadence D04) : re-vérification des ToS (diff sur la copie archivée), des quotas, du taux d'erreur et de la qualité.
- Immédiate en cas de : changement de ToS détecté, mise en demeure, taux d'erreur > seuil (§7.2) pendant 7 jours.
- Désactivation (`active = false`) : le scheduler ignore la source ; les offres mono-source passent `withdrawn` après le délai d'expiration standard (§4.6).

---

## 4. Pipeline d'ingestion

### 4.1 Architecture

Workers Celery (D12), file dédiée `ingestion`. Chaîne par source :

```
Celery beat ──> fetch_source(source_slug)          # 1 tâche par cycle et par source
                  └─> pour chaque page/board :
                      fetch_page(...) ──> pour chaque offre :
                          upsert_raw(source_id, external_ref, payload)   # S3 + job_sources
                              └─> si nouveau ou modifié :
                                  normalize_job(job_source_id)           # §5
                                      └─> dedupe_and_merge(...)          # §6
                                          └─> embed + index (tsv trigger)
                                              └─> événement interne "job_normalized"
                                                  └─> scoring (cf. 06 §4)
```

Chaque étape est une tâche Celery idempotente et rejouable isolément (relance à partir du payload S3 sans re-fetch).

### 4.2 Planification (Celery beat)

| Source | Fréquence 🟡 | Justification |
|---|---|---|
| `france-travail` | Toutes les 2 h (fenêtre incrémentale), + 1 réconciliation complète par nuit (03:00 UTC) | Volume élevé, incrémental natif ; la réconciliation nocturne rattrape les trous et détecte les expirations |
| `greenhouse` | Toutes les 6 h par board | Fetch complet peu coûteux, boards petits |
| `lever` | Toutes les 6 h par site | Idem |
| `partner-*` | Selon contrat (défaut : quotidien 04:00 UTC) | — |

Les cycles d'une même source ne se chevauchent pas : verrou Redis `ingestion:lock:{slug}` (TTL = 2 × durée max observée) ; si le verrou est pris, le cycle est sauté et compté (`ingestion_cycle_skipped`).

### 4.3 Fetch incrémental

- **France Travail** : curseur `last_sync_at` persisté par source (table `connector_state` : `source_id`, `cursor`, `updated_at`). Requête sur les offres créées/actualisées depuis `last_sync_at − 15 min` (chevauchement volontaire, l'idempotence absorbe les doublons). Le curseur n'avance qu'après un cycle complet réussi.
- **Greenhouse / Lever** : pas d'incrémental côté API → fetch complet, puis diff local : une offre dont `updated_at` (Greenhouse) est inchangé et dont le hash du payload brut (`sha256` du JSON canonicalisé) est identique au dernier ingéré est ignorée sans re-normalisation.
- **Réconciliation complète** (nocturne pour FT, chaque cycle pour les ATS) : sert aussi la détection d'expiration (§4.6).

### 4.4 Idempotence et stockage brut

Pour chaque offre reçue :

1. Écriture S3 du payload brut : clé `raw/{source_slug}/{external_ref}/{ingested_at_iso}.json` (bucket versionné, chiffrement SSE, rétention alignée sur la politique 11 §3 : 12 mois après expiration de l'offre).
2. `INSERT ... ON CONFLICT (source_id, external_ref) DO UPDATE` sur `job_sources` : mise à jour de `raw_payload_key` et re-normalisation **uniquement si** le hash du payload a changé ; sinon simple rafraîchissement de `last_seen_at` sur le `job_posting` lié.
3. Aucune écriture applicative ne dépend de l'ordre d'arrivée : rejouer un cycle complet est sans effet de bord.

### 4.5 Erreurs, retries, circuit breaker

**Classification des erreurs :**

| Classe | Exemples | Comportement |
|---|---|---|
| Transitoire | timeout, 429, 500–504, erreur réseau | Retry Celery : backoff exponentiel `min(2^n × 30 s, 30 min)` + jitter ±20 %, max 5 tentatives ; sur 429, `Retry-After` respecté s'il est fourni |
| Permanente requête | 400, 404 sur une offre précise | Pas de retry ; offre marquée en erreur (`ingestion_item_error`), cycle continue |
| Permanente source | 401/403 (credentials, révocation), changement de schéma détecté (validation Pydantic du payload brut échoue sur > 10 % 🟡 des items) | Cycle interrompu, alerte immédiate (§7.3), circuit ouvert |

**Circuit breaker par source** (état en Redis `ingestion:cb:{slug}`) :

- Fermé → Ouvert : ≥ 5 échecs de cycle consécutifs 🟡 **ou** 1 erreur « permanente source ».
- Ouvert : les cycles planifiés sont sautés ; demi-ouverture après 1 h (erreurs transitoires) — les erreurs de type credentials/révocation exigent une **réactivation manuelle** après vérification (lien avec §3.3).
- Demi-ouvert : 1 cycle d'essai ; succès → fermé, échec → ouvert (fenêtre doublée, plafond 24 h).
- Chaque transition est journalisée (`audit_log`, entité `source`) et émet une alerte.

Un circuit ouvert n'affecte jamais les autres sources (files et verrous par source).

### 4.6 Détection d'expiration des offres

Trois mécanismes combinés, du plus fiable au moins fiable :

1. **Signal explicite de la source** : statut « annulée/pourvue » (France Travail) ou date de fin de publication → `status = 'withdrawn'` ou `expires_at` renseigné ; à `expires_at` dépassé, un job horaire passe l'offre `expired`.
2. **Disparition du flux** : lors d'une réconciliation complète réussie, toute offre de cette source absente du flux est candidate à expiration. Règle anti-faux-positif : l'offre doit être absente de **2 réconciliations complètes consécutives** 🟡 avant que la `job_source` soit considérée éteinte. L'offre canonique ne passe `expired` que si **toutes** ses `job_sources` sont éteintes (D13 : le multi-source protège).
3. **Re-check ciblé** : pour les offres `active` sans signal depuis > 14 jours 🟡 (`last_seen_at` ancien — cas des sources sans réconciliation fiable), une tâche `recheck_job` fait un GET unitaire sur `original_url`/l'API : 404/410 ou disparition → traitement comme en (2).

Effets de l'expiration : l'offre disparaît des résultats (`status = 'active'` filtré en dur, D07) ; `match_results` conservés (historique candidatures) ; purge/archivage à 12 mois après expiration (11 §3).

---

## 5. Normalisation

Objectif : transformer chaque payload brut en `job_postings` + tables satellites (`job_locations`, `job_skills`, `job_languages`), avec **confiance par attribut extrait** (alimentant `q_d` du moteur, 06 §1).

### 5.1 Mapping des champs par source

Convention de confiance : champ structuré fourni par la source → `confidence = 1.0` ; champ dérivé par règle → 0,7–0,9 selon la règle ; champ extrait par LLM → confiance retournée par le modèle (schéma `job_extraction`).

| Champ `job_postings` | France Travail | Greenhouse | Lever |
|---|---|---|---|
| `title` | `intitule` (1.0) | `title` (1.0) | `text` (1.0) |
| `company_name` | `entreprise.nom` (1.0 ; sinon « Employeur confidentiel ») | nom du board (config `connector_boards`) (1.0) | nom du site (config) (1.0) |
| `description_text` | `description` (1.0) | `content` HTML → texte (sanitisation §5.2.0) | `descriptionPlain` (1.0) |
| `contract` | mapping direct `typeContrat` (CDI→`permanent`, CDD→`fixed_term`, MIS/intérim→`other`, stage→`internship`, alternance→`apprenticeship`) (1.0) | étage 1 règles / étage 2 LLM | `categories.commitment` mappé par dictionnaire (0.9) ; sinon étages 1/2 |
| `remote` | champ télétravail si présent (1.0) ; sinon étages 1/2 | étages 1/2 | `workplaceType` mappé direct (1.0) |
| `salary_min/max/currency/period` | parsing du libellé salaire par règles (0.8) ; sinon LLM | étages 1/2 | `salaryRange` si présent (1.0) ; sinon étages 1/2 |
| `seniority`, `experience_min/max` | `experienceExige`/libellé par règles (0.8) | étages 1/2 (cf. 06 §2 dim. 4) | étages 1/2 |
| `job_locations` | code INSEE + lat/lon fournis (1.0) | `location.name` → géocodage §5.3 | `categories.location` → géocodage |
| `job_skills` | référentiel ROME → taxonomie §5.5 (0.9) | étage 2 LLM (extraction depuis description) | étage 2 LLM |
| `job_languages` | champ langues si présent (1.0) ; sinon étages 1/2 | étages 1/2 | étages 1/2 |
| `sector_code` | code NAF/ROME → table de correspondance NACE simplifié (0.9) | inconnu au MVP (k=0, cf. 06 dim. 6) 🟡 | inconnu au MVP 🟡 |
| `language` | détection §5.4 | détection §5.4 | détection §5.4 |

Tout champ non résolu reste `NULL` → dimension « inconnue » côté matching (jamais de valeur devinée sans confiance — D03).

### 5.2 Extraction d'attributs en deux étages

**Étage 0 — sanitisation** : HTML → texte (balises retirées, entités décodées, scripts/styles supprimés), normalisation unicode NFKC, espaces compactés. Le texte sanitisé est l'unique entrée des étages suivants (défense anti-injection : cf. 08 §6 — le HTML n'atteint jamais un prompt).

**Étage 1 — règles déterministes** (coût nul, reproductible — priorité par conception, D02/R7). Bibliothèque `ingestion/rules/`, testée unitairement, par famille :

- *Contrat* : dictionnaires multilingues FR/EN (`\bCDI\b`, `permanent contract`, `CDD`, `fixed[- ]term`, `freelance`, `internship|stage`, `alternance|apprenticeship`…). Confiance 0,9 si un seul type détecté ; si plusieurs types contradictoires → non résolu (passe à l'étage 2).
- *Salaire* : regex sur motifs `([\d\s.,]+)\s*(k€|K€|€|EUR)` avec fenêtres contextuelles (« brut annuel », « /mois », « per year », « TJM »), fourchettes `X – Y`, conversion k€→€ ; période inférée du contexte, confiance 0,8. Montants aberrants (< 10 000 €/an ou > 500 000 €/an 🟡 après conversion annuelle) → rejetés, passage étage 2.
- *Remote* : dictionnaires (« full remote », « télétravail total/partiel/x jours », « hybrid », « on[- ]site », « présentiel ») + extraction du nombre de jours ; confiance 0,85 ; motifs contradictoires → étage 2.
- *Langues* : motifs « anglais courant », « English fluent », « bilingue », niveaux CECRL explicites (`\bB2\b` avec contexte langue) ; mapping courant→B2 🟡, bilingue/natif→C2 ; confiance 0,8. La langue de rédaction n'est **jamais** convertie en exigence (06 §2 dim. 9).
- *Expérience* : motifs « X ans d'expérience », « X+ years », « X à Y ans » ; confiance 0,85.

**Étage 2 — LLM en secours** : uniquement pour les attributs non résolus par l'étage 1 **et** pour `job_skills` (extraction sémantique). Tâche `extract_job` (08 §2), sortie validée contre `ai-output-schemas.json#job_extraction`, chaque item porte `confidence` et `evidence.quote`. Règles :

- Cache par offre : 1 seul appel LLM par (offre, `prompt_version`) — résultat réutilisé entre re-normalisations tant que le payload est inchangé (R7).
- Les valeurs de l'étage 1 **priment** sur celles de l'étage 2 (déterminisme d'abord) ; le LLM ne remplit que les trous.
- Confiance < 0,5 → attribut traité comme inconnu par le moteur (06 §1) ; on stocke quand même la valeur + confiance pour analyse.
- Échec propre de la tâche IA (08 §5) → l'offre est publiée avec les seuls attributs déterministes ; compteur `job_extraction_failed` (l'indice de confiance du matching reflète naturellement le manque).

### 5.3 Géocodage

- France : Base Adresse Nationale (API Adresse — licence et conditions d'usage **à confirmer par revue juridique**, comme toute source) ; libellés de villes → lat/lon + `country_code`.
- Hors France / fallback : géocodeur auto-hébergé (Photon/Nominatim sur données OpenStreetMap — obligations d'attribution ODbL **à confirmer par revue juridique**) 🟡.
- Cache persistant `geocode_cache(label_norm → lat, lon, country_code, resolved_at)` — un libellé n'est géocodé qu'une fois ; TTL 12 mois.
- Libellés non résolus (« Remote — EMEA », « multiple locations ») : `job_locations.lat/lon = NULL`, le moteur traite la localisation comme inconnue (06 §2 dim. 7) ; motif journalisé pour enrichir les règles.

### 5.4 Détection de langue

- Bibliothèque déterministe embarquée (lingua-py 🟡 — pas d'appel réseau) sur `title + description_text`.
- Sortie : `language` ISO 639-1 ; confiance < 0,7 🟡 → défaut `fr` si source FR (France Travail), sinon `en`, et warning journalisé.
- Impact : configuration `tsvector` (`french`/`english`, trigger SQL existant) et langue des contenus générés (D15).

### 5.5 Taxonomie de compétences

Normalisation de chaque `label_raw` (issu de ROME, de l'étage 2 LLM, ou du profil candidat — même chaîne partagée avec le module profil) :

1. **Canonicalisation** : lowercase, unaccent, trim, compactage espaces, suppression ponctuation terminale.
2. **Alias exact** : lookup `skill_aliases(alias)` (citext) → `skill_id`. La table d'alias est enrichie en continu (ex. `react.js`→`react`, `postgres`→`postgresql`).
3. **Rapprochement par embedding** : sinon, embedding du libellé (même modèle que §5.6) et recherche du plus proche voisin dans `skills.embedding` ; cosinus ≥ `skill_alias_threshold` = 0,85 🟡 → rattachement + **proposition** d'alias (file de revue humaine hebdomadaire, pas d'écriture automatique dans `skill_aliases`).
4. **Non rattaché** : `job_skills.skill_id = NULL`, `label_raw` conservé — le matching de compétences retombe sur la comparaison par embeddings de libellés (06 §2 dim. 1, seuil 0,75 🟡).

Référentiel de départ : ESCO 🟡 (licence d'utilisation **à confirmer par revue juridique**), sous-ensemble tech/support/vente chargé en seed.

### 5.6 Embeddings et indexation

- Embedding de l'offre (`job_postings.embedding`, vector(1024)) : `title + "\n" + premier paragraphe de description_text` (cohérent avec 06 §2 dim. 3). Modèle : cf. 08 §8 (multilingual-e5-large, 1024 dim 🟡, auto-hébergé UE — D09).
- `tsv` maintenu par trigger SQL (déjà en place).
- L'événement `job_normalized` n'est émis qu'après embedding + dédup, pour que le scoring lise un état complet.

---

## 6. Déduplication (D13)

Exécutée dans `dedupe_and_merge`, **avant** insertion/rattachement du `job_posting` canonique. 100 % déterministe, aucun LLM.

### 6.1 Étage 1 — clé exacte (`dedup_hash`)

```
dedup_hash = sha256(
    norm(company_name) || "\x1f" ||
    norm(title)        || "\x1f" ||
    norm_location      || "\x1f" ||
    norm_ref
)
```

**Fonction de normalisation `norm(s)` — définition exacte :**

1. Unicode NFKC ;
2. lowercase (casefold) ;
3. suppression des diacritiques (unaccent) ;
4. remplacement de toute ponctuation et de tout séparateur (`/ \ - _ , . ( ) [ ] & + ' "`) par une espace ;
5. compactage des espaces multiples en une seule, trim ;
6. pour `company_name` uniquement : suppression des suffixes juridiques terminaux (`sas`, `sasu`, `sarl`, `sa`, `gmbh`, `inc`, `ltd`, `llc`, `bv`) et des mentions `groupe`/`group` en tête 🟡.

**Composantes :**

- `norm_location` : `country_code + ":" + norm(libellé ville principale)` si géocodée ; sinon `norm(raw_label)` ; offre full-remote sans ville → `"remote:" + country_code` (ou `"remote:"` seul).
- `norm_ref` : **référence employeur** si la source en expose une (numéro de requisition interne, ex. champ ID d'annonce republiée) après `norm()` ; chaîne vide sinon. Elle permet une fusion exacte quand deux sources republient la même annonce avec sa référence d'origine ; en son absence, l'étage 1 déduplique surtout les republis strictes et l'étage 2 fait le travail inter-sources. *(Interprétation de la formule D13 — voir Questions ouvertes Q4.)*

**Algorithme :** `SELECT id FROM job_postings WHERE dedup_hash = :h` → hit : rattachement (nouvelle ligne `job_sources` si source différente, cf. §6.3) ; miss : passage à l'étage 2.

### 6.2 Étage 2 — similarité (candidats trigram, décision cosinus)

Ne s'applique qu'aux offres `active` (jamais de fusion avec une offre expirée).

1. **Génération de candidats** (index trigram existants `idx_jobs_title_trgm`, `idx_jobs_company_trgm`) :

```sql
SELECT id FROM job_postings
WHERE status = 'active'
  AND similarity(company_name, :company) > 0.55   -- 🟡
  AND similarity(title,        :title)   > 0.45   -- 🟡
LIMIT 50;
```

2. **Filtre de compatibilité dure** (évite les fusions absurdes) : même `country_code` (ou l'un des deux NULL) ; si les deux offres ont un lieu géocodé, distance ≤ 50 km 🟡 ou l'une est full-remote ; types de contrat non contradictoires (égaux, ou l'un NULL).
3. **Décision** : cosinus entre `embedding` du candidat et de la nouvelle offre ≥ **0,92** 🟡 (seuil D13, à calibrer en alpha) → doublon. Plusieurs candidats au-dessus du seuil → celui de plus forte similarité.
4. Aucun candidat → nouvelle offre canonique (`INSERT job_postings` avec son `dedup_hash`).

Biais assumé : seuil élevé → faux négatifs (doublons non fusionnés) préférés aux faux positifs (D13). Mesure du taux résiduel en alpha via échantillonnage annoté.

### 6.3 Fusion des champs

Quand une offre entrante est rattachée à un `job_posting` existant :

1. **`job_sources`** : ligne ajoutée (ou mise à jour si même `(source_id, external_ref)`), avec `original_url` obligatoire — **chaque** source conserve son lien d'origine, affiché côté produit.
2. **Champ par champ** (attributs extraits : `contract`, `remote`, `salaire_*`, `seniority`, `experience_*`, `job_skills`, `job_languages`) — règle « la donnée la plus riche et la plus récente gagne » :
   - valeur existante NULL, entrante non NULL → entrante ;
   - les deux non NULL et **égales** → conservation, `confidence = max` des deux ;
   - les deux non NULL et **différentes** → gagne la valeur de plus forte confiance ; à confiance égale (±0,05), gagne la plus récente (`posted_at`, sinon `ingested_at`) ; **le conflit est journalisé** dans `audit_log` (action `job_field_conflict`, meta : champ, valeurs, sources, confidences, valeur retenue) pour calibrage ultérieur des règles ;
   - `description_text` : la plus longue (proxy « plus riche ») est conservée 🟡 ; re-calcul `tsv` + embedding si elle change.
3. **Dates** : `first_seen_at` = min, `last_seen_at` = max ; `posted_at` par source dans `job_sources`.
4. **Statut** : une fusion sur offre `active` la maintient `active` ; les règles d'expiration multi-sources s'appliquent (§4.6).

---

## 7. Volumétrie, SLOs, monitoring

### 7.1 Volumétrie cible MVP 🟡

| Grandeur | Cible |
|---|---|
| Offres actives en base | 50 000 – 150 000 (lancement vertical FR ; très en-deçà des seuils D06 de 500 k/5 M) |
| Nouvelles offres / jour | 3 000 – 10 000 (dont ~80 % France Travail) |
| Boards ATS activés | 50 – 200 (Greenhouse + Lever cumulés) |
| Taux de doublons inter-sources attendu | 5 – 15 % des offres ATS (à mesurer en alpha, D13) |
| Appels LLM `extract_job` / jour | ≤ 1 appel par offre nouvelle/modifiée, soit ≤ 10 000/jour au pic (cache par payload, R7) |

### 7.2 SLOs

| SLO | Cible | Mesure |
|---|---|---|
| Fraîcheur | **< 24 h** entre publication chez la source et disponibilité scorée chez nous, p95 ; cible interne 6 h pour France Travail 🟡 | `job_sources.posted_at` → fin de `normalize_job` |
| Taux d'échec d'ingestion | **< 2 %** d'items en erreur définitive par cycle et par source (hors circuit ouvert) | `ingestion_item_error / items_seen` |
| Latence de normalisation | p95 < 60 s par offre (étage 2 LLM inclus) 🟡 | traces Celery |
| Exactitude d'expiration | 0 offre affichée `active` > 72 h après disparition confirmée de toutes ses sources | audit réconciliation |
| Disponibilité du pipeline | ≥ 1 cycle réussi par source et par période de planification sur 99 % des jours | métrique `ingestion_cycle_success` |

### 7.3 Métriques de monitoring (Prometheus 🟡, labels `source`)

- `ingestion_cycle_duration_seconds`, `ingestion_cycle_success_total`, `ingestion_cycle_skipped_total`
- `ingestion_items_seen_total`, `ingestion_items_new_total`, `ingestion_items_updated_total`, `ingestion_items_unchanged_total`
- `ingestion_item_error_total{class="transient|permanent"}` ; **alerte** : ratio erreurs/items > 2 % sur 3 cycles consécutifs
- `ingestion_circuit_state{state}` ; **alerte immédiate** sur ouverture (page si source = france-travail)
- `ingestion_http_429_total`, `ingestion_rate_limit_remaining` (FT) ; **alerte** à < 20 % du quota
- `normalization_field_resolved_total{field, stage="source|rules|llm"}` — suivi de la part règles vs LLM (objectif : ≥ 70 % des attributs résolus sans LLM 🟡)
- `job_extraction_failed_total`, `job_extraction_low_confidence_total` (conf < 0,5)
- `dedup_stage1_hit_total`, `dedup_stage2_hit_total`, `dedup_new_posting_total`, `job_field_conflict_total{field}`
- `jobs_active_gauge{source}`, `jobs_expired_total{mechanism="signal|absence|recheck"}`
- `freshness_seconds` (histogramme publication→disponibilité) ; **alerte** p95 > 24 h
- Tableau de bord par source : items/cycle, erreurs, fraîcheur, circuit, quota — revu à la revue trimestrielle (§3.3)

---

## Questions ouvertes

1. **Q1 — Conditions France Travail** : quelles sont les conditions exactes (convention, quotas, rétention, réaffichage) applicables à notre cas d'usage d'agrégation ? → revue juridique + dossier francetravail.io avant activation. Bloquant lancement.
2. **Q2 — Ré-agrégation des flux ATS** : les ToS Greenhouse/Lever et la volonté des employeurs autorisent-elles le réaffichage par un tiers ? Faut-il un opt-in employeur systématique ou seulement en cas de doute ? → revue juridique ; définit la vitesse d'ajout de boards.
3. **Q3 — Licences des référentiels** : ESCO (taxonomie compétences), BAN/API Adresse, OSM/ODbL (géocodage fallback) — obligations d'attribution et compatibilité d'usage commercial à confirmer par revue juridique.
4. **Q4 — Interprétation du `source_ref` dans la clé d'étage 1 (D13)** : ce document l'interprète comme « référence employeur si exposée, sinon vide ». Si D13 visait la référence externe propre à chaque source, l'étage 1 ne fusionnerait jamais inter-sources et servirait uniquement d'idempotence renforcée — à trancher avec l'auteur de D13 avant implémentation.
5. **Q5 — Calibrage des seuils** : cosinus 0,92 (dédup), trigram 0,55/0,45 (candidats), 2 réconciliations avant expiration, fréquences de fetch — à recalibrer sur données réelles en alpha (procédure : échantillon annoté de 200 paires candidates).
6. **Q6 — Secteur des offres ATS** : `sector_code` inconnu pour Greenhouse/Lever au MVP (poids 4 → impact limité). Enrichissement ultérieur par référentiel entreprise (SIRENE ?) — licence et coût à étudier.
7. **Q7 — Partenaire** : y a-t-il un partenaire signé avant le gel du périmètre MVP ? Sinon, retirer `partner-*` du plan de charge.
8. **Q8 — « Description la plus longue gagne »** : proxy fruste pour « source la plus riche » ; valider en alpha qu'il ne dégrade pas la qualité (alternative : score de richesse pondéré par nombre de champs structurés fournis).
