# decisions.md — Registre des décisions (ADR condensés)

Format : **Décision / Justification / Alternatives / Compromis / Réévaluation**.
Statuts : ✅ actée · 🟡 hypothèse de travail (à confirmer) · Voir `17-open-questions.md` pour les ambiguïtés.

---

## D01 — Monolithe modulaire ✅
- **Décision** : un seul service FastAPI + workers Celery, découpé en modules internes (`auth`, `profiles`, `preferences`, `ingestion`, `jobs`, `matching`, `explanations`, `generation`, `applications`, `privacy`) communiquant par appels de fonctions et événements internes, jamais par accès croisé aux tables d'un autre module.
- **Justification** : équipe réduite, itération rapide, un seul déploiement, transactions simples ; le cahier des charges exige une architecture simple au MVP.
- **Alternatives** : microservices (rejeté : coût opérationnel injustifié) ; serverless (rejeté : workers longs de parsing/ingestion mal adaptés).
- **Compromis** : scalabilité horizontale grossière (on scale tout le monolithe) ; discipline de frontières à maintenir par revue.
- **Réévaluation** : > 50k offres ingérées/jour, > 8 devs, ou besoin d'isolation de charge entre ingestion et API.

## D02 — Scoring 100 % déterministe, config versionnée ✅
- **Décision** : le score est calculé par `matching/engine.py` en Python pur à partir de données structurées ; poids, seuils et courbes dans `scoring-config.json` (versionné, chargé au démarrage, référencé par `scoring_version` sur chaque résultat).
- **Justification** : reproductibilité, explicabilité, coût nul par calcul, exigence explicite du cahier des charges.
- **Alternatives** : score LLM (rejeté : non reproductible, coûteux, inexplicable) ; modèle ML appris (reporté : pas de données d'entraînement au MVP).
- **Compromis** : poids initiaux à dire d'expert, calibrage nécessaire.
- **Réévaluation** : dès ≥ 500 paires annotées (Phase 8), calibrage des poids ; envisager un modèle appris à ≥ 5k paires.

## D03 — Score de compatibilité ≠ indice de confiance ✅
- **Décision** : deux valeurs distinctes affichées ensemble. Compatibilité = qualité du match calculée sur les dimensions **connues**. Confiance = couverture pondérée des données (deux côtés) × fiabilité d'extraction. Les critères bloquants et les inconnues sont des sorties séparées.
- **Justification** : « transparence plutôt que score magique » ; une donnée manquante ne doit pas déguiser un mauvais match en moyen ni un bon match en mauvais.
- **Alternatives** : score unique pénalisé par l'incertitude (rejeté : illisible) ; intervalle de score (reporté : UX plus complexe, envisageable v2).
- **Compromis** : deux chiffres à expliquer à l'utilisateur → effort de pédagogie UX (microcopies Phase 2).
- **Réévaluation** : tests utilisateurs alpha (H1).

## D04 — Ingestion par connecteurs explicitement autorisés ✅
- **Décision** : chaque source = un connecteur dédié avec fiche de conformité (base légale, licence/ToS, quota, fraîcheur) validée avant activation. MVP 🟡 : API France Travail (publique, conventionnée), flux publics d'ATS (Greenhouse Job Board API, Lever Postings API — offres exposées publiquement par les employeurs), + 1 partenaire si signé. Pas de crawler générique.
- **Justification** : exigence produit (sources légalement exploitables), risque R1.
- **Alternatives** : scraping large (rejeté : légalement indéfendable en UE à l'échelle) ; agrégateur commercial unique (reporté : coût, dépendance).
- **Compromis** : couverture limitée au départ → positionnement vertical assumé.
- **Réévaluation** : à chaque source ajoutée ; revue trimestrielle du registre des sources.

## D05 — Profil canonique versionné avec provenance par champ ✅
- **Décision** : un profil canonique unique par utilisateur (JSON structuré + tables normalisées), chaque champ portant `source` ∈ {cv_extraction, user_input, user_confirmed} et `confidence` ∈ [0,1]. Les CV adaptés à une offre sont des **variantes** dérivées référencant le canonique (jamais modifié par une variante).
- **Justification** : anti-invention (on ne génère que depuis du validé), traçabilité RGPD, explicabilité du matching.
- **Alternatives** : multi-profils libres (reporté v2) ; stockage document brut seul (rejeté : inexploitable pour le matching déterministe).
- **Compromis** : modèle de données plus riche ; migration nécessaire si multi-profil v2.
- **Réévaluation** : demande utilisateur de multi-profils (mesurer en alpha).

## D06 — PostgreSQL + pgvector ✅
- **Décision** : une seule base PostgreSQL 16 ; embeddings (profils, offres) en pgvector, index HNSW.
- **Justification** : simplicité opérationnelle, transactions communes données/vecteurs, volumes MVP faibles (< 500k offres).
- **Alternatives** : Qdrant/Weaviate (rejeté MVP : un système de plus) ; OpenSearch k-NN (rejeté : idem).
- **Compromis** : perfs vectorielles moindres à très grande échelle.
- **Réévaluation** : > 5M offres actives ou p95 recherche > 500 ms.

## D07 — Recherche hybride SQL + full-text + rerank vectoriel ✅
- **Décision** : pipeline : (1) filtres durs SQL (localisation, contrat, langue, statut), (2) full-text `tsvector` (config `french`/`english` par langue d'offre), (3) re-ranking par similarité cosinus pgvector, (4) tri final par score de matching si profil actif.
- **Justification** : couvre filtres + pertinence sans Elasticsearch.
- **Alternatives** : Elasticsearch/OpenSearch (reporté), Meilisearch (reporté : facettes sympa mais système en plus).
- **Compromis** : tuning full-text multilingue limité.
- **Réévaluation** : ajout d'une 3e langue d'offres ou besoin de facettes agrégées complexes.

## D08 — Couche IA multi-provider, sorties JSON contraintes ✅
- **Décision** : module `ai/` avec interface `LLMProvider` (implémentations : Anthropic par défaut 🟡, + un second provider pour fallback), appels typés par tâche (`extract_cv`, `extract_job`, `explain_match`, `generate_letter`, `generate_email`, `tailor_cv`, `optimize_cv`). Toute sortie = JSON validé Pydantic contre les schémas de `ai-output-schemas.json` ; en cas d'échec : 1 retry avec message d'erreur, puis repair-parse, puis échec propre. Prompts versionnés (table `prompt_versions`), chaque appel journalisé avec `prompt_version`, `model`, tokens, latence.
- **Justification** : exigences produit (multi-provider, validation, versionnement) ; testabilité des prompts.
- **Alternatives** : framework d'orchestration lourd type LangChain (rejeté : abstraction opaque) ; function-calling propriétaire seul (utilisé mais derrière notre interface).
- **Compromis** : code d'infrastructure IA à maintenir nous-mêmes.
- **Réévaluation** : si un standard d'API structurée s'impose entre providers.

## D09 — Privacy by design UE ✅
- **Décision** : hébergement UE, chiffrement TLS 1.2+ en transit et AES-256 au repos, minimisation vers les LLM (jamais nom/email/téléphone dans les prompts de matching/génération sauf nécessité explicite validée), pas d'entraînement des providers sur nos données (contrats), suppression compte effective ≤ 30 jours (soft delete immédiat + purge planifiée, backups purgés au cycle), export des données (RGPD art. 20), registre des traitements + DPIA avant lancement.
- **Justification** : exigence produit, marché UE, données de CV = données personnelles riches.
- **Alternatives** : néant (exigence non négociable).
- **Compromis** : certains providers/features indisponibles ; latence potentielle.
- **Réévaluation** : expansion hors UE.

## D10 — Human-in-the-loop obligatoire ✅
- **Décision** : aucune action sortante automatisée. Tout contenu généré passe par relecture avec diff/aperçu et action explicite d'export (copie, téléchargement PDF/DOCX). L'état « candidature envoyée » est déclaré par l'utilisateur.
- **Justification** : exigence produit ; réduit drastiquement le risque AI Act/réputationnel.
- **Alternatives** : envoi assisté un-clic (reporté v2, avec garde-fous).
- **Compromis** : friction assumée.
- **Réévaluation** : post-MVP, si demande forte et cadre juridique clarifié.

## D11 — Frontend Next.js App Router en BFF léger ✅
- **Décision** : Next.js (App Router, TypeScript, Tailwind, shadcn/ui, TanStack Query, RHF + Zod). Le front appelle l'API FastAPI via un proxy de route Next (même origine, cookies httpOnly). Pas de logique métier côté Next.
- **Justification** : stack imposée ; auth par cookies simplifiée ; pas de duplication de règles métier.
- **Alternatives** : appels directs cross-origin (rejeté : gestion CORS/cookies plus fragile).
- **Compromis** : un saut réseau supplémentaire.
- **Réévaluation** : besoin de SSR intensif sur pages authentifiées.

## D12 — Async : Celery + Redis ✅
- **Décision** : Celery (broker Redis) pour parsing CV, ingestion, normalisation, embeddings, scoring en masse, générations longues ; files séparées `ingestion`, `ai`, `scoring` ; idempotence par clés naturelles ; retries exponentiels.
- **Justification** : stack imposée (Celery ou Dramatiq) ; Celery choisi pour maturité et écosystème (beat pour planification).
- **Alternatives** : Dramatiq (viable, moins d'outillage de planification intégré).
- **Compromis** : complexité Celery connue (visibilité) → Flower + métriques.
- **Réévaluation** : problèmes de fiabilité récurrents.

## D13 — Déduplication déterministe à deux étages ✅
- **Décision** : étage 1 : clé exacte `sha256(norm(company_name) + norm(title) + norm_location + norm_ref)` où `norm_ref` est la **référence employeur** si la source l'expose, chaîne vide sinon (résolution 2026-07-23 — l'idempotence par source reste assurée par l'unicité `(source_id, external_ref)` ; définition exacte de `norm()` dans 07 §6.1) ; étage 2 : candidats par similarité (trigram sur titre+entreprise, puis cosinus embeddings > 0,92 🟡 seuil initial) → fusion en `job_posting` canonique avec liste de `job_sources`. Le lien original de **chaque** source est conservé.
- **Justification** : exigence F ; multi-sources d'une même offre fréquent.
- **Alternatives** : dédup LLM (rejeté : coût, non-déterminisme).
- **Compromis** : faux négatifs possibles (doublons non fusionnés) — préférés aux faux positifs.
- **Réévaluation** : mesure du taux de doublons résiduels en alpha (seuil à calibrer).

## D14 — Explication en deux couches ✅
- **Décision** : couche 1 déterministe : le moteur émet des `explanation_facts` structurés (par dimension : valeur candidat, valeur offre, sous-score, poids, statut connu/inconnu/bloquant). Couche 2 LLM optionnelle à la demande : reformulation en langage naturel **uniquement à partir des facts** (le prompt ne contient pas l'offre brute), validée contre schéma.
- **Justification** : l'explication ne peut pas contredire le score (même source de vérité) ; coût LLM à la demande seulement.
- **Alternatives** : explication LLM libre depuis l'offre (rejeté : risque de divergence score/explication).
- **Compromis** : prose moins « riche » — assumé.
- **Réévaluation** : retours utilisateurs sur la lisibilité.

## D15 — i18n : FR d'abord, EN ensuite, architecture prête ✅
- **Décision** : UI en FR au lancement (fichiers de messages i18n dès le départ, next-intl 🟡) ; données d'offres avec `language` détecté ; full-text par langue ; modèles de génération capables de produire FR/EN selon la langue de l'offre.
- **Justification** : marché prioritaire France, exigence d'extensibilité multi-pays.
- **Compromis** : coût initial léger de l'externalisation des chaînes.
- **Réévaluation** : deuxième pays de lancement.

---

## D16 — Files Celery spécialisées ✅ *(précise D12)*
- **Décision** : quatre files — `ingestion`, `ai`, `scoring`, `maintenance` — avec priorités, `acks_late=true` et dead-letter queue ; détail dans 10 §4.
- **Justification** : isoler les charges (une panne LLM ne bloque pas l'ingestion) ; **Compromis** : plus de workers à dimensionner ; **Réévaluation** : saturation récurrente d'une file.

## D17 — Deux Redis logiques ✅
- **Décision** : instance persistante (broker Celery + sessions, AOF, `noeviction`) séparée de l'instance volatile (cache, rate-limit, LRU).
- **Justification** : une éviction LRU ne doit jamais détruire une session ou un message broker ; **Compromis** : deux instances à opérer ; **Réévaluation** : offre managée UE ne le permettant pas (cf. questions ouvertes).

## D18 — Dégradation gracieuse sans LLM ✅
- **Décision** : circuit breaker par provider + fallback second provider ; en panne totale, l'application reste pleinement fonctionnelle (recherche, scores, facts déterministes) — seuls parsing de nouveaux CV, reformulations et générations sont suspendus avec message explicite.
- **Justification** : le cœur de valeur (matching explicable) ne dépend d'aucun appel LLM (D02/D14) ; **Réévaluation** : jamais — propriété structurante.

## D19 — Sauvegarde PITR ✅ *(précise D09)*
- **Décision** : PITR PostgreSQL, RPO 1 h / RTO 4 h 🟡, rétention des backups 30 j alignée sur la fenêtre de purge RGPD, test de restauration mensuel.
- **Réévaluation** : validation produit des RPO/RTO avant beta.

## D20 — Observabilité ✅
- **Décision** : logs JSON structurés avec `trace_id` propagé API↔workers, métriques Prometheus/Grafana 🟡, Sentry, dashboard de conformité (purges en retard = alerte critique).

## D21 — Purge et export par interfaces de module ✅
- **Décision** : chaque module expose `purge_user()` / `export_user()` ; le module `privacy` orchestre, journalise et vérifie l'exhaustivité (aucun module ne peut être oublié : registre déclaratif contrôlé par test).

## D22 — Données synthétiques hors production ✅
- **Décision** : staging et local n'utilisent que des données synthétiques ; jamais de dump de prod, même « anonymisé ».

## D23 — Secrets et chiffrement ✅
- **Décision** : secrets via vault de plateforme 🟡, clés gérées par KMS cloud UE, rotation planifiée, aucun secret en variable d'environnement committée.

---

# Décisions issues de l'implémentation (M1 → M6)

> D24–D33 n'ont pas été arbitrées sur le papier : elles ont été **tranchées dans le code**, la plupart après qu'une revue a montré que la garantie annoncée ne tenait pas à l'exécution. Chaque décision ci-dessous est vérifiable dans un fichier nommé et verrouillée par un test nommé.

## D24 — Backend de stockage objet sélectionné par configuration, avec refus de démarrage ✅ *(précise D09)*
- **Décision** : `STORAGE_BACKEND` ∈ {`local`, `s3`} sélectionne l'implémentation de `ObjectStorage` (`api/app/core/storage.py` : `LocalDiskStorage` / `S3ObjectStorage` sur boto3, SSE-KMS ou SSE-S3). `check_storage_configuration()` **refuse le démarrage** dès que l'environnement n'est pas `development` avec `STORAGE_BACKEND=local`, ou avec `S3_SSE=none`. Le contrôle est branché au démarrage de l'API (`app/main.py`), **au niveau module** de `app/workers/celery_app.py` et dans `/readyz` (complété par `probe_object_storage()`, un `HeadBucket` réel). Corollaire indissociable : `ENV` est un vocabulaire **fermé** (`Literal["development", "staging", "production"]`, `app/core/config.py`), et le durcissement s'applique **dès staging** (`is_hardened`, et non `is_production`).
- **Justification** : `local` écrit sur le disque du conteneur courant. Dès que l'API et les workers Celery sont deux conteneurs, l'export RGPD (F-Q) répond 404 et les CV sont perdus au redémarrage. La revue M6 a établi que `ENV=prod`, `ENV=Production` ou `ENV="production "` désactivaient **silencieusement** tous les contrôles, et que le garde-fou du worker était un no-op (`Signal.send` avale les exceptions des récepteurs, et `worker_ready` se déclenche après le début de la consommation) : un worker de production démarrait sur du stockage local.
- **Alternatives** : avertissement au démarrage (rejeté : un log n'empêche pas la perte de données) ; alias tolérés pour `ENV` (rejeté : un alias muet redevient un contournement — seuls la casse et les espaces sont normalisés).
- **Compromis** : un déploiement mal configuré ne démarre pas du tout. Assumé : ne pas démarrer vaut mieux que perdre des exports.
- **Réévaluation** : jamais pour le principe. Le seuil `env != development` serait à revoir si un environnement mono-conteneur légitime apparaissait.
- **Vérifié par** : `tests/unit/core/test_startup_guards.py`, `tests/unit/core/test_config_env.py`, `tests/unit/core/test_storage_s3.py` (contrat partagé, paramétré sur les deux backends).

## D25 — Fabrique de providers LLM : circuit breaker, et interdiction du repli implicite vers le factice ✅ *(précise D08/D18)*
- **Décision** : `api/app/ai/providers/factory.py` sélectionne le provider par configuration (`AI_PROVIDER`, défaut `fake`), compose primaire + `AI_FALLBACK_PROVIDER` dans un `RoutedProvider`, et place un `CircuitBreaker` **par provider** partagé par processus (seuil, délai de réarmement, état demi-ouvert à **un seul** appel d'essai sous verrou). **Le provider factice n'est jamais un repli implicite** : clé absente, provider inconnu ou circuits tous ouverts ⇒ `ProviderUnavailableError`, jamais `FakeProvider`. `AI_FALLBACK_PROVIDER=fake` derrière un provider réel est explicitement **refusé et journalisé en erreur**. Toute exception du provider (y compris un défaut de code : `TypeError`, `KeyError`) compte comme une panne et bascule sur le fallback.
- **Justification** : la revue M6 a montré qu'un repli implicite transformait une panne LLM en CV « analysé » **entièrement vide**, sans erreur pour l'utilisateur et sans ligne dans `ai_calls` — l'exact inverse de D18, qui exige une suspension « avec message explicite ». Un demi-ouvert sans jeton renvoyait par ailleurs 1000 appels sur 1000 vers un provider encore en panne.
- **Alternatives** : repli silencieux sur le factice (rejeté : panne masquée) ; disjoncteur global tous providers confondus (rejeté : une panne Anthropic fermerait aussi le second provider).
- **Compromis** : l'indisponibilité IA devient visible pour l'utilisateur (503 explicite). C'est le comportement voulu — le cœur déterministe (recherche, scores, facts) reste intact (D02/D14/D18).
- **Réévaluation** : ajout d'un second provider réel ; seuils du disjoncteur (5 échecs / 60 s) à calibrer sur incidents réels 🟡.
- **Vérifié par** : `tests/unit/ai/test_provider_factory.py`, `tests/unit/ai/test_provider_wiring.py` (le provider réel est réellement atteignable depuis les sites d'appel métier — ils codaient auparavant `FakeProvider` en dur).

## D26 — Journal `ai_calls` structurellement fermé au contenu ✅ *(précise D09/D20)*
- **Décision** : `api/app/ai/calls.py` définit `AiCallRecord` comme une dataclass **`frozen`, `slots`, sans aucun champ de contenu** : tâche, version de prompt, modèle, `user_id` nullable, tokens, latence, statut, `error_code`. Il n'existe ni `prompt`, ni `response`, ni `detail` — journaliser du contenu est **structurellement impossible**, pas seulement interdit par convention. `task`, `status` et `error_code` sont des vocabulaires **fermés** validés en `__post_init__`. L'écriture ne peut jamais faire échouer l'appel IA. Le journal est inscrit au registre de purge avec **anonymisation** (`user_id → NULL`), jamais suppression.
- **Justification** : une interdiction déclarative se contourne par inadvertance ; une structure ne se contourne pas. La revue M4/M5 avait déjà trouvé une fuite de sortie LLM dans les journaux applicatifs. Le vocabulaire fermé a par ailleurs révélé son utilité immédiatement : `match_explanation` au lieu de `explain_match` violait l'enum SQL et faisait perdre **100 %** du journal des explications — l'erreur n'apparaissait qu'au commit, dans un bloc qui avale tout.
- **Alternatives** : champ `detail` libre avec consigne de ne pas y mettre de contenu (rejeté : c'est exactement le mode de fuite observé) ; suppression des lignes à la purge (rejeté : détruirait les métriques agrégées de coût et de latence).
- **Compromis** : le debug d'un prompt fautif ne peut pas s'appuyer sur le journal — il faut rejouer en local. Assumé.
- **Réévaluation** : jamais pour le principe. La **rétention 13 mois reste non implémentée** (voir 17, question nouvelle N4).
- **Vérifié par** : `tests/unit/ai/test_calls_journal.py`, `tests/unit/ai/test_ai_calls_purge.py`, `tests/unit/core/test_migration_0006.py`.

## D27 — Provider d'embeddings local déterministe par défaut, dimension validée au démarrage ✅ *(précise D06/D08)*
- **Décision** : `EmbeddingProvider` (`api/app/ai/embeddings/`) avec deux implémentations : `HashingEmbeddingProvider` (**défaut**, local, sans réseau ni clé — *hashing trick* signé sur mots + n-grammes, normalisé L2) et `ManagedEmbeddingProvider` (squelette, **inactif**, lève tant que Q11 n'est pas tranchée). Le condensat est **`blake2b`, jamais `hash()`** : le hachage natif de Python est randomisé par processus, l'API et les workers auraient écrit des vecteurs divergents. `check_embedding_dimension()` compare la dimension du provider à `EMBEDDING_DIM` du schéma (`vector(1024)`) **avant toute mise en cache** et refuse tout écart. La fabrique reprend le `CircuitBreaker` de la couche LLM.
- **Justification** : quatre fonctions écrites étaient inertes faute de vecteurs (similarité d'intitulé — 15 % du poids —, crédit « compétence proche », dédup étage 2, rerank hybride). Un provider local déterministe les active, se teste sans réseau ni clé, et ne préjuge pas de Q11. Un modèle de dimension différente corromprait silencieusement la base.
- **Alternatives** : attendre le choix du modèle managé (rejeté : quatre fonctions gelées et non testables) ; désactiver ces fonctions (rejeté : la chaîne n'aurait jamais été exercée de bout en bout).
- **Compromis** : les vecteurs sont **lexicaux, pas sémantiques** — « développeur backend » et « ingénieur serveur » restent éloignés. Tous les seuils produit (0,75 / 0,80–0,55 / 0,85 / 0,92) devront être recalibrés avec le modèle réellement retenu, et un changement impose un re-embedding **complet**.
- **Réévaluation** : à la résolution de Q11 (bloquante) — avec re-calibrage obligatoire et backfill forcé.
- **Vérifié par** : `tests/unit/embeddings/test_hashing_provider.py`, `test_factory.py`, `test_text.py`, `test_backfill.py`, `test_embed_profile_enqueue.py`.

## D28 — Dédup étage 2 neutralisée hors provider sémantique, + filtre géographique dur ✅ *(amende D13)*
- **Décision** : `_stage2_threshold()` (`api/app/modules/ingestion/service.py`) rend un seuil **inatteignable** (`STAGE2_DISABLED_THRESHOLD = 1.5`) tant que `EMBEDDINGS_PROVIDER` n'appartient pas à `SEMANTIC_EMBEDDING_PROVIDERS` (= `{"managed"}`). Sous le provider lexical par défaut, **seul l'étage 1 (hash exact) déduplique**. Indépendamment du cosinus, un filtre géographique dur (`STAGE2_MAX_DISTANCE_KM = 50`, haversine sur lieux géocodés) interdit toute fusion — il était exigé par la spec (07 §6.2.2) mais n'avait jamais été implémenté. Une divergence de dimension entre deux vecteurs stockés interdit également la comparaison.
- **Justification** : le seuil 0,92 de D13 a été fixé pour des vecteurs **sémantiques**. Mesuré en revue sur le provider lexical réellement actif : « Ingénieur DevOps » et sa variante « Senior » à **0,949** ; deux offres partageant titre et premier paragraphe mais publiées à **Paris et Lyon** à **1,0000**. La fusion est irréversible pour l'utilisateur — l'offre absorbée disparaît définitivement. Le biais doit aller au faux négatif, comme D13 l'exige.
- **Alternatives** : abaisser/relever le seuil (rejeté : aucun seuil n'est défendable sur des vecteurs lexicaux) ; garder l'étage 2 actif en acceptant les pertes (rejeté : perte de données).
- **Compromis** : les doublons multi-sources ne sont plus fusionnés au-delà du hash exact tant que Q11 n'est pas tranchée — la couverture produit annoncée pour F est donc partiellement en retrait.
- **Réévaluation** : réactivation **après** choix du modèle sémantique **et** calibration sur données réelles (Q12) — dans cet ordre, jamais l'inverse.
- **Vérifié par** : `tests/unit/ingestion/test_dedup_stage2.py` (les tests de calibration exercent désormais le provider réellement en usage sur du texte réaliste ; les précédents imposaient le cosinus avec des vecteurs synthétiques, ce qui est précisément pourquoi le défaut est passé inaperçu).

## D29 — Suite d'intégration PostgreSQL réelle, en gate de CI ✅ *(précise D06, complète 13)*
- **Décision** : `api/tests/integration/` exécute le **code réel** contre un **PostgreSQL 16 + pgvector réel**, schéma monté par les **migrations Alembic réelles** (testcontainers en local, service `pgvector/pgvector:pg16` en CI, `BOUSSOLE_TEST_DATABASE_URL` court-circuitant testcontainers). Marqueur `integration` exclu des `addopts` : ces tests ne tournent qu'en job dédié (`.github/workflows/boussole-ci.yml`, job `integration`, conditionné à un diff touchant `boussole/api/`) et via `make test-integration`.
- **Justification** : la suite unitaire n'exerce jamais de base — les dépôts sont doublés ou les requêtes seulement compilées. C'est ainsi qu'a été livré le bug de datetime naïf de M2 (500 sur toute page 2 paginée par date). La suite a immédiatement trouvé un bug produit vivant : le déclencheur `tsv` désaccentue le texte indexé mais la requête ne l'était pas — un francophone tapant « développeur », le cas nominal, ne trouvait **rien**.
- **Alternatives** : SQLite en mémoire (rejeté : ni `tsvector`, ni `pgvector`, ni `trigram`, ni les contraintes réelles) ; base partagée de CI (rejeté : la suite tronque les tables entre chaque test).
- **Compromis** : CI plus lente et un service de plus à ordonnancer, d'où le filtre par chemin calculé en `git diff`.
- **Réévaluation** : si la durée du job dépasse le budget de PR.
- **Vérifié par** : la suite elle-même — 7 fichiers, 61 tests : `test_jobs_search_pagination.py`, `test_jobs_fulltext_trigger.py`, `test_jobs_salary_filter.py`, `test_ingestion_dedup.py`, `test_sql_constraints.py`, `test_privacy_export.py`, `test_privacy_purge.py`.

## D30 — Mapping `datetime` timezone-aware global ✅ *(précise D06)*
- **Décision** : `type_annotation_map` sur la `Base` déclarative (`api/app/core/db.py`) mappe **tout** `datetime` Python vers `DateTime(timezone=True)`. La règle est portée par la classe de base, pas par chaque colonne.
- **Justification** : le schéma n'utilise que `timestamptz`. Sans ce mapping, asyncpg caste les binds en `TIMESTAMP WITHOUT TIME ZONE` et **rejette** les datetimes aware — la pagination keyset par date et le filtre `posted_since` renvoyaient 500. Une correction colonne par colonne aurait réintroduit le défaut au premier modèle suivant.
- **Alternatives** : `timezone=True` déclaré sur chaque colonne (rejeté : non tenable, la revue M2 a montré l'oubli) ; normaliser en naïf UTC côté applicatif (rejeté : perte d'information et conversions implicites).
- **Compromis** : aucun connu.
- **Réévaluation** : jamais.
- **Vérifié par** : `tests/integration/test_jobs_search_pagination.py` (régression du bind timezone-aware, contre PostgreSQL réel — le test unitaire ne pouvait structurellement pas l'attraper).

## D31 — `override_engine` : moteur `NullPool` dédié aux workers, non réentrant ✅ *(précise D12)*
- **Décision** : chaque tâche Celery construit un moteur dédié (`create_worker_engine()`, `NullPool`) et enveloppe sa coroutine dans `override_engine(engine)` (`api/app/core/db.py`), qui substitue temporairement le moteur **et** la fabrique de sessions **globaux**, puis restaure quoi qu'il arrive. Le contexte est **explicitement non réentrant** : une seconde entrée lève `EngineOverrideError`.
- **Justification** : les tâches exécutent leur cycle via `asyncio.run` (boucle neuve à chaque exécution) ; le moteur global poolé lierait des connexions asyncpg à une boucle déjà fermée. La substitution est nécessaire parce que le code des modules — notamment les `purge_user`/`export_user` du registre privacy (D21) — ouvre ses sessions via `get_session_factory()` et ne reçoit pas de moteur en paramètre. Sans garde de réentrance, deux substitutions imbriquées restauraient un moteur intermédiaire puis un moteur déjà disposé : sessions liées à une boucle morte, diagnostic impossible.
- **Alternatives** : injecter la fabrique de sessions dans chaque purger (rejeté au MVP : élargit l'interface de module de D21) ; moteur poolé partagé (rejeté : cassé par `asyncio.run`).
- **Compromis** : une tâche à la fois par processus, et un état global muté — d'où la garde bruyante.
- **Réévaluation** : si les purgers passent à une injection explicite, `override_engine` disparaît.
- **Vérifié par** : `tests/unit/test_hardening.py` (garde de réentrance), `tests/unit/privacy/test_registry.py`, `tests/unit/ingestion/test_worker_tasks.py`.

## D32 — Rate limiting fondé sur la session résolue et l'IP de proxy de confiance ✅ *(précise D17)*
- **Décision** : l'identité de seau (`app/main.py`) est `user:<uuid>` **si et seulement si** le cookie de session est **réellement résolu dans Redis** ; sinon `ip:<ip cliente>`. L'IP cliente ne lit `X-Forwarded-For` que si le pair immédiat figure dans `FORWARDED_ALLOW_IPS` (défaut restrictif `127.0.0.1`), et retient le **dernier saut de confiance** (parcours de droite à gauche). Le limiteur global est **fail-open** (D18) ; les routes qui ne peuvent pas s'ouvrir — quota d'export RGPD, `DELETE /account` — portent leur propre limiteur **fail-closed** (`modules/privacy/router.py`).
- **Justification** : deux défauts de revue M5, symétriques. (1) L'identité venait du cookie **présenté**, pas de la session résolue : un cookie aléatoire créait un seau neuf à chaque requête et annulait toute limite. (2) L'API tourne derrière le proxy Next.js : sans liste de confiance, tout le trafic anonyme partageait un unique seau de 60 req/min (auto-DoS trivial), et un usage naïf de `X-Forwarded-For` aurait laissé n'importe quel client forger son identité en préfixant l'en-tête.
- **Alternatives** : compter par cookie présenté (rejeté : contournable en une ligne) ; faire confiance à `X-Forwarded-For` inconditionnellement (rejeté : identité falsifiable) ; tout en fail-closed (rejeté : Redis volatile deviendrait un point de panne pour toute l'API).
- **Compromis** : une résolution de session Redis par requête ; les clients derrière un même NAT partagent un seau anonyme.
- **Réévaluation** : si le coût de résolution pèse sur la latence p95.
- **Vérifié par** : `tests/unit/test_hardening.py` (le limiteur est réellement exercé depuis M2 : les fabriques Redis sont posées sur `app.state`, les middlewares échappant à `dependency_overrides` — avant, seule la branche fail-open était testée), `tests/unit/privacy/test_delete_account.py`, `tests/unit/privacy/test_export_api.py`.

## D33 — Barrière PII déterministe et ancrage vérifié du corps généré ✅ *(précise D09/D10, RM-T-7)*
- **Décision** : `api/app/ai/scrubbing.py` applique un filtrage **déterministe par expression régulière** (e-mail, téléphone FR/international, IBAN, date de naissance, adresse, situation familiale 🟡) à la sortie d'extraction **et** au payload de profil des quatre prompts, en ne journalisant que les **catégories** retirées, jamais les valeurs. Côté anti-invention, le contrôle d'ancrage ne se contente plus de la liste de `claims` : le corps est confronté aux durées, rôles revendiqués et entités inconnues du payload de profil, et un `claim` dont le texte contredit l'élément référencé ne compte plus comme ancré.
- **Justification** : deux défauts de revue M4/M5. (1) Aucune barrière déterministe n'atteignait les prompts — la docstring affirmait à tort qu'`extra='forbid'` protégeait, alors qu'un schéma fermé interdit des **clés** hors schéma et n'empêche en rien une adresse e-mail de voyager dans un champ texte légitime (`headline`, `summary`, `evidence.quote`). (2) L'ancrage était contournable avec une **liste de claims vide** : un corps entièrement inventé passait « ancré », donc validable et exportable — la garantie produit la plus centrale de D10 ne tenait pas.
- **Alternatives** : s'en remettre à la consigne de prompt (rejeté : c'est le mode de fuite observé) ; s'en remettre au schéma fermé (rejeté : hors sujet, voir ci-dessus).
- **Compromis** : filtrage volontairement **conservateur** — un faux positif coûte une reformulation, un faux négatif expose une donnée personnelle à un tiers.
- **Réévaluation** : élargissement des motifs à mesure des cas réels ; les motifs adresse/situation familiale restent 🟡.
- **Vérifié par** : `tests/unit/generation/test_grounding_unit.py`, `test_generation_anchoring.py`, `tests/unit/embeddings/test_text.py`, `tests/unit/cv/test_extract_cv.py`, `tests/unit/cv/test_cv_safety.py`.

---

## Journal des mises à jour
- 2026-07-23 : création, D01–D15 actées pour le MVP (phases 1–10). Hypothèses 🟡 signalées : providers exacts, seuils de dédup, next-intl, liste initiale des connecteurs.
- 2026-07-23 (revue de phase 4–10) : ajout D16–D23 (issus de 10-system-architecture.md) ; résolution de l'ambiguïté `source_ref` de D13 (référence employeur, sinon vide — 07 §6.1 Q4 close) ; contrats API complétés (`GET /generations`, filtre `saved` sur `GET /jobs`) suite à la revue UX (03) ; questions ouvertes consolidées dans 17.
- 2026-07-28 (**M1 — fondations**) : monolithe modulaire (D01) et BFF Next.js (D11) confirmés à l'exécution — modules `auth`, Alembic `0001` (schéma intégral, extensions pgvector/pg_trgm/unaccent/citext), Celery + files, seeds. **Q18 tranchée par le code** : `next-intl` ^3.26 est en place (`web/i18n.ts`, parité fr/en vérifiée par script). Q31 tranchée conformément à l'hypothèse (réponse neutre à l'inscription). Les modules non encore livrés répondent **501 documenté** plutôt qu'un TODO silencieux (`app/core/problems.py`).
- 2026-07-28 (**M2 — ingestion + recherche**) : connecteurs France Travail / Greenhouse / Lever derrière feature flags (D04 tenu), dédup étage 1, recherche hybride avec pagination keyset (D07), migrations `0002`/`0003` (curseurs et compteurs d'absence persistés). Revue : **D30 actée** (mapping timezone-aware global) après un 500 sur toute page 2 paginée par date ; annualisation des salaires et normalisation pays corrigées. Q32 tranchée conformément à l'hypothèse (offres sans salaire incluses).
- 2026-07-28 (**M3 — matching + explications**) : moteur déterministe **12 dimensions** piloté par `scoring-config.json` (D02 tenu : `tests/unit/matching/test_purity.py` vérifie par AST **et** sous-processus l'absence d'import réseau/DB dans `app/matching`), score ≠ confiance (D03) et explications en deux couches (D14) avec garde de **diff numérique nul** entre facts et reformulation. Profils à provenance par champ et préférences en remplacement transactionnel (D05). Cas d'or UM-01…UM-18 gelés.
- 2026-07-28 (**M4 — CV, générations, candidatures**) : import CV (octets magiques, quotas, extraction pypdf/python-docx), générations sous validation humaine obligatoire (D10 : contrainte SQL + 409), candidatures à transitions libres historisées, migration `0004`. Revue : **D33 actée** — l'ancrage était contournable avec une liste de `claims` vide (corps entièrement inventé accepté comme ancré, donc exportable), et aucune barrière PII déterministe n'atteignait les prompts. Bombe de décompression DOCX (475 Ko → 1,3 Go) rejetée au dépôt.
- 2026-07-28 (**M5 — privacy + durcissement**) : module `privacy` (export RGPD à lien signé HMAC, suppression de compte, purge orchestrée par registre déclaratif — D21), migration `0005`. Revue : la purge **ne se terminait jamais** (le module `jobs` était resté un stub M1 : `saved_jobs` conservés indéfiniment, promesse des 30 jours de D09 rompue) ; l'export ne se construisait pas (contrat de stockage async déclaré contre le contrat sync livré). **D31** (garde de réentrance d'`override_engine`) et **D32** (identité de rate limiting) actées à cette occasion.
- 2026-07-28 (**M6 — mise en service**) : **D24** (backend de stockage + refus de démarrage, vocabulaire `ENV` fermé, durcissement dès staging), **D25** (fabrique LLM, circuit breaker, interdiction du repli implicite vers le factice), **D26** (journal `ai_calls` fermé au contenu), **D27** (embeddings locaux déterministes + validation de dimension), **D28** (neutralisation de la dédup étage 2 hors provider sémantique + filtre géographique dur), **D29** (suite d'intégration PostgreSQL en gate). Quatre des cinq garanties annoncées par le jalon ne tenaient pas à l'exécution malgré une suite verte ; chacun des correctifs est verrouillé par un test de non-régression vérifié en réintroduisant le défaut. ⚠️ **Le changement de tokenisation des embeddings invalide tout vecteur stocké : un backfill forcé est requis au déploiement** (voir 17, N3).

---

## D34 — Corpus de démonstration fictif, refusé hors développement ✅ *(lot post-M6 n° 1)*
- **Décision** : un quatrième connecteur, `demo-corpus`, lit un fichier local (`config/demo-corpus/jobs.json`) et le fait passer par la **vraie** chaîne d'ingestion. Ses offres sont inventées, ses URL sont sur le TLD réservé `.invalid` (RFC 2606) — vérifié au chargement, une URL résolvable fait échouer le fetch — et `build_demo_connector` **lève dès que `ENV` est durci**, staging compris. Le feature flag `FEATURE_SOURCE_DEMO` ne suffit donc pas à l'activer.
- **Justification** : les trois sources réelles attendent Q2/Q3, un arbitrage juridique. Sans offres, ni la recherche, ni le matching, ni surtout la **mesure de qualité** ne pouvaient être exercés — et la mesure est le chemin critique le plus long du projet (annotateurs, budget, protocole). Ce corpus lève le blocage pour la mesure sans rien préjuger du juridique.
- **Alternatives** : attendre Q2/Q3 (rejeté : gèle le seul travail qui n'en dépend pas) ; générer des offres à la volée dans les tests (rejeté : n'exerce ni la dédup, ni l'ingestion, ni les embeddings) ; utiliser un jeu d'offres réelles collecté à la main (rejeté : c'est exactement la question juridique qu'on ne veut pas préempter).
- **Compromis** : deux barrières plutôt qu'une, et une URL volontairement morte. Un corpus fictif visible par un utilisateur violerait l'interdiction de présenter des données fabriquées comme authentiques ; c'est le type d'accident qui arrive par une variable d'environnement oubliée, donc c'est le code qui refuse, pas la procédure.
- **Réévaluation** : le jour où une source réelle est homologuée. Le corpus reste utile pour la mesure — un jeu d'évaluation a besoin d'un corpus stable, pas d'un corpus frais.
- **Vérifié par** : `tests/unit/evaluation/test_dataset_and_corpus.py`.

## D35 — Harnais de mesure du matching, seuils lus sur la configuration ✅ *(lot post-M6 n° 1)*
- **Décision** : `app/evaluation` (métriques pures + chargement + exécution) mesure Spearman, NDCG@10 et précision/rappel des bloquants, et les confronte aux `evaluation_gates` de `scoring-config.json`. Les seuils **ne sont jamais recopiés dans le code** : ils sont portés par `ScoringConfig`. Spearman et NDCG sont évalués **par profil, le pire faisant foi** ; les bloquants sont agrégés. Commande : `make evaluate`, sortie non nulle si une porte tombe.
- **Justification** : les gates existaient depuis le premier jour et n'avaient jamais été exécutées — « aucun jeu annoté n'existe, aucune mesure n'a été faite ». Un seuil qu'on ne mesure pas n'est pas un seuil. Moyenner entre profils masquerait le profil pour lequel le moteur classe à l'envers, or c'est celui-là qu'il faut voir.
- **Alternatives** : `scipy.stats.spearmanr` (rejeté : deux dépendances lourdes pour trois formules, et écrire les rangs à la main force à traiter les ex æquo — la formule courte `1-6Σd²/n(n²-1)` est fausse dès qu'il y en a) ; moyenne des profils (rejeté, voir ci-dessus).
- **Compromis** : le jeu livré est fait de **cas de référence construits**, pas d'annotations humaines d'offres réelles (N16). L'instrument est réel ; son verdict actuel ne répond pas à « le matching est-il bon ».
- **Résultat de la première exécution** : bloquants parfaits (précision 1,00, rappel 1,00), NDCG@10 ≥ 0,907 sur les trois profils, et **Spearman à 0,570 sur un profil, sous la porte de 0,60**. Deux causes identifiées et chiffrées : N14 (`title_similarity` inerte) et N15 (couverture favorisant les offres maigres). Elles sont épinglées par test de caractérisation, **délibérément non corrigées** — un jeu recalé sur la sortie du moteur ne mesure plus rien.
- **Réévaluation** : à chaque changement de `scoring_version`, et à l'arrivée d'un vrai jeu annoté.
- **Vérifié par** : `tests/unit/evaluation/test_metrics.py`, `test_measured_state.py`.

## D36 — Un cosinus n'est interprété qu'avec les seuils calibrés pour son modèle ✅ *(lot post-M6 n° 2, corrige N14)*
- **Décision** : la dimension `title_similarity` déclare dans `scoring-config.json` le modèle pour lequel ses seuils ont été mesurés (`calibrated_for_model`) ; `JobInput` porte le modèle qui a produit le vecteur (`title_embedding_model`, alimenté par le provider actif). **Discordance ⇒ dimension INCONNUE** (`uncalibrated_embeddings`), renormalisée hors du score **et** de l'indice de confiance — jamais un sous-score. La valeur livrée est `null` : ces seuils n'ont été calibrés contre aucun modèle. `scoring_version` passe à `1.1.0`, ce qui invalide le cache `match_results`.
- **Justification** : `zero_below` / `one_above` découpent une échelle qui dépend entièrement de la famille de vecteurs. Appliquer les seuils d'un modèle sémantique à un condensat lexical ne produit pas une mesure imprécise, mais une mesure **fausse présentée comme un fait**. Mesuré avant correction sur les 36 paires du jeu d'évaluation : sous-score **0,00 partout**, statut **connu**. 15 % du poids ne discriminaient rien, abaissaient uniformément tous les scores, et surtout gonflaient la confiance — 97,2 de moyenne pour une dimension muette. Après : 82,2. Un sous-score de 0 est une affirmation (« ces métiers n'ont rien à voir ») ; une inconnue est un aveu. Seul le second était vrai.
- **Alternatives** : booléen « faire confiance aux vecteurs » (rejeté : ne dit pas *pour quoi* la config est calibrée, et n'attrape pas le changement de modèle) ; recalibrer les seuils pour le provider lexical (rejeté : on calibrerait sur un provider qu'on sait provisoire, et Q11 remettrait tout à plat) ; laisser en l'état en le documentant (rejeté : c'est l'indice de confiance qui mentait, pas seulement le score).
- **Compromis** : la dimension est inactive tant que Q11/Q12 ne sont pas tranchées — 15 % du poids sortent du calcul. C'est le prix d'un chiffre honnête, et la renormalisation existe précisément pour ça. Le rapprochement se fait sur le provider **actif**, pas sur la provenance réelle de chaque ligne : `job_postings` n'a pas de colonne `embedding_model_version` (§8.2 item 12, toujours ouvert), un vecteur calculé par un modèle précédent reste indiscernable d'un vecteur à jour.
- **Bénéfice non recherché mais décisif** : le garde-fou protège surtout le sens inverse. Brancher un provider sémantique sans recalibrer produirait des sous-scores **plausibles et faux** — infiniment plus difficiles à repérer qu'un zéro constant. Le même contrôle les attrape.
- **Réévaluation** : au moment de renseigner `calibrated_for_model`, c'est-à-dire quand les seuils auront été mesurés contre un modèle réel.
- **Vérifié par** : `tests/unit/matching/test_calibration_guard.py`, `test_shipped_config.py`, `tests/unit/evaluation/test_measured_state.py`.

## D37 — Une inconnue due à l'outil ne met en cause ni le profil ni l'offre ✅ *(lot post-M6 n° 2)*
- **Décision** : nouveau code de raison `unavailable` dans le contrat (`openapi.yaml`, `UnknownReason`, types front, i18n fr/en), distinct de `job_not_provided`, `profile_not_provided` et `low_extraction_confidence`.
- **Justification** : D36 crée une inconnue dont la cause est **notre** outil. La replier sur `low_extraction_confidence` — le repli par défaut du mapping — aurait affiché « information extraite de l'offre incertaine » : une accusation fausse portée sur l'annonce, et une hypothèse présentée comme un fait, exactement ce que les règles de sûreté IA interdisent. `profile_not_provided` aurait été pire encore : il invite l'utilisateur à compléter un profil qui n'a aucun défaut.
- **Alternatives** : réutiliser un code existant (rejeté, voir ci-dessus) ; ne rien exposer et masquer la dimension (rejeté : la transparence sur ce qui n'a pas pu être évalué est un principe produit, et l'utilisateur doit pouvoir comprendre pourquoi sa confiance n'est pas à 100).
- **Compromis** : un ajout de valeur à une énumération du contrat. Le front le traite explicitement ; un client tiers qui ne connaîtrait pas la valeur devra la gérer comme inconnue.
- **Vérifié par** : `tests/unit/evaluation/test_measured_state.py::test_la_raison_ne_met_en_cause_ni_le_profil_ni_loffre`, parité i18n.

## D38 — Le facteur `k` est continu : la preuve partielle pèse à proportion ✅ *(lot post-M6 n° 3, corrige N15)*
- **Décision** : `DimensionOutcome` porte un `weight_factor` ∈ ]0,1] et le moteur pondère par le **poids effectif**. Pour les dimensions de couverture de compétences, ce facteur vaut `min(1, n / evidence_full_count)` où `n` est le nombre d'exigences retenues et le seuil vient de `scoring-config.json` (valeur 3). Le `weight` exposé dans le résultat est l'**effectif** — l'utilisateur voit ce qui a réellement compté. Score **et** confiance suivent la même règle.
- **Justification** : `skills_required` (25 %, la dimension la plus lourde) notait en couverture. Une offre n'exigeant qu'une compétence banale, que le candidat possède, obtenait 1,00 ; une offre pertinente listant cinq exigences dont quatre satisfaites plafonnait à 0,80. Mesuré sur l'application réelle : un poste « Développeur Python Junior » sur site sortait **en tête** pour un profil backend senior. Les vraies annonces variant énormément dans le soin de leur rédaction, le biais favorisait systématiquement les plus vagues. Le sous-score n'est pas en cause — la couverture *est* de 100 % — c'est le poids accordé à une information mince qui l'était.
- **Alternatives** : lissage bayésien du sous-score vers une moyenne (rejeté : interdirait à jamais d'atteindre 1,00, donc de marquer 100 sur une offre parfaitement couverte — une promesse produit qu'on ne casse pas pour corriger un biais) ; seuil minimal d'exigences en dessous duquel la dimension devient inconnue (rejeté : trop brutal, une exigence porte quand même de l'information) ; ne rien faire et documenter (rejeté : la porte Spearman du projet était en échec à cause de ça).
- **Compromis** : la confiance n'atteint plus 100 que si toutes les dimensions ont une preuve pleine. C'est voulu et cohérent avec D36 : ne pas revendiquer une certitude qu'on n'a pas. **Limite mathématique documentée** : quand la dimension atténuée est la SEULE connue, le facteur se simplifie à la renormalisation et n'a aucun effet — juste, puisqu'alors le score *est* la couverture.
- **Mesuré, pas raisonné** : Spearman du pire profil 0,526 → 0,714 (porte 0,60), NDCG@10 0,907 → 0,956, bloquants inchangés. Le correctif tient pour le paramètre valant 2, 3, 4 **ou** 5 : c'est le mécanisme qui corrige, pas la constante.
- **Réévaluation** : à la première mesure sur jeu annoté humain (N16), qui pourra affiner `evidence_full_count`.
- **Vérifié par** : `tests/unit/matching/test_evidence_weighting.py` (dont un test qui **reproduit le défaut** en rechargeant la config sans le paramètre : 88 contre 86, l'ordre s'inverse), `tests/unit/evaluation/test_measured_state.py`.

## D39 — « Requis » est une contrainte : l'hybride bloque aussi ✅ *(lot post-M6 n° 3, tranche N13)*
- **Décision** : `remote.blocking_policies` dans `scoring-config.json` (`{"required": ["onsite", "hybrid"]}`) remplace la condition en dur du moteur. Un candidat dont la préférence est `required` reçoit le bloquant `remote_required` sur une offre **hybride** comme sur une offre sur site. Le sous-score hybride reste à **0,4** et l'offre reste visible.
- **Justification** : le vocabulaire de préférence distingue déjà `required` de `preferred`. Si `required` ne bloque pas, les deux niveaux deviennent indiscernables dans les faits et le mot ment. Un poste hybride impose une présence certains jours : pour qui ne peut pas venir — la raison même de cocher « requis » —, il est aussi inaccessible qu'un poste sur site. Sans badge, un candidat pouvait bâtir une candidature complète autour d'un poste qu'il ne pourrait pas accepter.
- **Alternatives** : conserver la spec initiale et renommer le niveau en « fortement souhaité » (rejeté : déplace le problème sur l'interface et perd la capacité d'exprimer une vraie contrainte) ; bloquer ET mettre le sous-score à 0 (rejeté : un arrangement hybride se négocie parfois, et un bloquant n'a jamais eu vocation à annuler un score — 06 §1).
- **Compromis** : plus de bloquants affichés qu'avant pour ce profil. Acceptable parce qu'ils sont **justes** : la mesure donne 12 bloquants, précision et rappel à 1,00. Élargir au-delà de `required` banaliserait le badge et le rendrait illisible — d'où une configuration par préférence plutôt qu'une règle globale.
- **Réévaluation** : à l'usage réel, si les utilisateurs signalent des offres hybrides négociables badgées à tort.
- **Vérifié par** : `tests/unit/matching/test_blocking.py::TestTeletravailExigeFaceAUnPosteHybride`.

## D40 — Un amorçage vérifiable plutôt qu'une procédure ✅ *(finalisation)*
- **Décision** : `make demo` (`app/demo.py`) amène une base **vide** à une application utilisable — migrations, référentiels, ingestion du corpus **par la chaîne de production**, embeddings, compte au profil **validé** — et **vérifie son propre résultat** : offres actives, offres vectorisées, recherche plein texte non vide, profil validé présent. Sortie non nulle sinon.
- **Justification** : « il suffit de lancer les migrations puis de seeder » est une phrase de documentation, pas une garantie. Monter ce chemin pour de vrai a trouvé **quatre défauts** qu'aucune suite ne voyait : chargement paresseux dans la dédup étage 2 (offres **perdues** en silence), contrat de connecteur incapable d'exprimer compétences souhaitées et secteur (14 % du poids morts pour toute source à règles), vocabulaire du corpus non traduit (échec sur l'énumération PostgreSQL), et une suite de tests qui n'exerçait que la branche dégradée du rate limiting. Le profil **validé** est le détail décisif : un profil `draft` fait répondre 409 à toutes les routes de matching, et l'application paraît cassée alors qu'elle applique sa règle.
- **Alternatives** : script de seed SQL direct (rejeté : n'exerce ni la normalisation, ni la dédup, ni les embeddings — donc ne prouve rien sur la chaîne) ; jeu de données figé chargé par `COPY` (rejeté pour la même raison, et se périme silencieusement).
- **Compromis** : la commande refuse de s'exécuter hors développement, et le corpus est fictif. Ce n'est pas un outil de démonstration commerciale.
- **Vérifié par** : exécution réelle contre PostgreSQL 16 depuis une base vide, puis parcours de l'API en fonctionnement (connexion, recherche, matching, sources, préférences, candidatures).

## D41 — Idempotence et verrous partagés, jamais en mémoire de processus ✅ *(finalisation)*
- **Décision** : `Idempotency-Key` des candidatures dans le Redis volatile (TTL 24 h, portée par utilisateur) ; verrou d'ingestion par **bail à jeton** (`app/core/locks.py`), le cycle **renonce** au lieu d'attendre.
- **Justification** : le cache d'idempotence vivait dans un dictionnaire de processus. Derrière deux répliques d'API — le déploiement normal — un double-clic tombait une fois sur deux sur l'instance qui n'avait rien vu, et créait le doublon que la clé existait pour empêcher ; aucun test mono-processus ne pouvait le montrer. Côté ingestion, deux cycles concurrents lisent le même curseur de départ et le second peut faire reculer celui du premier.
- **Alternatives** : table SQL d'idempotence (rejetée au MVP : le Redis volatile suffit pour une fenêtre de rejeu courte, et le pire cas est le doublon qu'on avait déjà) ; verrou sans bail (rejeté : un worker tué gèlerait la source **pour toujours**, la panne la plus pénible à diagnostiquer) ; libération sans jeton (rejetée : un worker dont le bail a expiré libérerait le verrou d'un autre, remettant deux cycles en parallèle) ; script Lua pour l'atomicité (rejeté : ferait dépendre la testabilité d'un interpréteur Lua — une transaction `WATCH`/`MULTI` donne la même garantie).
- **Compromis** : l'idempotence reste un cache de **rejeu**, pas un verrou distribué — deux requêtes strictement simultanées peuvent encore créer deux lignes. Dit explicitement plutôt que sous-entendu.
- **Amendement (revue de finalisation)** : trois trous dans la même famille « ça marche à un exemplaire ». (a) Les clients Redis **singletons** étaient réutilisés par les tâches Celery, alors qu'`asyncio.run` ouvre une boucle d'événements neuve à chaque tâche : le remboursement de quota ne marchait qu'une fois sur deux et les sessions d'un compte purgé lui survivaient, sans qu'aucun test le voie (fakeredis ne lie pas ses connexions à une boucle). Client dédié par cycle, plus un contrôle structurel sur le texte des modules exécutés par Celery. (b) `refund` faisait `GET` puis `DECR` : mesuré à **−4** avec six processus concurrents, la fenêtre autorisant ensuite 12 appels pour une limite de 5 — passé en transaction `WATCH`/`MULTI`. (c) `reconcile` s'exécutait **hors verrou**, alors que c'est le cycle qui réécrit le plus de lignes.
- **Vérifié par** : `tests/unit/applications/test_idempotency_shared.py` (deux services, un magasin partagé), `tests/unit/core/test_locks.py`, `tests/unit/core/test_redis_worker_loop.py`.

## D42 — Observabilité et e-mail : livrés, ou retirés, jamais inertes ✅ *(finalisation)*
- **Décision** : `SENTRY_DSN` est **lu** ; un `logger.error` devient un événement (les alertes de conformité atteignent donc quelqu'un) ; les données personnelles sont retirées avant envoi ; un DSN configuré sans le paquet **fait échouer le démarrage**. `OTEL_EXPORTER_OTLP_ENDPOINT` est **retirée**. L'e-mail transactionnel part par **SMTP**, et la confirmation de suppression de compte est envoyée.
- **Justification** : ces deux variables étaient déclarées et lues par personne. Le système émet `purge_backlog_detected` quand une purge RGPD est en retard — un engagement légal en train d'être rompu — et cette alerte partait sur stdout. Côté e-mail, une demande de suppression aux conséquences irréversibles ne laissait **aucune trace** à son titulaire : une demande faite depuis une session volée passait inaperçue.
- **Alternatives** : dépendance Sentry obligatoire (rejetée : tout le monde ne l'utilise pas) ; laisser les variables inertes en les documentant (rejeté : une variable qui ne fait rien induit en erreur plus sûrement qu'une variable absente) ; API d'un fournisseur d'e-mail (rejetée : le choix est Q15 et suppose un arbitrage — SMTP ne préempte rien).
- **Compromis** : pas de traces distribuées. Le `trace_id` reste propagé dans les logs JSON.
- **Point de vigilance** : ce produit manipule des CV. Le nettoyage des événements est une **fonction pure testée sans le paquet installé** — faire dépendre un contrôle de confidentialité d'une dépendance optionnelle reviendrait à ne pas le tester en CI.
- **Amendement (revue de finalisation) — liste blanche, pas liste noire.** La première version énumérait ce qu'elle retirait. En exécutant le vrai SDK, la revue a montré que **huit chemins portaient encore des données** : l'adresse de l'utilisateur et le sujet « demande de suppression de compte » partaient par les fils d'Ariane construits depuis les journaux `INFO`, puis se rattachaient à n'importe quelle erreur ultérieure du processus ; s'y ajoutaient `request.query_string` (la requête de recherche d'emploi, qui peut révéler une santé ou une reconversion), `extra`, `contexts`, `tags`, `user`, `message`, `logentry`. Énumérer ce qu'on retire est une course perdue : chaque nouveau champ du SDK, chaque `extra` ajouté par un développeur, passe à travers. `scrub_event` ne conserve désormais que des champs dont on sait qu'ils ne portent pas de données et **retire tout le reste** ; les fils d'Ariane issus des journaux sont coupés (`level=None`, `max_breadcrumbs=0`). Le principe conservé : garder la **forme**, jeter les **valeurs** — le gabarit `"mail_envoi_echoue destinataire=%s"` reste, l'adresse non. Échouer du côté d'un rapport d'erreur moins riche est le bon sens de l'échec.
- **Amendement — STARTTLS avec contexte explicite.** `starttls()` sans argument retombe sur un contexte qui ne vérifie ni le certificat ni le nom d'hôte : la revue a fait ressortir le mot de passe SMTP du service en clair côté intercepteur. L'envoi passe par `asyncio.to_thread` (il gelait la boucle d'événements) et la construction du message est **dans** le `try` (une adresse contenant un retour chariot faisait lever `EmailMessage`, alors que le contrat promet de ne jamais lever).
- **Vérifié par** : `tests/unit/core/test_observability.py`, `tests/unit/privacy/test_deletion_email.py`, `tests/unit/core/test_hardening_guard.py`, et un envoi réel contre un serveur SMTP.

## D43 — Une offre ne se perd jamais sur une donnée secondaire ✅ *(revue de finalisation)*
- **Décision** : un code secteur absent du référentiel `sectors` est **écarté avec un avertissement** au lieu d'être propagé jusqu'à la clé étrangère. Le connecteur de démonstration le valide en amont, comme il valide déjà `contract` et `remote`.
- **Justification** : `job_postings.sector_code` est une clé étrangère vers dix sections NACE. Un code hors référentiel — une source publiant `62.01Z` au lieu de `J`, ce qui est le format NAF courant — levait un `IntegrityError` que le savepoint par item convertissait en `errors += 1` : **l'offre entière disparaissait**, et une telle source perdait 100 % de ses annonces, une par une. Le secteur pèse 4 % et le moteur sait renormaliser sur le connu : l'écarter coûte une dimension, le propager coûte tout.
- **Alternatives** : élargir le référentiel aux codes NAF complets (rejeté : c'est un travail de taxonomie, pas un correctif de robustesse — et il resterait toujours un code hors liste) ; faire échouer bruyamment l'item (rejeté : c'est le comportement qu'on corrige) ; retomber sur un secteur « autre » (rejeté : inventerait une donnée, interdit par les règles de sûreté).
- **Compromis** : une source mal adaptée perd sa dimension secteur en silence si personne ne lit les journaux. Le WARNING nomme l'offre et le code, et pointe l'adaptateur à corriger.
- **Vérifié par** : `tests/integration/test_ingestion_sector_fk.py` (clé étrangère réelle ; le test échoue sur le code d'avant), `tests/unit/ingestion/test_enrichment_paths.py`.

## D44 — L'ingestion doit ENRICHIR une offre, pas seulement la créer ✅ *(revue de finalisation)*
- **Décision** : `sector_code` et le drapeau `required` des compétences sont désormais mis à jour sur les deux chemins de reprise — remplacement direct pour la même source (07 §4.4), arbitrage par confiance entre sources concurrentes (§6.3). Un libellé cité à la fois en exigé et en souhaité ne donne qu'**une** ligne, l'exigé l'emportant, à la création comme à la fusion.
- **Justification** : trois défauts de la même famille, tous silencieux, tous trouvés en rejouant deux cycles d'ingestion contre PostgreSQL. Le secteur n'était écrit qu'à la création : une offre née avant que sa source ne le publie le gardait `NULL` **à vie**, et la dimension restait inconnue par construction — exactement ce que D38 et le corpus prétendaient corriger. Le drapeau `required` était figé sur ce qu'en disait la **première** publication : une compétence promue en exigence continuait d'être pesée à 10 % au lieu de 25 %, et l'inverse. Le doublon, lui, faisait compter la même compétence deux fois (25 + 10 %) et l'affichait dans les deux colonnes — et le **même flux donnait un résultat différent** selon qu'il créait ou rattachait, ce qui est le genre d'incohérence dont on ne soupçonne pas l'existence.
- **Alternatives** : traiter le libellé ambigu comme « souhaité » (rejeté : l'offre affirme l'exigence, et `skills_required` n'étant pas bloquante, la retenir ne peut pas inventer de rejet dur) ; laisser la source concurrente écraser le drapeau au dernier cycle (rejeté : l'ordre d'arrivée des sources n'est pas une information).
- **Pourquoi aucune suite ne le voyait** : les douze offres du corpus de démonstration naissent complètes, avec leur secteur, sans recouvrement entre exigé et souhaité, et ne sont jamais republiées enrichies. Un corpus commode masque exactement les chemins qu'il devrait exercer.
- **Vérifié par** : `tests/unit/ingestion/test_enrichment_paths.py` (7 des 11 tests échouent sur le code d'avant).

## D45 — Un amorçage qui perd une offre ne dit pas « utilisable » ✅ *(revue de finalisation)*
- **Décision** : `make demo` compare le nombre d'offres **reçues** au nombre d'offres **traitées** (créées + mises à jour + rattachées) et remonte `errors` dans son verdict. Le contrôle porte sur le compte rendu d'ingestion, pas sur le nombre de lignes en base.
- **Justification** : le savepoint par item est le bon comportement — une offre en échec est annulée seule et le batch continue — mais personne ne lisait `errors`. Sur un corpus de douze offres dont une échouait, l'amorçage affichait « 11 créées » puis « ✅ Application utilisable » et sortait en 0. C'est précisément la sortie sur laquelle on s'appuie pour conclure que l'environnement est sain et aller chercher le problème ailleurs. D40 a bouché la cause connue sans installer la détection.
- **Alternatives** : compter les lignes `job_postings` (rejeté : une offre rattachée par déduplication est traitée et ne crée pas de ligne — le contrôle crierait à chaque fois que la dédup fait son travail).
- **Compromis** : côté worker, `errors` figure dans le journal `ingestion_cycle_success` mais reste sans métrique ni alerte. C'est une lacune connue, distincte de l'amorçage.
- **Vérifié par** : `tests/unit/core/test_demo_accounting.py`.

## D46 — Un seul registre de modèles, importé par tout processus qui touche l'ORM ✅ *(revue avant déploiement)*
- **Décision** : `app/models_registry.py` importe les dix modules de modèles. `alembic/env.py` et `app/workers/celery_app.py` l'importent. Un module ajouté sans y figurer fait échouer `tests/unit/core/test_models_registry.py`, qui compare la liste au contenu réel de `app/modules/*/models.py` et force la résolution de toutes les clés étrangères.
- **Justification** : deux pannes graves, cause identique, trouvées le même jour par deux revues indépendantes. (a) `env.py` n'importait qu'`auth` : `Base.metadata` connaissait **3 tables sur 37**, et `alembic revision --autogenerate` produisait un `upgrade()` contenant **33 `drop_table`** — dont `ai_calls` (treize mois de conservation obligatoire) et `audit_log` (la preuve des purges RGPD). La commande qu'on tape pour écrire la migration suivante écrivait la destruction de la base. (b) Le processus Celery n'importait pas `applications`, alors que `generated_documents.application_id` porte une clé étrangère vers cette table : **tout flush ORM d'un document généré échouait**, donc e-mail, lettre de motivation, CV adapté et optimisation de CV étaient **intégralement inopérants**. Silencieusement — l'API répondait 202, le document restait `pending` pour toujours, et l'utilisateur lisait « Rédaction en cours… » sans limite de temps.
- **Le mécanisme à retenir** : une métadonnée SQLAlchemy incomplète ne lève pas là où on l'a laissée incomplète. Elle lève ailleurs, dans un autre processus — ou pire, elle ne lève pas et fait dire à un outil que ce qu'il ne voit pas n'existe plus.
- **Alternatives** : importer les modèles à la demande dans chaque tâche (rejeté : c'est ce qui a produit le défaut) ; donner un modèle ORM aux quatre tables gérées en SQL brut (rejeté : inventer une abstraction que personne n'utilise pour satisfaire un outil).
- **Complément** : `include_object` refuse à l'autogenerate tout ce qui est présent en base et absent des modèles — les quatre tables sans modèle et les quinze index/contraintes que SQLAlchemy ne sait pas déclarer (index partiels, GIN trigram, HNSW). Contrepartie assumée : un index réellement retiré d'un modèle devra être supprimé à la main. C'est le bon sens de l'échec.
- **Vérifié par** : `tests/unit/core/test_models_registry.py`, et par exécution — `upgrade()` généré sur base à jour est désormais **vide**.

## D47 — Les paramètres SQL ne sortent jamais dans le texte d'une erreur ✅ *(revue avant déploiement)*
- **Décision** : `hide_parameters=True` sur les deux moteurs (`app/core/db.py`).
- **Justification** : le `str()` d'une `IntegrityError` embarque `[SQL: …]` **et** `[parameters: …]`, quel que soit `echo`, quel que soit `DEBUG`. Or ces paramètres sont le contenu du produit. Mesuré en `ENV=production`, `DEBUG=false`, sur une simple violation de clé étrangère déclenchable par n'importe quel utilisateur authentifié : une expérience portant « arrêt de travail longue durée suite à burn-out » ressortait **en clair sur stdout**, deux fois, et repartait telle quelle vers Sentry dans `exception.values[].value` — que la liste blanche conserve par construction. `check_hardening_configuration` refuse `DEBUG=true` pour exactement ce motif : il couvrait le cas nominal et ratait le cas d'erreur.
- **Compromis** : un diagnostic d'erreur SQL demande de reproduire la requête. Acceptable devant un transfert de données de santé inférables vers un sous-traitant tiers, hors registre.
- **Vérifié par** : reproduction dans les deux sens (avec et sans le drapeau, même requête, même erreur).

## D48 — Ce qui n'est pas destiné au public ne s'expose pas dès que l'environnement est durci ✅ *(revue avant déploiement)*
- **Décision** : `openapi_url` **et** `docs_url` conditionnées à `is_hardened` (donc fermées dès staging). Plafond de corps de requête global à 12 Mo. Secrets refusés s'ils sont vides, trop courts (< 32 caractères) ou égaux au défaut du dépôt. SMTP en clair refusé même **sans** authentification.
- **Justification** : quatre expositions mesurées. (a) Le schéma OpenAPI — 73 Ko, 36 routes — était servi **sans authentification en production**, docstrings comprises : « scan antivirus hors périmètre », « le jeton de session posé est un leurre invalide », « oracle de mot de passe pour quiconque a volé un cookie ». La carte des faiblesses connues, offerte à qui la demande. (b) Swagger UI était entièrement ouvert **en staging**, `docs_url` étant conditionnée à `is_production` quand tous les autres garde-fous avaient migré vers `is_hardened`. (c) Aucune borne de corps : 8 requêtes de 100 Mo depuis un client **non authentifié** faisaient monter le processus à 1,94 Go — un OOMKill déclenché par une ligne de shell. (d) `PRIVACY_SIGNING_KEY=` (vide) démarrait en production : le pseudonyme conservé dans `audit_log` après purge devenait recalculable **sans aucun secret**, donc une personne supprimée était ré-identifiable à partir d'une sauvegarde en testant un UUID — l'inverse exact de ce que promet la docstring de `subject_key_for`.
- **Alternatives** : protéger le schéma par authentification (rejeté : le contrat public destiné à la lecture est `cv-job-matching/openapi.yaml`, qui n'a pas ces docstrings) ; borner le corps au niveau du proxy seulement (rejeté : l'API doit tenir seule, elle est déployable sans lui).
- **Vérifié par** : `tests/unit/core/test_deployment_hardening.py` (20 tests), matrices exécutées sur les trois environnements.

## D49 — Une panne d'infrastructure ne devient pas une panne de fonction ✅ *(revue avant déploiement)*
- **Décision** : `celery beat` écrit son état hors du répertoire de travail ; `visibility_timeout` (900 s) et `task_reject_on_worker_lost` posés ; limites de durée douce/dure sur les tâches ; enfilement Celery borné et factorisé dans `app/core/enqueue.py`, avec deux régimes explicites (échec remonté en 503, ou best-effort rattrapé par un beat) ; le limiteur de la connexion dégrade au lieu de rendre 500 ; les échecs du fournisseur LLM sur l'explication rendent 503 et non 500.
- **Justification** : cinq pannes mesurées. (a) `beat` sortait en **code 1 immédiatement** dans l'image livrée — CWD non inscriptible pour l'utilisateur non privilégié — donc boucle de redémarrage et **rien n'était jamais planifié**, `maintenance.purge_due_accounts` compris : l'engagement RGPD des 30 jours, rompu en silence, sans healthcheck pour le dire. (b) `acks_late` seul ne suffit pas : le défaut de kombu-redis rend le message au bout d'**une heure**, pendant laquelle le document reste `parsing` devant l'utilisateur. (c) Un correctif d'enfilement documenté et mesuré (« 19,18 s ») n'avait été appliqué qu'à **un** des trois appels : l'import de CV et la génération gelaient encore toute la boucle d'événements de l'instance. (d) Le Redis de cache tombé rendait la **connexion entièrement impossible** (12 × 500) pendant que le limiteur global partait en fail-open — le pire des deux mondes. (e) Tout hoquet du fournisseur d'IA sortait en 500 « Erreur interne » au lieu du message prévu, qui dit vrai et rassure : « le score et les critères détaillés restent accessibles ».
- **Compromis** : laisser passer les connexions pendant une panne de cache affaiblit la protection anti-force-brute le temps de l'incident. Le mot de passe reste haché, l'audit reste écrit, et D17 dit déjà que la perte du Redis volatile est acceptable — une panne de cache ne doit pas devenir une panne d'authentification.
- **Vérifié par** : `tests/unit/core/test_deployment_hardening.py`, `tests/unit/core/test_models_registry.py`.

## D50 — L'image et le compose doivent produire une application qui marche ✅ *(revue avant déploiement)*
- **Décision** : `output: "standalone"` et `web/public/` ajoutés (sans quoi l'image web ne se construit pas) ; `api/config/` copié dans l'image API ; `SCORING_CONFIG_PATH` réellement lue ; le proxy BFF accepte `API_INTERNAL_URL` **et** `API_URL` ; `x-forwarded-for` transmis ; en-têtes de sécurité et `poweredByHeader: false` posés par le front ; `.dockerignore` ajouté.
- **Justification** : dans l'état, **le déploiement ne pouvait pas aboutir**. (a) `Dockerfile.web` copiait `.next/standalone` et `public/`, dont aucun n'existait — le commentaire du Dockerfile demandait lui-même `output: "standalone"`, que personne n'avait ajouté. (b) Le compose posait `API_INTERNAL_URL`, le code lisait `API_URL` : **100 % des appels API** finissaient en 500 sur `localhost:8000`, inexistant dans le conteneur. (c) `Dockerfile.api` ne copiait pas `config/` : l'image démarrait, servait les pages, et la **première recherche** rendait 500 — la fonction centrale du produit, en panne dans l'image seulement, sans recours par configuration puisque `SCORING_CONFIG_PATH` était déclarée et ignorée. (d) `X-Forwarded-For` n'avait aucun émetteur : tout le trafic anonyme partageait un seau de quota unique, et un script à 1 req/s empêchait **toute** connexion et **toute** inscription pour tout le monde. (e) 12 §1 et 09 §215 promettent « CSP/HSTS posés par le front/edge » : aucun n'était posé, et aucun manifeste d'edge n'existe dans le dépôt — une promesse déléguée à une couche qui n'existe pas n'est pas déléguée, elle est absente.
- **Le mécanisme à retenir** : rien de tout cela n'était visible en développement, où l'on ne construit pas les images, où le front et l'API tournent sur `localhost`, et où `config/` est là parce que le dépôt est là. Un environnement de développement commode masque exactement ce que le déploiement exerce.
- **Vérifié par** : build Next réel (`server.js` produit), proxy réel devant un faux API (l'en-tête arrive, et Next le pose lui-même quand rien n'est en amont), démarrage à froid depuis une base vide.

## D51 — La liste d'offres porte le score, et « trier par compatibilité » trie ✅ *(affinage produit)*
- **Décision** : `GET /jobs` joint `match_results` sur `(profile_id, scoring_version)` et peuple `JobCard.match`. `sort=match` ordonne par score décroissant ; les offres non scorées prennent la valeur de substitution `-1` et se rangent après. Le repli sur la pertinence ne demeure que pour un utilisateur **sans profil validé**, qui n'a aucun score.
- **Justification** : deux commentaires « M2 » oubliés sur la fonction centrale du produit. `JobCard.match` était documenté « toujours `null` au M2 » et `sort=match` « retombe sur `relevance` tant que le scoring n'est pas livré (M3) » — or M3 était clos, `/matches` rendait des scores, le front affichait un sélecteur « Compatibilité » et un `MatchBadge` par carte, et le tableau de bord renvoyait vers `/offres?sort=match`. Mesuré : `sort=match` et `sort=relevance` rendaient un ordre **identique, octet pour octet**. Le produit conduisait donc l'utilisateur depuis un écran qui affiche des scores vers un écran où ils disparaissent et où le tri annoncé ne fait rien.
- **Alternatives** : recopier le score dans `job_postings` (rejeté : deux sources de vérité pour le chiffre central) ; scorer à la volée pendant la recherche (rejeté : le moteur est déterministe mais la recherche est la requête la plus chaude, et `match_results` existe précisément comme cache).
- **Choix de conception** : `COALESCE(score, -1)` plutôt que `NULLS LAST`. La pagination keyset compare un tuple `(score, id)` ; un `NULL` y rend toute comparaison indéterminée et la page suivante reviendrait vide. `-1` est hors de l'intervalle 0–100, donc l'ordre reste stable et comparable.
- **Filtre sur `scoring_version`** : un score calculé par une version précédente n'est pas comparable à un score courant. La jointure l'exclut plutôt que de mélanger deux échelles sur le même écran.
- **Vérifié par** : `tests/unit/jobs/test_search_match.py` (11 tests), **et** contre PostgreSQL réel — la doublure en mémoire ne prouve rien d'une jointure SQL : ordre 90/60/30, non scorées à la fin, aucun score sans profil validé, version obsolète ignorée.

## D52 — Les index se posent sur ce qui a été mesuré, avec la nuance mesurée ✅ *(affinage efficience)*
- **Décision** : migration 0007 — index sur `ai_calls(created_at)`, sur les neuf clés étrangères du chemin de purge, et `match_results(profile_id, score DESC)` **non partiel**.
- **Justification** : trois coûts constatés contre un PostgreSQL peuplé, aucun visible sur le corpus de douze offres. (a) La rétention d'`ai_calls` filtre sur `created_at` seul, et le seul index existant est `(task, created_at)` — inutilisable, `task` étant en tête. (b) Vingt-quatre clés étrangères sans index : purger un compte coûtait 130 ms à 300 000 comptes, **linéairement au volume total**, pas au sien. (c) `idx_match_by_score` est partiel (`WHERE blocking_criteria = '[]'`) et ne couvre donc pas le cas par défaut du contrat, où les offres bloquées restent visibles.
- **La nuance, qui vaut plus que l'index** : le gain dépend de la distribution. Sur un arriéré massif — le premier passage — le planificateur balaie la clé primaire et l'index sur `created_at` ne sert à rien. C'est en **régime permanent**, peu de lignes éligibles parmi beaucoup de récentes, qu'il mord : mesuré sur 200 000 lignes dont 5 000 éligibles, `Index Scan` 1,7 ms / 18 blocs contre `Parallel Seq Scan` 20,2 ms / 1907 blocs. Douze fois plus rapide, cent fois moins d'E/S, chaque nuit, sur la table la plus volumineuse. Poser l'index sans le vérifier aurait produit une affirmation fausse dans les deux sens.
- **Rejouabilité, corrigée du piège de 0006** : un `CREATE INDEX CONCURRENTLY` interrompu laisse un index **INVALIDE** que `IF NOT EXISTS` prend pour fait — la migration se déclarait appliquée avec un index inutilisable, et `upgrade head` étant déjà à head ne repassait jamais. 0007 supprime explicitement tout index invalide de même nom avant de créer. Le contrôle est en Python, pas dans un `DO $$` : PostgreSQL refuse `DROP INDEX CONCURRENTLY` dans un bloc de fonction — première version écrite ainsi, elle échouait précisément sur le cas qu'elle traite.
- **Vérifié par** : montée, descente, remontée, puis rejeu après invalidation forcée d'un index (`indisvalid` passe de `false` à `true`).
