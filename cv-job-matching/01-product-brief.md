# 01 — Product Brief : Boussole

> Assistant de candidature transparent — CV structuré, matching explicable, candidatures maîtrisées.
> Statut : v1.0 (MVP scoping) — 2026-07-23. Marché prioritaire : Europe (lancement France).

---

## 1. Reformulation du produit

**Boussole** est une application web qui aide un candidat à piloter sa recherche d'emploi de bout en bout, sans jamais candidater à sa place :

1. Le candidat **importe son CV** (PDF ou DOCX). Le système le transforme en **profil professionnel structuré**, éditable, dont chaque champ conserve sa provenance (extrait du CV, saisi par l'utilisateur, inféré et marqué incertain).
2. Il précise ses **préférences** (métiers cibles, localisation, télétravail, contrat, salaire, langues, secteurs).
3. Le système **agrège des offres d'emploi** uniquement depuis des sources légalement et techniquement exploitables (APIs publiques, flux ATS ouverts, partenaires, sources explicitement autorisées). Chaque offre conserve sa source et son lien d'origine. Aucune promesse de couvrir « tout le web ».
4. Pour chaque offre, un **moteur déterministe** calcule un **score de compatibilité (0–100)** et un **indice de confiance (0–100)** distincts, identifie les **critères bloquants** et les **informations inconnues**. Le LLM explique, il ne note pas.
5. Le candidat comprend **pourquoi** : points forts, lacunes, incertitudes, dimension par dimension.
6. Il peut générer un **e-mail de candidature** ou une **lettre de motivation** personnalisée, et **adapter son CV** à une offre — sans aucune invention : tout contenu généré est ancré dans le profil validé, et toute reformulation est soumise à validation humaine.
7. Il **suit ses candidatures** dans un tableau de bord (statuts, relances, historique).

Le MVP **n'envoie jamais de candidature automatiquement**. L'utilisateur relit et valide tout contenu avant usage.

## 2. Proposition de valeur

| Pour | Qui | Boussole apporte | Contrairement à |
|---|---|---|---|
| Les candidats européens (cadres, tech, fonctions support) | veulent comprendre pourquoi une offre leur correspond et candidater mieux, pas plus | un matching **explicable** (score + confiance + lacunes), un profil structuré fiable, des contenus de candidature **fidèles au CV réel** | les job boards (recherche par mots-clés, zéro explication) et les outils « IA magique » qui inventent des compétences et candidatent en masse |

**Différenciateurs :** transparence du score (méthode publiée dans le produit), indice de confiance assumé, zéro invention garantie par conception (ancrage + validation), privacy by design (RGPD, données en UE), pas de spam de candidatures.

## 3. Problèmes utilisateurs adressés

1. Trier des centaines d'offres redondantes et mal ciblées prend des heures par semaine.
2. Impossible de savoir si une offre « vaut le coup » sans lire l'intégralité de l'annonce.
3. Adapter CV et lettre à chaque offre est coûteux ; les outils IA existants inventent du contenu (risque réputationnel réel en entretien).
4. Le suivi des candidatures se fait dans des tableurs bricolés.
5. Les scores « magiques » des outils existants ne sont ni explicables ni contestables.

## 4. Périmètre MVP

### Inclus (features A→Q du cahier des charges)
- Compte + onboarding (A), import/parsing CV (B), édition profil (C), préférences (D)
- Agrégation d'offres depuis 2–3 connecteurs initiaux (E), normalisation + déduplication (F)
- Recherche + filtres (G), matching (H), indice de confiance (I), explication (J)
- Sauvegarde/masquage d'offres (K), génération e-mails (L) et lettres (M)
- Optimisation générale du CV (N), adaptation du CV à une offre (O)
- Suivi des candidatures — saisie manuelle des statuts (P)
- Export et suppression des données, suppression du compte (Q)

### Explicitement hors MVP (reporté)
- Envoi automatique de candidatures ; auto-remplissage de formulaires ATS
- Applications mobiles natives ; extension navigateur
- Multi-CV par utilisateur (un profil canonique + variantes par offre seulement)
- Alertes push/e-mail temps réel (digest e-mail simple possible en fin de MVP)
- Marché biface (comptes recruteurs) ; parrainage ; coaching entretien
- Langues d'interface autres que FR/EN (architecture i18n prête dès le MVP)
- Apprentissage automatique des poids de matching (poids fixes versionnés au MVP)

## 5. Les dix décisions structurantes

Chaque décision suit le format : décision / justification / alternatives / compromis / réévaluation. Détail complet dans `decisions.md`.

1. **D01 — Monolithe modulaire** : FastAPI unique + workers async (Celery/Redis), découpé en modules internes aux frontières nettes. *Réévaluer* quand l'ingestion dépassera ~50k offres/jour ou qu'une équipe > 8 devs travaillera en parallèle.
2. **D02 — Score 100 % déterministe** : calcul en Python pur, configuration des poids dans `scoring-config.json` versionné ; le LLM n'intervient jamais dans le calcul. *Réévaluer* après constitution du jeu annoté (≥ 500 paires) pour calibrer les poids.
3. **D03 — Score et confiance séparés** : compatibilité (qualité du match sur données connues) ≠ confiance (couverture et fiabilité des données). Jamais fusionnés en un seul chiffre.
4. **D04 — Ingestion par connecteurs explicites** : un connecteur par source (API France Travail, flux ATS publics type Greenhouse/Lever job boards API, partenaires) avec contrat, licence documentée et robots/ToS vérifiés. Pas de crawler générique. *Réévaluer* à chaque nouvelle source.
5. **D05 — Profil canonique versionné avec provenance** : chaque champ du profil porte `source` (cv_extraction | user_input | user_confirmed) et `confidence`. Les variantes de CV par offre référencent le canonique, jamais l'inverse.
6. **D06 — PostgreSQL + pgvector, pas de vector DB dédiée** : embeddings dans Postgres. *Réévaluer* au-delà de ~5M d'offres actives ou si p95 recherche > 500 ms.
7. **D07 — Recherche hybride sans Elasticsearch** : filtres SQL + full-text `tsvector` + re-ranking embeddings. *Réévaluer* si besoins de facettes complexes ou multi-langue avancé.
8. **D08 — Couche IA multi-provider à sorties contraintes** : abstraction provider (Claude par défaut), toute sortie LLM est du JSON validé par Pydantic contre `ai-output-schemas.json`, avec retry/répare et fallback. Prompts versionnés en base.
9. **D09 — Privacy by design UE** : hébergement et traitement en UE, chiffrement au repos et en transit, suppression effective ≤ 30 jours, minimisation (le LLM ne reçoit que le nécessaire), DPIA avant lancement. Positionnement AI Act instruit dès le MVP (voir risques).
10. **D10 — Human-in-the-loop obligatoire** : aucune candidature envoyée par le système ; tout contenu généré (e-mail, lettre, CV adapté) passe par un écran de relecture avec diff avant export. Non négociable au MVP.

## 6. Hypothèses principales à tester

| ID | Hypothèse | Test | Seuil de validation |
|---|---|---|---|
| H1 | Les candidats font davantage confiance à un score expliqué qu'à un score opaque | Interviews + A/B sur l'ouverture du panneau d'explication | ≥ 40 % des vues d'offre ouvrent l'explication |
| H2 | Le parsing CV atteint une qualité suffisante pour ne pas décourager (édition < 5 min) | Mesure du taux de champs corrigés post-import | ≤ 20 % de champs corrigés ; ≥ 70 % des profils validés en < 10 min |
| H3 | 2–3 sources d'offres suffisent pour une densité crédible sur 1–2 verticales (ex. tech France) | Comptage d'offres pertinentes par profil pilote | ≥ 30 offres à score ≥ 60 par profil actif |
| H4 | Les contenus générés « sans invention » restent perçus comme utiles | Taux d'export/copie des lettres générées | ≥ 50 % des générations exportées |
| H5 | Les utilisateurs acceptent la saisie manuelle du statut de candidature | Part des candidatures avec ≥ 1 mise à jour de statut | ≥ 40 % |
| H6 | Poids initiaux du matching raisonnables | Corrélation avec jugements humains (jeu annoté) | Spearman ≥ 0,6 au MVP |

## 7. Risques critiques

| ID | Risque | Impact | Mitigation MVP |
|---|---|---|---|
| R1 | **Légal — sources d'offres** : une source utilisée sans droit clair (ToS, licence) | Blocage produit, exposition juridique | D04 : connecteurs approuvés un par un, registre des licences par source, revue juridique avant activation ; aucune promesse d'exhaustivité |
| R2 | **AI Act / RGPD** : le matching emploi peut relever des systèmes à haut risque (annexe III AI Act) selon le rôle du système | Obligations lourdes, retrait du marché | Le produit sert le candidat (pas de décision de recrutement) ; analyse juridique formelle avant lancement — inscrit dans `17-open-questions.md` ; transparence et supervision humaine déjà par conception ; DPIA |
| R3 | **Qualité du parsing CV** : profils faux → matching faux → confiance détruite | Churn immédiat | Provenance + confiance par champ, écran de validation obligatoire, jeu de CV de référence (Phase 8), seuils qualité bloquants en CI |
| R4 | **Hallucinations dans les contenus** : une seule compétence inventée détruit la promesse | Réputationnel majeur | Génération ancrée (le prompt ne reçoit que le profil validé), vérification post-génération par extraction de claims et contrôle d'ancrage, diff obligatoire, tests de prompts en CI |
| R5 | **Prompt injection** via CV ou offres importés | Fuite de données, contenus manipulés | Documents traités comme données non fiables : délimiteurs stricts, sorties JSON schématisées, aucune instruction exécutable issue du contenu, tests adversariaux |
| R6 | **Densité d'offres insuffisante** au lancement | Produit perçu comme vide | Lancement vertical (tech France), H3 mesurée en alpha fermée, connecteur France Travail (API publique) en priorité |
| R7 | **Coûts LLM non maîtrisés** | Marges négatives | Le scoring de masse est déterministe (zéro LLM) ; LLM uniquement à l'import, à l'explication à la demande et à la génération ; cache des extractions d'offres |
| R8 | **Biais du matching** | Discrimination indirecte, risque légal | Attributs sensibles jamais extraits ni utilisés (liste d'exclusion au parsing), audit du jeu annoté, tests de non-régression biais |

## 8. Métriques de succès du MVP

- **Activation** : ≥ 60 % des inscrits importent un CV et valident leur profil.
- **Cœur de valeur** : ≥ 40 % des utilisateurs actifs hebdo consultent ≥ 1 explication de score (H1).
- **Qualité matching** : Spearman ≥ 0,6 vs jeu annoté ; 0 offre à critère bloquant présentée au-dessus de 60 sans avertissement.
- **Génération** : ≥ 50 % des contenus générés exportés ; 0 invention détectée sur le jeu de test de prompts en CI.
- **Rétention** : ≥ 25 % d'actifs semaine 4.
- **Conformité** : suppression de compte effective ≤ 30 jours vérifiée par test automatisé ; 100 % des offres affichées avec source + lien d'origine.

## 9. Contraintes assumées

- Aucune promesse d'exhaustivité des offres ; le produit affiche le nombre et la nature de ses sources.
- Données incertaines toujours affichées comme telles (badge « incertain » / « inconnu »), jamais présentées comme des faits.
- Calculs métier (score, confiance, déduplication) reproductibles sans LLM.
- Architecture simple (monolithe modulaire) mais frontières de modules prêtes pour extraction ultérieure.
