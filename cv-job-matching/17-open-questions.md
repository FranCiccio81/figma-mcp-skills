# 17 — Questions ouvertes

> Ambiguïtés assumées, non tranchées. Chaque entrée : question, hypothèse MVP retenue en attendant (🟡), décideur, échéance. Les hypothèses 🟡 sont aussi marquées dans les documents concernés.

## Juridique et conformité

| ID | Question | Hypothèse MVP 🟡 | Décideur | Échéance |
|---|---|---|---|---|
| Q1 | **AI Act** : Boussole (outil au service du candidat, sans décision de recrutement) relève-t-il des systèmes à haut risque de l'annexe III (emploi) ? | Conception conforme aux obligations haut-risque par précaution (transparence, supervision humaine, logs, robustesse), sans auto-classification | Conseil juridique + CPO | Avant lancement public |
| Q2 | Conditions exactes d'utilisation de l'**API France Travail** (quota, mention obligatoire, restrictions de réutilisation) | Connecteur développé derrière un feature flag, activation après signature/validation | Juridique + Data Eng | Avant M2 (ingestion) |
| Q3 | L'agrégation des flux publics **Greenhouse/Lever** par entreprise nécessite-t-elle un accord par employeur ? | Activation entreprise par entreprise après vérification des ToS de chaque board | Juridique | Avant M2 |
| Q4 | Localisation UE garantie des **providers LLM** retenus (traitement et non-entraînement contractuels) | Anthropic via endpoint UE si disponible, sinon DPA + clauses ; à confirmer | Security/Privacy Eng | Avant M1 (parsing CV) |
| Q5 | Faut-il un **DPO** désigné dès le MVP ? | DPO externe mutualisé | CPO | Avant lancement |

## Produit

| ID | Question | Hypothèse MVP 🟡 | Décideur | Échéance |
|---|---|---|---|---|
| Q6 | Verticale de lancement exacte (tech France seulement ? + fonctions support ?) | Tech France (dev, data, produit) | CPO | Avant alpha |
| Q7 | Le score doit-il être affiché sur les cartes de la liste ou seulement en détail ? (risque d'ancrage excessif) | Affiché sur les cartes avec confiance accolée | Design + CPO (test H1) | Alpha |
| Q8 | Multi-CV / multi-profils par utilisateur | Un profil canonique + variantes par offre (D05) | CPO | Post-MVP |
| Q9 | Digest e-mail de nouvelles offres en fin de MVP ? | Hors MVP, réévalué à M4 | CPO | M4 |
| Q10 | Modèle économique (freemium ? quota gratuit ?) — impacte les quotas LLM | Quotas MVP : 10 générations/h, 40/j, gratuits en alpha | CPO | Avant beta |

## Technique

| ID | Question | Hypothèse MVP 🟡 | Décideur | Échéance |
|---|---|---|---|---|
| Q11 | Modèle d'embeddings (multilingue FR/EN, dimension, hébergement UE) | Dimension 1024, modèle multilingue managé ; à évaluer sur le jeu annoté | ML Eng | Avant M2 |
| Q12 | Seuil de dédup étage 2 (cosinus 0,92) et seuil « compétence proche » (0,75) | Valeurs initiales, calibrées sur données réelles en alpha | ML Eng + Data Eng | Alpha |
| Q13 | Taxonomie compétences : ESCO complet, sous-ensemble, ou taxonomie maison amorcée d'ESCO ? | Sous-ensemble ESCO (tech) + alias maison | ML Eng | Avant M3 |
| Q14 | Service de géocodage (Nominatim self-hosted vs API commerciale, conformité) | Nominatim self-hosted avec cache | DevOps | Avant M2 |
| Q15 | Fournisseur d'e-mail transactionnel UE | À sélectionner (liste courte : Brevo, Mailjet) | DevOps | Avant M1 |
| Q16 | Antivirus upload (ClamAV self-hosted suffisant ?) | ClamAV en sidecar | Security Eng | Avant M1 |
| Q17 | Taux de change pour la normalisation des salaires multi-devises | Figés par release (EUR pivot) ; UE ≈ EUR majoritaire au lancement | Backend Eng | M3 |
| Q18 | next-intl vs alternative pour l'i18n front | next-intl | Frontend Eng | M1 |

## Données et évaluation

| ID | Question | Hypothèse MVP 🟡 | Décideur | Échéance |
|---|---|---|---|---|
| Q19 | Sourcing des 500 paires annotées : profils volontaires (consentement) + profils synthétiques — proportion ? | 60 % synthétiques / 40 % volontaires anonymisés | ML Eng + Privacy | M3 |
| Q20 | Rémunération/outillage des annotateurs, plateforme d'annotation | Outil interne léger (grille dans l'admin) | QA Lead | M3 |
| Q21 | Conservation des échantillons de prompts pour debug (30 j, consentement) : opt-in ou opt-out ? | Opt-in explicite (consent `ai_debug_sampling`) | Privacy Eng | M1 |

## Ajouts issus des revues de phase (consolidation 2026-07-23)

*(sources : sections « Questions ouvertes » des docs 02–10 et 13–16 ; les doublons avec Q1–Q21 ont été fusionnés)*

### Produit / UX

| ID | Question | Hypothèse MVP 🟡 | Décideur | Échéance |
|---|---|---|---|---|
| Q22 | OCR des PDF scannés (image only) au MVP ? | Hors MVP : erreur `image_only_pdf` + saisie manuelle guidée | CPO | Avant M1 |
| Q23 | Éditer un profil validé le fait-il repasser en `draft` (re-validation requise) ? | Non : l'édition incrémente `version`, les champs édités passent `user_input`, le statut reste `validated` | CPO + Backend | M1 |
| Q24 | Réimport d'un nouveau CV : fusion avec le profil existant ou remplacement ? | Écran de fusion champ à champ, l'existant validé prime | Design + CPO | M1 |
| Q25 | `anchoring_check=failed` : comportement UI et contrôle sur texte édité manuellement ? | Génération non exportable tant que failed ; l'édition manuelle lève le contrôle (responsabilité utilisateur, bandeau d'information) | CPO + ML Eng | M4 |
| Q26 | Offre expirée : quelles actions restent autorisées (génération, candidature, accès direct) ? | Lecture + suivi autorisés ; génération refusée (`job_expired`) | CPO | M3 |
| Q27 | Génération autorisée sur une offre à critère bloquant ? | Autorisée avec avertissement (contrôle utilisateur > paternalisme) | CPO | M4 |
| Q28 | Une génération `failed` consomme-t-elle le quota ? | Non | Backend | M4 |
| Q29 | Matrice exacte des transitions de statut de candidature + unicité (1 candidature par offre ?) | Transitions libres historisées ; unicité (user, job) non forcée | CPO | M4 |
| Q30 | Fenêtre de rétractation sur la suppression de compte + e-mail de confirmation ? | E-mail de confirmation avec lien d'annulation 7 j (dans la fenêtre des 30 j) | Privacy + CPO | M5 |
| Q31 | Anti-énumération à l'inscription : 409 explicite ou réponse neutre ? | Réponse neutre (e-mail envoyé dans les deux cas) | Security | M1 |
| Q32 | Filtre `salary_min` : exclure ou inclure les offres sans salaire ? | Inclure avec badge « non communiqué » (cohérent : l'inconnu n'est pas un fait négatif) | CPO | M2 |
| Q33 | Changement d'e-mail absent des contrats API | Ajout post-MVP (workflow à double confirmation) | Backend | Beta |
| Q34 | Qualité mobile web minimale au lancement (persona jeune diplômé mobile-first) | Responsive complet, optimisé desktop d'abord | Design | Alpha |
| Q35 | UX des scores bas structurels pour jeunes diplômés (risque de découragement) | Messages d'accompagnement + tri par confiance ; à tester en alpha | Design + CPO | Alpha |

### Technique / Sécurité / Conformité

| ID | Question | Hypothèse MVP 🟡 | Décideur | Échéance |
|---|---|---|---|---|
| Q36 | MFA au MVP ? | Non (mot de passe fort + rate limit) ; TOTP en beta | Security | Beta |
| Q37 | Lecture de l'art. 22 RGPD (décision individuelle automatisée) pour le score | Pas de décision à effet juridique (D10 : l'humain décide) — analyse à formaliser avec Q1 | Juridique | Avant lancement |
| Q38 | Suffisance SCC + TIA si le provider LLM traite hors UE (complète Q4) | Endpoint UE exigé ; sinon SCC+TIA documentés | Privacy | Avant M1 |
| Q39 | RPO 1 h / RTO 4 h validés produit ? (D19) | Oui par défaut | CPO + DevOps | Beta |
| Q40 | Deux instances Redis logiques réalisables chez l'hébergeur UE retenu ? (D17) | Oui (deux instances managées ou une instance + DB séparées en dégradé) | DevOps | M1 |
| Q41 | Pondération exacte du re-ranking hybride (full-text vs cosinus) | 50/50 normalisé 🟡, calibré en alpha | ML Eng | M2 |
| Q42 | Pattern outbox pour les événements internes : nécessaire au MVP ? | Non (appels en process + tâches Celery idempotentes) ; outbox si incohérences observées | Architect | M3 |
| Q43 | Latences cibles LLM à confirmer par benchmark (05) | Cibles de 08 conservées jusqu'au benchmark M1 | ML Eng | M1 |
| Q44 | ClamAV et schemathesis : en PR ou en nightly ? | Antivirus à l'upload en prod + scan PR léger ; schemathesis nightly | QA + DevOps | M1 |
| Q45 | Enrichissement secteur des offres ATS (SIRENE ?) — licence et coût | Secteur inconnu accepté au MVP (poids 4, `k=0`) | Data Eng | Post-MVP |
| Q46 | Un partenaire d'offres est-il signé avant gel du périmètre ? | Non : retirer `partner-*` du plan de charge M2 | CPO | Gel M2 |

### Données / Équipe / Coûts

| ID | Question | Hypothèse MVP 🟡 | Décideur | Échéance |
|---|---|---|---|---|
| Q47 | Recrutement et budget des 3 annotateurs (chemin critique M4, complète Q20) | Annotation interne équipe + 2 vacataires | CPO | M3 |
| Q48 | Budgets chiffrés LLM et infra (rendent opérants les signaux de risque R7/R11) | À chiffrer au gel du périmètre | CPO + DevOps | Gel M2 |
| Q49 | Analytics : consentement ou intérêt légitime (events server-side sans cookies tiers) ? | Intérêt légitime documenté + opt-out 🟡 — à valider DPO | DPO | Avant alpha |
| Q50 | Taille réelle de l'équipe (conditionne le calendrier S1–S16 de 15) | 4–5 ingés + 1 designer + 1 PM | CPO | Immédiat |

### Résolues en revue de phase (2026-07-23)

- ~~`GET /generations` manquant~~ → ajouté aux contrats (12, openapi.yaml).
- ~~Filtre « offres sauvegardées » manquant~~ → paramètre `saved_only` ajouté à `GET /jobs`.
- ~~Interprétation `source_ref` dans la clé de dédup D13 (07 Q4)~~ → tranché : référence **employeur** si exposée, sinon vide ; l'idempotence par source reste portée par `(source_id, external_ref)`. `decisions.md` mis à jour.

---

# Revue post-implémentation M1 → M6 (2026-07-28)

> Les six jalons ont tranché une partie de ces questions **dans le code**. Ci-dessous : ce qui est résolu (avec la réponse effective et l'endroit où elle vit), ce qui reste ouvert, et ce qui est apparu. Une question résolue est **barrée**, jamais supprimée. Rappel de probité : « implémenté conformément à l'hypothèse » n'est pas « validé produit » — les questions dont seul le décideur peut trancher restent ouvertes même si le code a fait un choix.

## A. Résolues par l'implémentation

| ID | Réponse effective | Où elle vit dans le code |
|---|---|---|
| ~~Q14~~ | **Nominatim auto-hébergé retenu**, avec cache Redis volatile (TTL 12 mois) et politesse 1 req/s ; `StaticGeocoder` (~30 villes) pour dev/tests, sans réseau. Le volet **attribution ODbL reste juridique** (voir Q3). | `api/app/modules/ingestion/geocode.py` |
| ~~Q18~~ | **next-intl** confirmé (^3.26). Pas de routage par locale au MVP ; la locale viendra de `GET /me` 🟡. Parité fr/en (569 clés) imposée par script. | `web/i18n.ts`, `web/package.json`, `web/scripts/check-i18n-parity.mjs` |
| ~~Q22~~ | **OCR hors MVP**, conformément à l'hypothèse : un PDF sans couche texte échoue en `image_only_pdf` **avant tout appel LLM**. | `api/app/workers/cv_tasks.py`, `api/app/modules/profiles/cv/schemas.py` |
| ~~Q23~~ | **Confirmé** : l'édition n'a pas d'effet sur le statut. Toute mutation incrémente `version` (`_bump_version`, RM-C-4) ; `status = "validated"` n'est posé que par `POST /profile/validate`. | `api/app/modules/profiles/service.py` |
| ~~Q24~~ | **Fusion champ à champ**, l'existant validé prime : `POST /cv-documents/{id}/apply` applique une sélection par item et **n'écrase jamais** une donnée `user_input`. | `api/app/modules/profiles/cv/service.py`, `tests/unit/cv/test_apply_api.py` |
| ~~Q26~~ | **Confirmé** : offre expirée lisible (retenue 12 mois, `status` exposé pour le bandeau) ; génération refusée par 409 `job_expired`. | `api/app/modules/jobs/service.py`, `api/app/modules/generation/service.py` |
| ~~Q29~~ | **Confirmé** : transitions **libres et historisées** (`application_events`), unicité `(user, job)` **non** forcée ; offres externes supportées. | `api/app/modules/applications/`, `tests/unit/applications/test_applications_api.py` |
| ~~Q31~~ | **Réponse neutre** confirmée à l'inscription (aucune information ne fuit vers le client). ⚠️ L'e-mail « un compte existe déjà » n'est encore que **journalisé** — dépend de Q15. | `api/app/modules/auth/service.py` |
| ~~Q32~~ | **Confirmé** : `salary_min` **inclut** les offres sans salaire ; l'annualisation multi-périodes est faite en SQL. | `api/app/modules/jobs/repository.py`, `tests/integration/test_jobs_salary_filter.py` |
| ~~Q40~~ | **Deux Redis logiques livrés** au niveau applicatif : `REDIS_PERSISTENT_URL` (sessions + broker) et `REDIS_CACHE_URL` (cache + rate limiting), distincts jusque dans les fabriques posées sur `app.state`. ⚠️ La **faisabilité chez l'hébergeur UE** reste une question DevOps, non tranchable par le code. | `api/app/core/config.py`, `api/app/main.py` |
| ~~Q42~~ | **Pas d'outbox au MVP**, conformément à l'hypothèse : appels en process + tâches Celery idempotentes (clés naturelles, `(source_id, external_ref)`, clés d'idempotence sur générations et exports). Aucune incohérence observée n'a justifié de revenir dessus. | `api/app/workers/`, `api/app/modules/ingestion/service.py` |

**Résolues par correction de revue** (la question ne se posait pas — la garantie était annoncée mais ne tenait pas ; le point est désormais verrouillé) :

- ~~Le garde-fou de stockage des workers Celery protège-t-il vraiment ?~~ → **Non**, il était un no-op (`Signal.send` avale les exceptions, `worker_ready` se déclenche trop tard). Déplacé au niveau module (D24), verrouillé par `tests/unit/core/test_startup_guards.py`.
- ~~La purge RGPD est-elle exhaustive ?~~ → **Non**, le module `jobs` était resté un stub M1 : `saved_jobs` conservés indéfiniment et requêtes jamais marquées purgées. Verrouillé par `tests/unit/privacy/test_registry.py` (le test résout et **appelle** chaque purger) et `tests/integration/test_privacy_purge.py` (inventaire depuis `information_schema`, parcours **transitif** des clés étrangères).
- ~~La recherche full-text fonctionne-t-elle sur du français accentué ?~~ → **Non** : le déclencheur `tsv` désaccentuait le texte indexé mais pas la requête — « développeur », le cas nominal, ne renvoyait rien. Verrouillé par `tests/integration/test_jobs_fulltext_trigger.py`.
- ~~Le journal `ai_calls` reçoit-il réellement les appels des workers ?~~ → **Non** : les écritures étaient planifiées sur une boucle fermée avant exécution (journal vide pour `extract_cv`, `extract_job` et toutes les `generate_*`), et le nom de tâche des explications violait l'enum SQL (100 % du journal des explications perdu). Verrouillé par `tests/unit/ai/test_calls_journal.py`.

## B. Toujours ouvertes

**Inchangées, hors périmètre du code** (juridique, produit, budget, équipe) — aucune n'a été tranchée par l'implémentation :
`Q1` (AI Act), `Q2` (ToS France Travail), `Q3` (accord par employeur Greenhouse/Lever, + attribution ODbL héritée de Q14), `Q4` (localisation UE du provider LLM), `Q5` (DPO), `Q6` (verticale de lancement), `Q8` (multi-profils), `Q9` (digest e-mail), `Q10` (modèle économique), `Q19`/`Q20`/`Q47` (jeu annoté, annotateurs), `Q34` (mobile), `Q35` (UX des scores bas), `Q37` (art. 22 RGPD), `Q38` (SCC/TIA), `Q39` (RPO/RTO), `Q45` (secteur SIRENE), `Q46` (partenaire d'offres), `Q48` (budgets), `Q49` (base légale analytics), `Q50` (taille d'équipe).

> Note sur Q4/Q38 : le code **n'active aucun provider LLM réel par défaut** (`AI_PROVIDER=fake`) et refuse d'instancier un provider réel sans clé. L'activation reste explicitement conditionnée à la résolution de ces questions — la contrainte juridique est donc tenue par construction, pas par discipline.

**Ouvertes avec un état d'avancement à noter** :

| ID | Ce que le code a fait | Ce qui reste à trancher |
|---|---|---|
| Q7 | Score + confiance **affichés sur les cartes**, conformément à l'hypothèse (`web/components/match/match-badge.tsx`, `job-card.tsx`). | Le test d'ancrage en alpha (H1) n'a pas eu lieu. Décision design **non validée**. |
| Q11 | **Bloquante — voir N1.** Un provider local déterministe permet de livrer et tester (D27), mais `ManagedEmbeddingProvider` **lève** : aucun modèle sémantique n'est choisi. | Modèle multilingue FR/EN, dimension, hébergement UE. |
| Q12 | **Aggravée — voir N2.** Le seuil 0,92 s'est révélé destructeur sur vecteurs lexicaux ; l'étage 2 est neutralisé (D28). | Calibration sur données réelles, **après** Q11. |
| Q13 | Sous-ensemble ESCO amorcé : ~20 compétences tech + alias en seeds, résolution par `taxonomy.py`, colonne `esco_id` prévue au schéma. | Périmètre cible de la taxonomie et politique d'alimentation. |
| Q15 | **Rien n'est envoyé.** Trois e-mails contractuels sont **journalisés en TODO explicite** : « compte existant » à l'inscription (`auth/service.py`), confirmation de suppression (`privacy/service.py`), et par conséquent le lien d'annulation de Q30. | Fournisseur UE à sélectionner — **bloquant pour Q30 et pour la boucle d'inscription**. |
| Q16 | **Non implémenté** : `profiles/cv/router.py` documente le scan ClamAV comme « hors périmètre M4 ». Les gardes livrées sont les octets magiques, le plafond 10 Mo et l'anti-bombe de décompression (D33). | Antivirus à l'upload avant mise en service publique. |
| Q17 | Annualisation multi-périodes implémentée en SQL ; une devise non supportée est traitée comme **dimension inconnue** (`unconvertible_value`), jamais comme un fait négatif. | Table de taux figés par release — la **conversion inter-devises n'existe pas**. |
| Q21 | Sans objet pour `ai_calls` : le journal est **structurellement** fermé au contenu (D26), donc aucun prompt n'y est conservé. | Le consentement `ai_debug_sampling` et le dispositif d'échantillonnage de debug **n'existent pas** — à trancher s'ils sont voulus. |
| Q25 | Verdict d'ancrage bloquant l'export **implémenté et durci** : une PATCH sans changement réel ne lève plus l'ancrage et le verdict d'origine est **préservé pour l'audit** (D33). | Le principe « l'édition manuelle lève le contrôle » reste un arbitrage produit à confirmer. |
| Q27 | **Aucun contrôle de critère bloquant** n'existe côté serveur dans le service de génération : la génération est donc autorisée, conformément à l'hypothèse. | L'**avertissement** exigé par l'hypothèse n'est vérifié par aucun test — garantie non tenue côté back. |
| Q28 | ⚠️ **Le code contredit l'hypothèse — voir N7.** | — |
| Q30 | Soft delete immédiat + purge à 30 jours **implémentés et testés**. | La **fenêtre de rétractation de 7 jours et l'e-mail de confirmation n'existent pas** (TODO explicite, dépend de Q15). |
| Q33 | Non implémenté, conformément au plan (post-MVP). | Workflow à double confirmation. |
| Q36 | Non implémenté : mot de passe fort (argon2) + rate limiting, conformément à l'hypothèse MVP. | TOTP en beta. |
| Q41 | Pondération **50/50 renormalisée, configurable** (`SEARCH_RERANK_FULLTEXT_WEIGHT` / `_VECTOR_WEIGHT`), rerank désactivable. | Calibration — impossible avant Q11 (les vecteurs actuels sont lexicaux). |
| Q43 | Timeouts par tâche et retries bornés implémentés dans le provider. | **Aucun benchmark de latence n'a été mené** : les cibles de 08 restent des hypothèses. |
| Q44 | CI livrée : ruff, mypy, tests unitaires, et tests d'intégration PostgreSQL en job conditionnel (D29). | **Ni ClamAV ni schemathesis ne sont dans la CI** — la question reste entière. |

## C. Nouvelles questions (apparues pendant l'implémentation)

| ID | Question | Hypothèse / état 🟡 | Décideur | Échéance |
|---|---|---|---|---|
| **N1** | **Choix du modèle d'embeddings — désormais bloquant.** Q11 n'est plus une question de réglage : `ManagedEmbeddingProvider` lève, le provider par défaut est **lexical**, et quatre fonctions produit en dépendent (similarité d'intitulé = 15 % du poids, crédit « compétence proche », dédup étage 2, rerank hybride). Elles fonctionnent, mais sur de la similarité de forme, pas de sens. | Provider `hashing` en attendant (D27). Aucune date de levée. | ML Eng + CPO | **Avant alpha** |
| **N2** | **Calibration du seuil de dédup sur données réelles.** Le 0,92 de D13 a été mesuré destructeur sur vecteurs lexicaux (0,949 entre une offre et sa variante « Senior » ; 1,0000 entre une offre parisienne et une lyonnaise). L'étage 2 est neutralisé (D28). Quelle procédure de calibration, sur quel corpus, avec quel critère d'acceptation avant réactivation ? | Étage 2 désactivé tant que le provider n'est pas sémantique. Ordre imposé : Q11 → calibration → réactivation. | ML Eng + Data Eng | Après N1 |
| **N3** | **Backfill forcé après changement de tokenisation.** La correction M6 (symboles conservés : `C`, `C++`, `C#`, `.NET` distincts) invalide **tout vecteur déjà stocké**. Quelle procédure de déploiement — backfill avant ouverture du trafic, ou dégradation acceptée le temps du rattrapage ? | Tâches `ai.embeddings.backfill_*` disponibles ; aucune procédure de bascule écrite. | DevOps + ML Eng | **Avant tout déploiement** |
| ~~**N4**~~ | ~~**Rétention 13 mois d'`ai_calls` non implémentée.**~~ ✅ **Résolue** (lot post-M6 n° 1) : `maintenance.purge_ai_calls`, suppression par lots bornés, borne calculée en mois calendaires. Reste à surveiller le premier passage, qui journalisera `ai_calls_retention_truncated` tant que le retard n'est pas rattrapé. | — | — | — |
| **N5** | **Un compte OAuth serait aujourd'hui impossible à supprimer par son titulaire.** `delete_account` exige une vérification de mot de passe ; un compte sans mot de passe local n'a d'autre voie que le support. Écart art. 17 RGPD. La branche est **morte** tant qu'aucun compte OAuth n'existe. | Le TODO est explicite dans le code et l'écart assumé **à condition** que la correction (réauthentification par le fournisseur d'identité ou e-mail signé) soit livrée **en même temps** qu'OAuth. | Privacy Eng + Backend | **Simultanément à OAuth** |
| **N6** | **`S3ObjectStorage` n'a jamais tourné contre un vrai S3.** Il est testé sur `moto` et sur un contrat partagé avec le backend local ; le compose de dev utilise MinIO. Le chiffrement SSE-KMS avec clé UE, la politique IAM et le comportement des codes d'erreur réels ne sont pas vérifiés en conditions de production. | Backend sélectionné et refus de démarrage acquis (D24) ; reste à valider sur l'hébergeur retenu. | DevOps + Security | Avant mise en service |
| **N7** | **Une génération `failed` consomme le quota — le code contredit Q28.** Les quotas (10/h, 40/j) sont prélevés au `POST /generations`, avant l'exécution de la tâche ; aucun remboursement n'existe en cas d'échec. Seul le **rejeu par clé d'idempotence** ne re-consomme rien. | Écart **non corrigeable par la documentation**. Soit Q28 est révisée (« oui, l'échec consomme »), soit un remboursement doit être implémenté. | CPO + Backend | Gel du périmètre |
| **N8** | **L'export RGPD ne contient pas les fichiers CV d'origine.** L'archive n'agrège que les données structurées ; les PDF/DOCX déposés restent dans le stockage objet. L'art. 20 vise les données fournies par la personne — les fichiers déposés en font partie. | Écart **explicite** dans le code (TODO M5+). Passage à une archive ZIP à arbitrer. | DPO + CPO | Avant lancement |
| **N9** | **Le module `ingestion` est absent du registre de purge** (`DATA_MODULE_NAMES`), alors qu'il expose un `purge.py` dont les deux fonctions **lèvent `NotImplementedError`**. Défendable (les offres ne sont pas des données personnelles), mais l'exclusion est **silencieuse** : le test d'exhaustivité ne peut pas la contrôler. | 🟡 Hypothèse : exclusion volontaire et correcte. À rendre **explicite** (liste d'exclusion motivée) ou à corriger. | Privacy Eng | M7 |
| **N10** | **Route morte `GET /sources`.** Elle est déclarée deux fois : stub 501 du routeur `ingestion` et implémentation réelle du routeur `jobs`. `jobs` étant enregistré en premier, FastAPI résout toujours vers l'implémentation réelle et le stub est **inatteignable**. Sans conséquence fonctionnelle aujourd'hui, mais c'est une ambiguïté de contrat qui piégera la prochaine évolution. | 🟡 Retirer le stub du routeur `ingestion`. | Backend | M7 |
| **N11** | **Le re-scoring asynchrone après changement de préférences n'existe pas.** Quatre TODO(M4) concordants (`matching/service.py`, `preferences/service.py`, `preferences/router.py`) : le recalcul est **paresseux, au prochain accès**. La spec D-Préférences annonce un « re-scoring déclenché » et la matrice de traçabilité le listait en test attendu. | 🟡 Le recalcul paresseux est peut-être suffisant au MVP — à acter explicitement plutôt qu'à laisser en TODO. | Architect + CPO | M7 |
| **N12** | **Le cache d'extraction d'offres et le court-circuit par hash de payload sont reportés.** Sans eux, chaque cycle d'ingestion re-normalise tout et peut re-payer une extraction LLM déjà faite (coût, risque R7). | 🟡 Reporté explicitement « avant de brancher un provider réel » (`ingestion/service.py`). | Data Eng | Avant activation d'un provider réel |
| ~~**N13**~~ | ~~**Un poste HYBRIDE n'est pas rédhibitoire pour un candidat exigeant le full remote.**~~ ✅ **Tranchée** (lot post-M6 n° 3) dans le sens (a) : « requis » désigne une **contrainte**, le vocabulaire distinguant déjà « préféré » pour le négociable. Un poste hybride impose une présence certains jours ; pour qui ne peut pas venir, il est aussi impossible à tenir qu'un poste sur site. `remote.blocking_policies` est désormais **dans la configuration** (`{"required": ["onsite", "hybrid"]}`), plus en dur dans le moteur. Le sous-score hybride reste à **0,4** et l'offre reste visible : un bloquant avertit, il n'annule ni le score ni l'offre (06 §1). Spec 06 mise à jour. | — | — | — |
| ~~**N14**~~ | ~~**`title_similarity` est inerte ET compte comme un fait connu.**~~ ✅ **Résolue** (lot post-M6 n° 2). Le moteur rapproche désormais le modèle qui a produit le vecteur du `calibrated_for_model` déclaré par la dimension, et rend la dimension **inconnue** en cas de discordance — jamais un sous-score que rien ne fonde. La config livrée porte `calibrated_for_model: null`, constat honnête : ces seuils n'ont été mesurés contre aucun modèle. **Effet mesuré sur les 36 paires** : confiance moyenne 97,2 → **82,2** (max 98 → 83) — les 15 points étaient revendiqués à tort ; score moyen 49,1 → 58,2 ; aucune paire ne bascule en `low_data`. Le garde-fou protège aussi le sens inverse, qui viendra : brancher un provider sémantique (Q11) **sans recalibrer** produirait des sous-scores plausibles et faux, bien plus difficiles à repérer qu'un zéro constant. `scoring_version` 1.0.0 → 1.1.0 (invalide le cache `match_results`). Nouveau code de contrat `unavailable` : la raison ne met en cause ni le profil ni l'offre, parce que la limite est la nôtre. | — | — | — |
| ~~**N15**~~ | ~~**La couverture des compétences requises récompense les offres peu exigeantes.**~~ ✅ **Corrigée** (lot post-M6 n° 3, D38). Le facteur `k` du modèle, jusque-là binaire connu/inconnu, devient **continu** : une dimension calculée sur moins de `evidence_full_count` éléments pèse au prorata. Le sous-score n'est pas touché — la couverture est bien de 100 % — c'est le poids de l'information qui suit la quantité de preuve. **Mesuré** : Spearman du pire profil 0,526 → **0,714**, NDCG@10 0,907 → 0,956, bloquants inchangés à 1,00/1,00 ; **toutes les portes passent**. Vérifié non ad hoc : la porte passe pour le paramètre valant 2, 3, 4 ou 5. Limite documentée : sur une offre dont `skills_required` est la SEULE dimension connue, le facteur se simplifie à la renormalisation et n'a aucun effet — c'est mathématiquement inévitable et juste. | — | — | — |
| **N16** | **Le jeu d'évaluation n'est pas annoté par des humains.** `config/demo-corpus/evaluation-set.json` contient des **cas de référence construits** : ils font tourner l'instrument et prouvent qu'il mesure, mais ne disent pas si le matching est bon pour de vrais candidats. Trois profils, douze offres fictives. | 🟡 L'instrument (`app/evaluation`, `make evaluate`) est livré et testé ; il attend un vrai jeu. Protocole, annotateurs et budget = Q19/Q20/Q47, et des offres réelles = Q2/Q3. | CPO + ML Eng | Chemin critique le plus long |
