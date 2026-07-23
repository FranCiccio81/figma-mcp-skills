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

## Journal des mises à jour
- 2026-07-23 : création, D01–D15 actées pour le MVP (phases 1–10). Hypothèses 🟡 signalées : providers exacts, seuils de dédup, next-intl, liste initiale des connecteurs.
- 2026-07-23 (revue de phase 4–10) : ajout D16–D23 (issus de 10-system-architecture.md) ; résolution de l'ambiguïté `source_ref` de D13 (référence employeur, sinon vide — 07 §6.1 Q4 close) ; contrats API complétés (`GET /generations`, filtre `saved` sur `GET /jobs`) suite à la revue UX (03) ; questions ouvertes consolidées dans 17.
