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
