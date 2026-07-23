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

## Ajouts issus des revues de phase

*(complété au fil des phases — voir aussi les sections « Questions ouvertes » en fin de chaque document, consolidées ici à la revue finale)*
