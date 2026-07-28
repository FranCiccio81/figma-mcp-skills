# 19 — État du MVP

> **À qui ce document s'adresse** : à quelqu'un qui doit décider s'il ouvre une alpha, ce qu'il promet aux premiers utilisateurs, et où il met le prochain euro d'effort.
>
> **Méthode** : tout ce qui suit a été vérifié dans le code de `boussole/`, et les chiffres proviennent d'exécutions réelles des suites de tests. Ce document ne recopie pas les intentions des spécifications : quand le code et la spec divergent, c'est le code qui est rapporté, et la divergence est signalée. Les incertitudes portent 🟡. Aucune question juridique n'est tranchée ici.
>
> **État de référence** : lot post-M6 n° 2 — **1241 tests unitaires + 66 tests d'intégration**, `ruff` et `mypy` verts (146 fichiers). La rédaction initiale portait sur le commit `811d4d1` ; §8.2 a été mis à jour à chaque lot depuis, chaque fois en fermant des points qu'écrire ce document avait révélés.

---

## 1. En une page

Six jalons ont été livrés et mergés : M1 (fondations + auth), M2 (ingestion + recherche), M3 (matching + explications), M4 (CV + générations + candidatures), M5 (privacy + durcissement), M6 (mise en service).

**Ce qui existe** : une application complète de bout en bout. Un utilisateur peut créer un compte, importer un CV, valider un profil, définir ses préférences, chercher des offres, voir un score de matching explicable, générer un e-mail ou une lettre ancrés dans son profil, suivre ses candidatures, exporter ses données et supprimer son compte. Le tout derrière une API FastAPI (1241 tests unitaires + 66 tests d’intégration PostgreSQL, lint et types verts) et un front Next.js.

**Ce qui manque pour que ce soit un produit** : trois choses de nature différente.

1. **Des décisions juridiques, pas du code.** Les connecteurs d'offres sont écrits mais désactivés en attendant Q2/Q3. Le provider LLM réel est écrit mais inactif en attendant Q4/Q38. Sans offres, le produit n'a rien à matcher ; c'est aujourd'hui le blocage n°1 et il ne se lève pas en écrivant du code.
2. **Un peu d'exploitation.** Pas d'e-mail transactionnel, pas d'antivirus, et surtout **aucun export d'observabilité** : `SENTRY_DSN` et `OTEL_EXPORTER_OTLP_ENDPOINT` sont des variables sans effet, les logs stdout sont le seul signal. Conséquence directe : les alertes de conformité que le système émet désormais (§5.6) n'atteignent personne.
3. **Des fonctionnalités assumées comme absentes** : export PDF/DOCX, digest e-mail, OAuth, multi-CV.

**Sur le niveau de maturité** : les revues de code ont trouvé, à chaque jalon, des défauts sérieux dans du code dont la suite de tests était verte — six sur M4/M5, et quatre garde-fous sur cinq qui ne tenaient pas à l'exécution sur M6. Tous ont été corrigés avec un test de régression vérifié par réintroduction du bug. Ce qu'il faut en retenir n'est pas « le code est mauvais » : c'est que **la suite de tests seule n'a jamais suffi à valider ce système**, et que le budget de revue doit rester dans le plan de charge.

---

## 2. Ce qui est réellement implémenté et testé — feature par feature

Statuts : ✅ implémenté et couvert · 🟡 implémenté avec une limite documentée · 🟠 partiel · ❌ non implémenté.

| Feature | Statut | Ce qui existe réellement | Limites vérifiées |
|---|---|---|---|
| **A — Compte & onboarding** | ✅ | `POST /auth/register`, `/auth/login`, `/auth/logout`, `GET /me`. Sessions opaques en Redis persistant à TTL glissant, CSRF double-submit, hachage argon2, rate limiting login 5/min, erreurs RFC 9457. Pages `/inscription` et `/connexion` | Pas de MFA (Q36, assumé). Pas d'e-mail de confirmation : **aucun envoi d'e-mail n'existe dans le système** |
| **B — Import & parsing CV** | ✅ | `POST /cv-documents`, `GET /cv-documents/{id}`, `POST /cv-documents/{id}/apply`. Taille ≤ 10 Mo, type détecté par **magic bytes** (jamais le `Content-Type` déclaré), quota 5/jour vérifié **avant** stockage, tâche Celery `ai.parse_cv`, bornes anti-bombe de décompression (50 Mo décompressés, ratio 100:1, 200 pages PDF, 2 M caractères). L'extraction ne produit qu'une **proposition** : rien n'est écrit dans le profil sans `apply` | Pas d'antivirus (Q16, hors périmètre explicite). Pas d'OCR des PDF image (Q22, assumé). Extraction réelle conditionnée à `AI_PROVIDER` (§3) |
| **C — Édition du profil** | ✅ | `GET/PATCH /profile`, CRUD complet sur expériences / formations / compétences / langues, `POST /profile/validate`. Provenance par champ, promotion en bloc `cv_extraction → user_confirmed` à la validation, `total_experience_years` recalculé par fusion d'intervalles, `version` incrémentée à chaque mutation. Page `/profil` avec badges de provenance | Un profil validé reste validé après édition (Q23, assumé) |
| **D — Préférences** | ✅ | `GET/PUT /preferences`, remplacement complet transactionnel, validations 422 ciblées par champ, déduplication insensible à la casse, hook interne « preferences_changed » branché sur l'invalidation des `match_results`. Page `/preferences` | Le vecteur agrégé de profil n'est pas recalculé au changement de préférences — rattrapé sous 24 h par le beat (§6 du runbook) |
| **E — Agrégation d'offres** | 🟠 | Trois connecteurs **écrits et testés** (France Travail OAuth2 incrémental, Greenhouse, Lever), `connector_state` avec curseur persisté, compteurs d'absence persistés en jsonb, tâches beat de sync et de réconciliation, `GET /sources` | 🔴 **Les trois sont derrière `FEATURE_SOURCE_*=false`** en attente de Q2/Q3 ; un quatrième connecteur, `demo-corpus`, alimente la mesure avec des offres **fictives** et refuse de s'activer hors développement (D34). Pas de verrou anti-chevauchement ni de circuit breaker par source 🟡. Archivage S3 du payload brut = stub logué 🟡 |
| **F — Normalisation & dédup** | 🟡 | Normalisation complète, taxonomie de compétences avec alias, géocodage, **dédup étage 1** (hash exact) avec contraintes SQL `dedup_hash` UNIQUE et `(source_id, external_ref)` UNIQUE, SAVEPOINT par item | 🟡 **Dédup étage 2 neutralisée** tant que le provider d'embeddings est lexical (§3) |
| **G — Recherche & filtres** | ✅ | `GET /jobs` : recherche full-text `tsvector` pondérée A/B/C avec `unaccent` **des deux côtés**, filtres, pagination keyset `(last_seen_at, id)`, tris `date`/`relevance`, rerank vectoriel. Pages `/offres` et `/offres/[id]` | Rerank **local à la page** 🟡. `sort=match` retombe sur `relevance` |
| **H — Matching** | ✅ | Moteur déterministe `app/matching` : 12 dimensions, configuration versionnée (`scoring-config.json`), renormalisation, bloquants, `GET /jobs/{id}/match` et `GET /matches` avec cache `match_results` et invalidation par version de profil / de scoring. 166 tests dont les cas de référence UM-01…UM-18 | `GET /matches` score **paresseusement** les 200 offres actives les plus récentes 🟡 ; pas de re-scoring asynchrone complet. Pré-filtre pays inapplicable (`preference_locations` ne porte pas de code pays) 🟡 |
| **I — Indice de confiance** | 🟡 | Calculé par le moteur, distinct du score, `unknown_dimensions` exposées | 🔴 **Surévalué** : `title_similarity` (15 % du poids) est publiée comme « connue » avec un sous-score de 0,00 sur 100 % des paires mesurées — N14. Calibration sur jeu annoté toujours non faite (N16) |
| **J — Explication** | ✅ | Deux couches : `explanation_facts` déterministes émis par le moteur, puis reformulation LLM dont l'entrée est **exclusivement** les facts. Sortie validée contre le schéma, **puis** contrôlée : aucun nombre absent des facts. Échec → 502 propre, jamais de contenu divergent. Cache `match_explanations`. Panneau front | Sortie « canned » sans aucun chiffre tant que `AI_PROVIDER=fake` |
| **K — Sauvegarde & masquage** | ✅ | `PUT/DELETE /jobs/{id}/saved-state`, filtre `saved_only`, purge RGPD des `saved_jobs` (le trou trouvé en revue M5) | — |
| **L — Génération e-mails** | ✅ | `POST /generations` (`email`), cycle `pending → processing → ready`, puis `draft → validated → exported`. Quotas 10/h et 40/j. Contrôle d'ancrage. Page `/candidatures/documents` | Provider réel inactif par défaut (§3) |
| **M — Lettres de motivation** | ✅ | `doc_type: cover_letter`, même chaîne | Idem |
| **N — Optimisation CV** | ✅ | `doc_type: cv_optimization` (seul type sans `job_id`) | Idem |
| **O — Adaptation CV à une offre** | ✅ | `doc_type: cv_variant` | Idem |
| **P — Suivi candidatures** | ✅ | CRUD `/applications`, `POST /applications/{id}/status`, transitions **libres mais toutes historisées** dans `application_events`, offres externes (`external_title` + `external_company`), `applied_at` posé à la première transition seulement, pagination keyset. Page `/candidatures` | Idempotency-Key **en mémoire de processus** 🟡 : ne survit ni au redémarrage ni au multi-instance |
| **Q — Données & suppression** | ✅ | `POST /privacy/export` (quota 2/jour, idempotence), `GET /privacy/exports/{id}`, `/download` par lien signé HMAC à 7 jours, `DELETE /account` avec limiteur dédié **fail-closed**. Registre déclaratif de purge : chaque module expose `purge_user()`/`export_user()`, exhaustivité vérifiée par test. Purge à J+30, anonymisation de `users`/`audit_log`/`ai_calls`, suppression des objets stockés, idempotence. Page `/parametres` | 🔴 **La purge ne s'exécute que par beat** : sans processus beat, l'engagement des 30 jours n'est pas tenu (§5). Lien signé = HMAC applicatif, pas encore un pré-signé S3 🟡 |

**Transverse** : `/healthz` et `/readyz` (base + deux Redis + joignabilité réelle du stockage), logs JSON avec `trace_id`, en-têtes de sécurité, rate limiting global 60/min et recherche 30/min, i18n FR/EN avec contrôle de parité, proxy BFF même origine.

---

## 3. Implémenté mais **inactif par défaut** — et pourquoi

Ces trois briques sont écrites, testées, et **délibérément éteintes**. Ce ne sont pas des oublis : ce sont des refus d'activer sans décision.

### 3.1 Provider LLM réel — `AI_PROVIDER=fake`

`AnthropicProvider` existe : sortie JSON contrainte avec schéma assaini, dégradation automatique vers repair-parse, retries bornés honorant `Retry-After`, vocabulaire d'erreur fermé, circuit breaker par provider, journal `ai_calls`. Il est branché sur les quatre points d'appel (extraction CV, extraction d'offre, explication, génération).

**Pourquoi éteint** : l'activation était explicitement conditionnée à la résolution de **Q4** (localisation UE garantie du provider, traitement et non-entraînement contractuels) et **Q38** (suffisance SCC + TIA si le traitement sort de l'UE). Ce sont des questions de conformité, pas d'ingénierie.

**Deux garde-fous accompagnent ce choix** :
- un provider réel **ne peut pas s'instancier sans clé** ;
- la fabrique **ne retombe jamais** sur le provider factice. C'était le cas avant M6, et le résultat était pire qu'une panne : une clé absente produisait un CV « analysé » entièrement vide, sans erreur, sans ligne dans `ai_calls`. Désormais l'indisponibilité remonte en 503 explicite, et le reste de l'application (recherche, scores, facts déterministes) continue de fonctionner.

**Avec `fake`** : les sorties sont déterministes et canned. Le produit est démontrable de bout en bout, mais l'extraction de CV et les générations ne portent aucune valeur réelle.

### 3.2 Dédup étage 2 — neutralisée hors provider sémantique

`_stage2_threshold()` retourne un seuil **inatteignable** (1,5) tant que `EMBEDDINGS_PROVIDER` n'est pas `managed`. Seule la dédup exacte par hash reste active.

**Pourquoi**. Le seuil de 0,92 a été calibré pour des vecteurs sémantiques. Mesuré en revue M6 avec le provider lexical par défaut : « Développeur Backend Python » et « … Java » de la même entreprise à **0,955** ; deux offres de même titre et même premier paragraphe, l'une à Paris l'autre à Lyon, à **1,0000**. Au-dessus du seuil, elles auraient fusionné — et **la fusion est irréversible pour l'utilisateur : l'offre absorbée disparaît définitivement**.

Deux corrections ont été faites ensemble : un filtre géographique dur (au-delà de 50 km, aucune fusion quel que soit le cosinus — la spec l'exigeait mais il n'avait jamais été écrit), et la neutralisation complète de l'étage 2 sous provider lexical. Le biais va vers le **faux négatif** (deux annonces du même poste restent visibles séparément), conformément à la décision de conception.

Ne pas « réactiver » en baissant `DEDUP_STAGE2_COSINE_THRESHOLD` : ce réglage n'est simplement pas consulté tant que le provider est lexical.

### 3.3 Provider d'embeddings managé — `EMBEDDINGS_PROVIDER=hashing`

Le défaut est un provider **local, déterministe, sans réseau ni clé** : hashing trick signé sur mots + n-grammes de caractères, `blake2b` (et non `hash()`, randomisé par processus — l'API et le worker auraient écrit des vecteurs divergents), vecteurs normalisés L2.

**Ce qu'il est** : de la similarité **lexicale** — morphologie, ordre des caractères. Il permet de livrer, tester et calibrer toute la chaîne sans dépendance externe. Il rend actives quatre fonctionnalités qui étaient écrites mais inertes avant M6 : similarité d'intitulé (15 % du poids de matching), crédit « compétence proche », dédup étage 2, rerank de recherche.

**Ce qu'il n'est pas** : un modèle sémantique. « Développeur backend » et « ingénieur serveur » restent éloignés.

**Pourquoi le managé reste éteint** : `ManagedEmbeddingProvider` est un squelette qui **ne nomme aucun fournisseur, ne code aucun endpoint et n'affirme aucune conformité** — parce que **Q11** (modèle multilingue FR/EN, dimension, hébergement UE) n'est pas tranchée. Toute tentative d'usage lève proprement ; la fabrique dégrade alors sur `hashing` en journalisant bruyamment. L'application ne part **jamais** en appel réseau vers un fournisseur non choisi.

**Garde-fou associé** : un provider dont la dimension diffère de 1024 est refusé (`EmbeddingDimensionError`) — un modèle de dimension différente corromprait silencieusement les colonnes `vector(1024)`. 🟡 Ce contrôle est **paresseux** (premier usage du provider), pas au démarrage.

---

## 4. Ce qui n'est **pas** implémenté

Vérifié dans le code, pas déduit des specs.

| Manque | Vérification | Statut |
|---|---|---|
| **Export PDF / DOCX** | `app/modules/generation/service.py::export` lève un `501 not_implemented` explicite pour `pdf` et `docx` | Assumé. Seul `format=text` (copie inline) fonctionne. La roadmap le désignait comme coupe possible |
| **Rétention 13 mois de `ai_calls`** | Documentée dans `app/ai/calls.py` avec un TODO M6 explicite ; **aucune entrée de `beat_schedule`** ne la réalise. Seule la purge RGPD par utilisateur existe, et c'est une *anonymisation* (`user_id → NULL`) | 🔴 **Rétention annoncée non tenue par le système.** La table croît sans limite (≤ 10 k lignes/jour pour `extract_job` seule) |
| **OAuth / connexion tierce** | `users.password_hash` est nullable « si OAuth (post-MVP) » et `privacy/service.py` porte une branche morte pour ce cas. Aucun flux, aucun endpoint | Post-MVP assumé |
| **Digest e-mail de nouvelles offres** | Aucun envoi d'e-mail n'existe (recherche exhaustive : pas de `smtp`, `mailer`, `send_email` dans `app/`) | Hors MVP (Q9). Désigné comme première coupe en cas de retard |
| **Tout e-mail transactionnel** | Idem. `mailpit` est dans le compose de dev mais rien ne lui écrit | 🔴 Conséquence : pas d'e-mail de confirmation de suppression de compte avec lien d'annulation (hypothèse Q30), pas de vérification d'adresse |
| **Multi-CV / multi-profils** | Un profil canonique unique par utilisateur ; les variantes passent par `doc_type: cv_variant` | Post-MVP assumé (Q8), conforme à la décision de conception |
| **Antivirus à l'upload** | Explicitement hors périmètre dans `cv/router.py` | Q16 non levée |
| **OCR des PDF image** | Aucun | Hors MVP (Q22) |
| **Export Sentry / OpenTelemetry** | `SENTRY_DSN` et `OTEL_EXPORTER_OTLP_ENDPOINT` sont **déclarés dans la configuration et jamais lus par le code** | 🔴 Les renseigner n'a aucun effet. L'observabilité se limite aux logs JSON sur stdout |
| **Service `beat` dans l'infrastructure** | `docker-compose.dev.yml` déclare `postgres`, `redis` ×2, `minio`, `minio-init`, `mailpit`, `api`, `worker`, `web` — **pas de beat** | 🔴 Voir §5 |
| **Alerte « purges en retard »** | Prévue par la décision d'observabilité ; aucun code ne la réalise | 🔴 Voir §5 |
| **Verrou anti-chevauchement d'ingestion / circuit breaker par source** | Documenté comme non implémenté en tête de `ingestion_tasks.py` | 🟡 Assumé |
| **Re-scoring asynchrone complet** | Le hook « preferences_changed » invalide les `match_results` ; le recalcul est paresseux à la lecture | 🟡 Assumé |
| **Changement d'adresse e-mail** | Aucun endpoint | Post-MVP (Q33) |
| **Colonnes `embedding_source_hash` / `embedding_model_version`** | Absentes du schéma | 🟡 Conséquence : aucune détection automatique d'un vecteur périmé après changement de modèle (voir runbook §5.1) |
| **Suite de tests front** | `web/package.json` n'expose que `dev`, `build`, `start`, `lint`, `typecheck`, `i18n:check`. Aucun runner de test | 🔴 Le front n'a **aucun test automatisé** |
| **Tests E2E / adversariaux / schemathesis** | Aucun harnais | Prévus par la stratégie de test, non réalisés |
| **Jeu annoté et gates de qualité matching** | `scoring-config.json` porte des `evaluation_gates` ; aucun jeu annoté, aucune mesure | 🔴 Voir §7 |

---

## 5. Les invariants produit et comment ils sont vérifiés **aujourd'hui**

Ce sont les promesses qui définissent le produit. Voici ce qui les tient réellement.

### 5.1 Le score n'est jamais généré par un LLM

**Tenu, et verrouillé structurellement.** Le moteur `app/matching` est un package pur : il ne peut rien importer d'autre que la stdlib et lui-même.

`tests/unit/matching/test_purity.py` le vérifie de deux façons complémentaires : une inspection AST de toutes les sources du package (imports interdits : `app.modules`, `app.ai`, `sqlalchemy`, `httpx`, `fastapi`, `celery`, `redis`, `asyncpg`, `alembic`), **et** un interpréteur frais lancé en sous-processus qui contrôle qu'importer `app.matching` ne charge aucun de ces modules. Un import accidentel casse le test — on ne peut pas y glisser un appel réseau par inadvertance.

Verrouillé aussi par les 166 tests du domaine, dont les cas de référence chiffrés **UM-01…UM-18**, calculés à la main et gelés : tout changement de seuil dans `scoring-config.json` les casse, ce qui force la décision à être assumée.

### 5.2 Anti-invention dans les contenus générés

**Tenu, après correction.** Le contrôle d'ancrage vérifie que chaque affirmation du corps généré est rattachée à un élément du profil.

Ce qu'il faut savoir : **ce contrôle était contournable jusqu'à la revue M4/M5**. Une liste de claims vide passait pour « ancré » — un corps entièrement inventé était donc validable et exportable. Le correctif vérifie désormais durées, rôles revendiqués et entités inconnues contre le profil, et **une affirmation dont le texte contredit l'élément qu'elle référence ne compte plus comme ancrée**. Un `PATCH` sans changement ne lève plus le contrôle et n'efface plus le verdict d'échec.

Verrouillé par `tests/unit/generation/test_generation_anchoring.py` et `test_grounding_unit.py` (69 tests sur le domaine génération).

Deux protections adjacentes, du même effort : un module de **scrubbing** applique une barrière PII déterministe à la sortie d'extraction et au payload de profil des quatre prompts ; et l'ancrage des citations impose une longueur minimale, la présence du libellé dans la citation, et rejette les formulations d'injection.

### 5.3 Score ≠ confiance

**Tenu.** Deux grandeurs calculées séparément par le moteur, exposées séparément dans le contrat, avec `unknown_dimensions` explicites. Les tests de dimensions et du moteur couvrent les deux formules.

🟡 **Ce qui n'est pas tenu** : la **calibration** de la confiance. Elle suppose un jeu annoté qui n'existe pas (§7). La formule est implémentée et cohérente ; on ne sait pas si elle prédit bien.

### 5.4 Source et lien d'origine conservés

**Tenu, au niveau SQL.** `job_sources.original_url` est `NOT NULL` et `(source_id, external_ref)` est UNIQUE — ce sont des contraintes de base, pas des conventions applicatives. `GET /sources` expose le registre, et le front a une page dédiée.

Verrouillé par `tests/integration/test_ingestion_dedup.py` (8 tests) et `test_sql_constraints.py` (15 tests), qui s'exécutent contre un **vrai** PostgreSQL avec les **vraies** migrations.

### 5.5 Validation humaine avant export

**Tenu, en ceinture et bretelles.** Un CHECK SQL (`exported ⇒ validated_at`) issu du schéma initial, **et** un contrôle applicatif : `export()` refuse en 409 `generation_not_validated` si le statut n'est pas `validated`/`exported`, **et** re-vérifie `validated_at is not None` — la vérification applicative du CHECK, pour ne pas dépendre d'une seule barrière. Un document dont l'ancrage a échoué ne peut pas être validé.

Verrouillé par `test_generation_lifecycle.py`, `test_generation_api.py` et le CHECK exercé dans `tests/integration/test_sql_constraints.py`.

### 5.6 Suppression effective ≤ 30 jours

**Implémenté et testé de bout en bout — mais tributaire d'un composant d'exploitation absent.**

Ce qui est solide : `PURGE_DELAY_DAYS = 30`, registre déclaratif dont l'exhaustivité est vérifiée par test (chaque module est **résolu et appelé**, pas seulement enregistré), purge idempotente, échec partiel journalisé et retenté, anonymisation de `users`/`audit_log`/`ai_calls`, suppression des objets stockés.

Le test d'intégration `test_privacy_purge.py` (12 tests) est le plus exigeant de la base : il inventorie les tables réelles via `information_schema`, **suit les clés étrangères transitivement**, et échoue si la moindre ligne du compte purgé survit. Aucune liste en dur : une future table personnelle oubliée dans le registre fera tomber ce test le jour de sa migration. C'est ce test qui aurait attrapé le purgeur `jobs` resté à l'état de stub — trouvé en revue M5, où des `saved_jobs` survivaient indéfiniment à l'effacement.

**Ce qui l'est devenu** : la purge n'est déclenchée que par la tâche beat `maintenance.purge_due_accounts` (04:15 UTC) — rien d'autre ne la lance, ni l'API, ni un trigger, ni une cascade. Le service `beat` manquait du `docker-compose.dev.yml` : un déploiement calqué dessus rendait 204 sur `DELETE /account` sans jamais rien supprimer. Il y est depuis la finalisation, avec un commentaire qui dit pourquoi il n'est pas optionnel.

La surveillance manquait aussi ; elle existe depuis le lot post-M6 n° 1 : `maintenance.check_purge_backlog` (05:15 UTC, une heure après la purge) journalise en **ERROR** toute demande échue depuis plus de 26 heures et toujours `pending` — le symptôme d'une purge qui échoue en boucle, jusqu'ici invisible au-dessus du niveau de la ligne de log.

🟡 **Deux limites à connaître, l'une et l'autre assumées.**

1. **Un ordonnanceur mort reste indétectable de l'intérieur** : la surveillance est elle-même une tâche beat. Si beat s'arrête, ni la purge ni son contrôle ne tournent, et le silence est complet. C'est pourquoi le cas sain journalise quand même `purge_backlog_ok` : c'est un **battement de cœur**, et c'est son absence que la supervision externe doit alerter (runbook §7.3).
2. **La marge de 26 heures signifie qu'une purge peut légitimement s'exécuter au 31ᵉ jour.** `purge_after` est posé à J+30 et la purge tourne une fois par jour : l'engagement est tenu à un cycle près, par construction. La surveillance rend ce dépassement visible, elle ne le supprime pas. Le fond se règle en posant `purge_after` à J+29 ou en purgeant plus souvent — c'est une modification de D09, pas de la surveillance, et elle n'est pas faite.

---

## 6. Ce que les revues de code ont trouvé — et ce que ça dit

Factuel. Chaque défaut listé est issu du message de commit du correctif correspondant, et chacun est aujourd'hui corrigé avec un test de régression.

### 6.1 M4/M5 — six défauts critiques

| # | Défaut | Effet réel |
|---|---|---|
| 1 | Purge RGPD jamais complétée : le module `jobs` était resté un stub M1, le runner s'arrêtait avant l'anonymisation de l'audit et ne marquait jamais les demandes `purged` | `saved_jobs` conservés indéfiniment — engagement des 30 jours rompu |
| 2 | Le module privacy déclarait un contrat de stockage **async** face au contrat **sync** livré en M4 | Export jamais construit ; archives survivant aux comptes supprimés |
| 3 | Rate limiting défait par un cookie de session aléatoire : l'identité était le **hash du cookie sans le vérifier** | Un cookie différent à chaque requête = seau neuf à chaque fois. 200 requêtes, 0 rejet |
| 4 | Ancrage contournable par une liste de claims vide | Un corps entièrement inventé passait pour ancré, validable et exportable |
| 5 | Aucune barrière PII déterministe n'atteignait les prompts ; la docstring affirmait à tort qu'`extra=forbid` protégeait | Données personnelles transmises au provider sans filtrage |
| 6 | Bombe de décompression DOCX : 475 Ko gonflant à 1,3 Go | Worker tué à l'import d'un CV hostile |

### 6.2 M6 — quatre garde-fous sur cinq ne tenaient pas à l'exécution

C'est le constat le plus instructif du projet : **le jalon annonçait cinq garde-fous, quatre étaient inopérants malgré une suite verte**.

| # | Garde-fou annoncé | Pourquoi il ne tenait pas |
|---|---|---|
| 1 | Le worker Celery refuse de démarrer sur stockage local en production | Branché sur `@worker_ready.connect`. `Signal.send` **attrape** les exceptions des receveurs, les journalise et poursuit — et `worker_ready` est émis **après** le début de la consommation de la file. Un worker de production démarrait normalement et écrivait CV et archives sur un disque que l'API ne lit jamais. Déplacé au niveau **module** : l'import échoue |
| 2 | `NoSuchBucket` remonte en erreur de configuration, jamais en « objet absent » | Une clause sur le **statut HTTP**, placée juste sous l'exclusion documentée, l'annulait (S3 répond 404 sur `NoSuchBucket`). **La purge RGPD rapportait un succès complet en n'ayant rien supprimé** |
| 3 | Les contrôles de production sont actifs en production | `env` était une chaîne libre comparée par égalité. `ENV=prod`, `Production`, ou avec un espace final désactivait **tous** les contrôles en silence — et `staging` n'était couvert par aucun. `env` est désormais un `Literal` et le durcissement s'applique dès staging |
| 4 | Un provider LLM indisponible échoue proprement | Repli implicite sur le provider factice : une panne LLM produisait un CV « analysé » vide, sans erreur, sans entrée dans `ai_calls`. La fabrique lève désormais, exposé en 503 |

Onze autres défauts ont été corrigés dans le même passage, dont : le provider réel bloquait la boucle d'événements (jusqu'à ~190 s de worker figé) ; les lignes `ai_calls` écrites depuis les workers étaient planifiées sur une boucle fermée avant exécution ; le nom de tâche de l'explication violait l'enum SQL, si bien que **rien n'était jamais journalisé** ; `extract_job` — le plus gros volume du système — n'atteignait jamais la fabrique et construisait un `FakeProvider` en dur, qu'aucune configuration ne pouvait remplacer.

Le même passage a corrigé quatre fonctionnalités **écrites mais inatteignables depuis le code de production** : le crédit « compétence proche » n'était câblé que côté candidat (sous-score 0,0 avec un cosinus de 0,99) ; la similarité d'intitulé faisait la **moyenne** des intitulés cibles au lieu du **max** exigé par la spec (0,000 au lieu de 0,889 pour un candidat parfaitement ciblé).

### 6.3 Ce que ces revues disent du niveau de maturité

Trois lectures, à tenir ensemble :

1. **Le processus de revue fonctionne, et il est indispensable.** Chaque défaut ci-dessus a été trouvé sur du code dont les tests passaient. Les correctifs M6 ont été vérifiés par **réintroduction du bug** — la seule méthode qui prouve qu'un test de régression teste quelque chose. Le budget de revue n'est pas un luxe de fin de jalon : c'est le mécanisme qui a rattrapé les défauts que la suite ne pouvait pas voir.

2. **Le mode de défaillance dominant est identifiable et récurrent** : *du code qui a l'air d'être là et qui ne s'exécute pas*. Garde-fou branché sur un signal qui avale les exceptions ; provider câblé en dur ignorant la configuration ; purgeur enregistré mais resté stub ; contrôle d'ancrage passant sur liste vide ; fonctionnalité correcte mais jamais atteinte depuis le chemin de production. Une suite de tests qui vérifie l'**appel** et non l'**effet** ne voit rien de tout cela. C'est exactement pourquoi la suite d'intégration existe — et pourquoi elle a immédiatement trouvé, à sa création, un bug produit vivant (la recherche accentuée qui ne remontait rien, cas nominal d'un francophone).

3. **La densité de défauts décroît en gravité mais pas en nombre.** M4/M5 : six défauts critiques touchant la conformité et la sécurité. M6 : quatre garde-fous inopérants + onze défauts d'exécution. La qualité de ce qui est livré **après revue** est bonne ; la qualité de ce qui est livré **avant** ne l'est pas encore assez pour se passer de l'étape. Un décideur doit en tirer une conséquence de planning : **prévoir la revue et son cycle de correction comme une phase à part entière de chaque jalon**, pas comme un aléa.

---

## 7. Métriques de qualité actuelles

Mesurées sur le commit `811d4d1`, `boussole/api`.

### Tests

| Suite | Volume | État | Commande |
|---|---|---|---|
| Unitaires | **1241** tests | ✅ tous verts (118 s) | `make test` |
| Intégration PostgreSQL | **66** tests | ✅ verts contre un PostgreSQL 16 + pgvector réel | `make test-integration` |
| Front | **0** | 🔴 aucun runner de test dans `web/package.json` | — |

Répartition des 1241 unitaires (48 nouveaux : `evaluation`) :

| Domaine | Tests | | Domaine | Tests |
|---|---|---|---|---|
| matching (moteur) | 166 | | privacy | 84 |
| ingestion | 156 | | cv | 82 |
| core (config, stockage, gardes) | 147 | | jobs | 80 |
| ai (providers, journal, rétention) | 133 | | generation | 76 |
| embeddings | 70 | | matching_api | 60 |
| applications | 47 | | auth/sécurité/erreurs (racine) | 45 |
| profiles | 32 | | preferences | 15 |

Répartition des 66 tests d'intégration : contraintes SQL 15, purge RGPD 12, dédup 8, trigger full-text 8, pagination keyset 8, rétention `ai_calls` 5, export RGPD 5, filtre salaire 5.

### Lint et types

| Outil | Périmètre | Résultat |
|---|---|---|
| `ruff` | `api/` — règles E, F, W, I, UP, B, SIM, RUF | ✅ **All checks passed** |
| `mypy` | `app` (146 fichiers), **strict** sur `app.core.*` et `app.matching.*` | ✅ **no issues found** |
| `next lint` / `tsc --noEmit` | `web/` | Non exécuté ici (dépendances npm non installées) 🟡 |

### CI

✅ **Active** depuis le lot post-M6 n° 1. `.github/workflows/boussole-ci.yml` définit quatre jobs sur toute PR touchant `boussole/` : lint (ruff + mypy), tests unitaires, détection de changement `boussole/api/**`, et tests d'intégration sur un service PostgreSQL `pgvector/pgvector:pg16`.

Le fichier a passé six jalons dans `infra/github-workflows/` avec un README demandant de le déplacer : **aucune vérification automatique n'a tourné sur les PR de tout le projet**, y compris celles où les revues manuelles ont trouvé des défauts critiques.

### Qualité du matching — première mesure

`scoring-config.json` portait des `evaluation_gates` depuis le premier jour sans qu'aucune n'ait jamais été exécutée. Le harnais existe désormais (`make evaluate`, D35) et a tourné. Résultat au corpus de démonstration :

| Porte | Seuil | Mesuré | |
|---|---|---|---|
| `spearman_min` | ≥ 0,60 | **0,570** (pire profil : `cand-devops`) | ❌ |
| `ndcg_at_10_min` | ≥ 0,75 | 0,913 (pire profil) | ✅ |
| `blocking_precision_min` | ≥ 0,95 | 1,000 — 0 rédhibitoire annoncé à tort | ✅ |
| `blocking_recall_min` | ≥ 0,85 | 1,000 — 0 rédhibitoire manqué | ✅ |

Par profil : `cand-backend-senior` ρ = 0,832 / NDCG 0,944 · `cand-devops` ρ = 0,570 / NDCG 0,913 · `cand-junior` ρ = 0,710 / NDCG 0,991.

**Ce que ça vaut.** Le jeu est fait de **cas de référence construits**, pas d'annotations humaines d'offres réelles (N16) : le rapport dit si le moteur se comporte comme spécifié sur des situations choisies, pas si le matching est bon pour de vrais candidats. Cette question-là reste entière et reste le chemin critique le plus long.

**Ce que la première exécution a trouvé**, en revanche, est solide et chiffré :

- **N14 — `title_similarity` est inerte et compte comme un fait connu.** Sous-score 0,00 sur les **36 paires**, statut « connu ». 15 % du poids qui ne discriminent rien et abaissent uniformément tous les scores. Pire : l'indice de confiance intègre cette dimension comme connue, il est donc **surévalué**. C'est la première mesure chiffrée de l'impact de N1 (provider lexical).
- **N15 — la couverture des compétences favorise les offres maigres.** Une offre à une seule exigence satisfaite obtient 1,00 sur la dimension à 25 %. Mesuré : un poste « Développeur Python Junior » sur site atteint 60 pour un profil DevOps senior exigeant le full remote. C'est ce qui fait tomber Spearman sous la porte.
- **N13 — « full remote requis » ne bloque pas un poste hybride.** Le moteur suit la spec ; c'est la spec qui mérite discussion — un niveau nommé « requis » qui ne bloque pas est difficile à défendre.

Les deux premières sont **épinglées par test de caractérisation et délibérément non corrigées** : un jeu recalé sur la sortie du moteur ne mesure plus rien.

### Ce qui n'est pas mesuré

- **Couverture de code** : aucun outil de couverture n'est configuré. Les 1241 tests sont un volume, pas une couverture.
- **Performance** : la cible « recherche p95 < 500 ms » n'a jamais été mesurée sur un corpus réel — il n'y a pas eu de corpus réel, les connecteurs étant désactivés.
- **Prompts** : les tests de prompts en CI et le jeu adversarial prévus par la stratégie de test n'existent pas.

---

## 8. Ce qui reste avant une alpha fermée

Ordonné par criticité. **Les blocages juridiques ne se résolvent pas en écrivant du code** et sont donc listés séparément — leur résolution ne relève ni de ce document ni de l'équipe technique.

### 8.1 Blocages **juridiques** — préalables, non arbitrés ici

| Priorité | Point | Question | Décideur (17) | Effet du blocage |
|---|---|---|---|---|
| **1** | Conditions d'utilisation de l'API **France Travail** | **Q2** | Juridique + Data Eng | 🔴 Sans elle, aucune offre publique française n'entre. **Un produit de matching sans offres n'est pas démontrable en alpha** |
| **1** | Agrégation des flux **Greenhouse / Lever** : accord par employeur nécessaire ? | **Q3** | Juridique | 🔴 Même effet. C'est la deuxième et dernière voie d'alimentation existante |
| **2** | Localisation UE du **provider LLM** (traitement, non-entraînement) | **Q4** | Security/Privacy Eng | 🔴 Sans elle, extraction de CV et générations restent factices |
| **2** | **SCC + TIA** si traitement hors UE | **Q38** | Privacy | Idem |
| **3** | Hébergement UE du **provider d'embeddings** | **Q11** | ML Eng | 🟠 Le provider local fonctionne ; la qualité sémantique et la dédup étage 2 attendent |
| **3** | **DPIA signée** — critère de sortie explicite de M5 | — | Privacy + CPO | Prérequis annoncé de l'alpha |
| **4** | **AI Act** : classification annexe III | **Q1** | Conseil juridique + CPO | Conditionne le lancement public plus que l'alpha fermée |
| **4** | **Art. 22 RGPD** appliqué au score | **Q37** | Juridique | Idem |
| **4** | **DPO** désigné | **Q5** | CPO | Idem |
| **5** | Conformité du **géocodage** (instance publique OSM par défaut aujourd'hui) | **Q14** | DevOps | 🟡 À trancher avant tout volume réel |

### 8.2 Blocages **techniques** — faisables, ordonnés

> **Mise à jour** — cette liste comptait 15 entrées dont 5 critiques à sa rédaction. Sept sont fermées : trois par la finalisation, quatre par le lot post-M6 n° 1. **Aucun blocage critique ne subsiste.** Les points fermés restent listés, barrés, avec ce qui les a réglés : une liste de blocages qui perd ses lignes sans laisser de trace ne se relit pas.

**Critique — sans quoi une alpha ne doit pas ouvrir**

1. ~~🔴 **Provisionner un processus `celery beat`**~~ — ✅ **fait** (finalisation). Service `beat` dans `docker-compose.dev.yml`, avec le commentaire qui dit qu'il n'est pas optionnel : sans lui, `DELETE /account` répond 204 et ne supprime rien. Une seule instance doit tourner.
2. ~~🔴 **Surveillance des purges en retard**~~ — ✅ **fait** (lot n° 1). `maintenance.check_purge_backlog` à 05:15, une heure après la purge : ERROR sur toute demande échue depuis plus de 26 h et toujours `pending`, battement `purge_backlog_ok` sinon. Limites en §5.6.
3. ~~🔴 **Remplacer `PRIVACY_SIGNING_KEY`**~~ — ✅ **outillé** (finalisation). `app/core/secrets.py` refuse le démarrage hors développement tant que la valeur du dépôt n'est pas remplacée, côté API **et** côté workers. Le remplacement lui-même reste un geste de déploiement — mais il ne peut plus être oublié en silence.
4. ~~🔴 **Backfill forcé des embeddings**~~ — ✅ **débloqué** (finalisation). `force=True` parcourt désormais par keyset et renvoie `next_after_id` ; l'exécution reste à faire le jour où un corpus réel existe.
5. ~~🔴 **Activer la CI**~~ — ✅ **fait** (lot n° 1). `boussole-ci.yml` vit à `.github/workflows/` : lint, tests unitaires et tests d'intégration PostgreSQL tournent sur toute PR touchant `boussole/`. Le fichier a passé six jalons dans `infra/` avec une note demandant de le déplacer.

**Élevé — pour que l'alpha produise des enseignements exploitables**

6. **Constituer le jeu annoté** — l'instrument est livré, il attend son jeu. `make evaluate` mesure Spearman, NDCG@10 et les bloquants contre les `evaluation_gates` (D35), sur un corpus de démonstration fictif (D34) et des **cas de référence construits**. Ce qui manque est ce qui coûte : des annotateurs humains sur des offres réelles (Q19/Q20/Q47 — et donc Q2/Q3). **Toujours le point n° 1 restant, mais la moitié technique est faite.**
7. **Traiter N14 avant l'alpha, sans attendre Q11.** La mesure a montré que `title_similarity` vaut 0,00 sur 100 % des paires **et** est comptée comme connue : 15 % du poids qui ne discriminent rien et qui gonflent l'indice de confiance. La marquer inconnue quand le provider est lexical est une correction courte, honnête, et indépendante du choix de modèle. La recalibration complète des seuils (0,75 « proche », 0,92 dédup, pondération de rerank — Q12/Q41) reste, elle, suspendue à Q11.
7 bis. **Instruire N15** — la couverture des compétences requises favorise les offres peu exigeantes, et c'est ce qui fait tomber la porte Spearman. Aucune piste ne doit être retenue sans la mesurer : c'est exactement l'usage du harnais.
8. **Brancher une observabilité qui existe.** `SENTRY_DSN` et `OTEL_EXPORTER_OTLP_ENDPOINT` sont des variables sans effet ; les logs stdout sont le seul signal disponible. C'est aussi ce qui manque pour que l'alerte du point 2 atteigne quelqu'un : elle est aujourd'hui une ligne ERROR que personne ne lit.
9. ~~**Purge par âge de `ai_calls`** (13 mois)~~ — ✅ **fait** (lot n° 1). `maintenance.purge_ai_calls` à 05:30, suppression par lots de 5 000 bornés à 20 lots par exécution (un `DELETE` global verrouillerait la table, donc les appels IA en cours). Borne calculée en **mois calendaires** : `13 × 30 jours` supprimerait cinq jours trop tôt, c'est-à-dire des lignes encore sous engagement de conservation. Vérifié contre un vrai PostgreSQL — `DELETE` n'accepte pas de `LIMIT`, la requête bornée est inhabituelle et méritait autre chose qu'un fake.

**Moyen — dette assumée à ne pas laisser filer**

10. **Verrou anti-chevauchement d'ingestion et circuit breaker par source** — deviennent nécessaires dès que des sources réelles tournent en continu.
11. **Idempotency-Key des candidatures en Redis** plutôt qu'en mémoire de processus : la solution actuelle ne survit ni au redémarrage ni au multi-instance.
12. **Colonnes `embedding_source_hash` / `embedding_model_version`** : sans elles, aucun changement de modèle n'est détectable automatiquement, et le rattrapage reste une opération manuelle risquée.
13. **Amorcer une suite de tests front** : `web/` n'a aujourd'hui aucun test.
14. **Décider du sort des e-mails transactionnels** : la confirmation de suppression avec lien d'annulation (Q30) suppose un fournisseur (Q15) qui n'a pas été choisi.
15. **Rafraîchir la documentation résiduelle** : le README de `tests/integration/` décrit encore un `xfail(strict=True)` sur la recherche accentuée — le bug a été corrigé et le `xfail` retiré ; le README annonce aussi « ~750 tests » unitaires alors qu'il y en a 1193.

**Nouveau — soulevé par le lot n° 1**

16. **L'engagement des 30 jours est tenu à un cycle près** : `purge_after` est posé à J+30 et la purge tourne une fois par jour, donc une purge peut légitimement s'exécuter au 31ᵉ jour. La surveillance rend le dépassement visible, elle ne le supprime pas. Se règle en posant `purge_after` à J+29 — c'est une modification de D09, à arbitrer.

**Non bloquant — assumé pour le MVP**

Export PDF/DOCX, OAuth, digest e-mail, multi-CV, MFA, OCR, changement d'adresse e-mail : tous documentés comme post-MVP ou coupes assumées, aucun ne conditionne une alpha fermée.

---

## 9. Références

- Runbook d'exploitation : [18-deployment-runbook.md](18-deployment-runbook.md)
- Questions ouvertes : [17-open-questions.md](17-open-questions.md) · Décisions : [decisions.md](decisions.md) · Traçabilité : [traceability-matrix.md](traceability-matrix.md)
- Roadmap et jalons : [15-delivery-roadmap.md](15-delivery-roadmap.md) · Risques : [16-risk-register.md](16-risk-register.md)
- Code : [`boussole/`](../boussole/) — API `boussole/api`, front `boussole/web`, infra `boussole/infra`
- Tests d'intégration : `boussole/api/tests/integration/README.md`
