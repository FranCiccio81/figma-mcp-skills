# 06 — Spécification du moteur de matching

> Moteur 100 % déterministe (D02). Le LLM n'intervient jamais dans le calcul — uniquement dans l'extraction amont (avec confiance) et la reformulation aval des explications (D14).
> Configuration versionnée : `scoring-config.json` (`scoring_version` estampillé sur chaque résultat).

## 1. Sorties du moteur

Pour chaque paire (profil, offre), le moteur produit un objet `match_result` :

| Sortie | Type | Définition |
|---|---|---|
| `score` | int 0–100 | Compatibilité calculée **sur les dimensions connues uniquement** |
| `confidence` | int 0–100 | Couverture pondérée × fiabilité d'extraction des données utilisées |
| `blocking_criteria[]` | liste | Critères rédhibitoires détectés (l'offre reste visible, badgée) |
| `unknown_dimensions[]` | liste | Dimensions non évaluables (donnée absente d'un des deux côtés) |
| `dimension_scores[]` | liste | Par dimension : sous-score, poids, statut, valeurs comparées |
| `explanation_facts` | objet | Faits structurés pour l'explication (D14) — dérivés des lignes ci-dessus |
| `scoring_version` | string | Version de `scoring-config.json` utilisée |

**Formules** (poids `w_d`, sous-score `s_d ∈ [0,1]`, `k_d = 1` si dimension connue sinon 0, `q_d ∈ [0,1]` fiabilité d'extraction) :

```
score      = round( 100 × Σ(w_d·s_d·k_d) / Σ(w_d·k_d) )      # renormalisation sur le connu
confidence = round( 100 × Σ(w_d·k_d·q_d) / Σ(w_d) )
```

- Si `Σ(w_d·k_d) < 40` (moins de 40 % du poids total connu), le score est affiché mais marqué `low_data = true` ; l'UI le grise.
- `q_d = min(conf_extraction_candidat_d, conf_extraction_offre_d)` ; toute donnée d'extraction avec confiance < 0,5 est traitée comme **inconnue** (`k_d = 0`), jamais comme un fait.
- Un critère bloquant **ne met pas le score à zéro** : il est signalé séparément (transparence). Le tri par défaut relègue les offres bloquées ; un filtre permet de les masquer.

## 2. Dimensions

Poids initiaux (somme = 100) — à dire d'expert, à recalibrer sur le jeu annoté (§5). Statut 🟡 = hypothèse.

| # | Dimension | Poids | Donnée candidat | Donnée offre |
|---|---|---|---|---|
| 1 | Compétences indispensables | 25 | compétences du profil validé (normalisées taxonomie) | `skills_required[]` extraites (conf. par item) |
| 2 | Compétences complémentaires | 10 | idem | `skills_nice_to_have[]` |
| 3 | Similarité du métier | 15 | intitulés cibles (préférences) + 2 derniers intitulés occupés | intitulé + résumé du poste (embedding) |
| 4 | Séniorité | 8 | niveau déclaré/inféré validé | niveau extrait (échelle ordinale) |
| 5 | Années d'expérience | 7 | total calculé depuis les expériences | fourchette min–max extraite |
| 6 | Secteur | 4 | secteurs préférés + secteurs des expériences | secteur de l'entreprise (taxo NACE simplifiée 🟡) |
| 7 | Localisation | 8 | lieux acceptés + rayon (km) | lieu(x) du poste géocodés |
| 8 | Télétravail | 6 | préférence (requis/préféré/indifférent/sur-site) | politique (full-remote/hybride/sur-site + jours) |
| 9 | Langues | 8 | langues + niveau CECRL | langues requises + niveau |
| 10 | Type de contrat | 4 | types acceptés (CDI, CDD, freelance, stage, alternance) | type extrait |
| 11 | Salaire | 3 | fourchette souhaitée + minimum strict optionnel | fourchette publiée (souvent absente) |
| 12 | Préférences fines | 2 | entreprises cibles, mots-clés à privilégier | nom entreprise, description |

### Spécification par dimension

Chaque dimension définit : **normalisation · calcul · donnée manquante · explication**.

**1. Compétences indispensables (w=25)**
- *Normalisation* : chaque compétence (deux côtés) est mappée vers la taxonomie interne (base ESCO 🟡 + table d'alias, ex. `React.js`→`react`) ; à défaut, forme canonique lowercase/trim.
- *Calcul* : pour chaque compétence requise `r` : crédit 1,0 si présente dans le profil (match exact taxonomie), 0,5 si compétence « proche » (cosinus embeddings de libellés ≥ `skill_related_threshold` = 0,75 🟡), 0 sinon. `s = Σ crédits / |required|`.
- *Manquant* : offre sans compétences extraites → `k=0`. Profil sans compétences → impossible (profil non validable sans ≥ 3 compétences).
- *Explication* : liste nominative des requises couvertes / proches / manquantes. Les manquantes alimentent « lacunes ».

**2. Compétences complémentaires (w=10)** — même méthode sur `skills_nice_to_have` ; `s = Σ crédits / |nice|` ; si l'offre n'en liste pas → `k=0` (fréquent, non pénalisant).

**3. Similarité du métier (w=15)**
- *Calcul* : `sim = max` des cosinus entre embeddings des intitulés cibles du candidat et l'embedding « intitulé + 1er paragraphe » de l'offre. Mapping affine par morceaux : sim ≤ 0,55 → 0 ; 0,55–0,80 → linéaire 0→1 ; ≥ 0,80 → 1. (Seuils 🟡, à calibrer.)
- *Manquant* : jamais manquant côté offre ; si aucune préférence d'intitulé, on utilise les 2 derniers intitulés occupés ; si profil sans expérience ni cible → `k=0`.
- *Explication* : « métier très proche de vos cibles (Développeur backend) » / « métier éloigné de vos cibles ».

**4. Séniorité (w=8)**
- *Normalisation* : échelle ordinale 0–6 : stagiaire(0), junior(1), confirmé(2), senior(3), lead(4), head/principal(5), direction(6). Extraction offre par règles (mots-clés multilingues) puis LLM en secours (avec confiance).
- *Calcul* : Δ = niveau_offre − niveau_candidat. Table : Δ=0→1,0 ; candidat sur-qualifié de 1 → 0,8 ; de 2 → 0,5 ; ≥3 → 0,3 ; sous-qualifié de 1 → 0,6 ; de 2 → 0,25 ; ≥3 → 0,0.
- *Manquant* : offre sans séniorité détectable → `k=0` (fréquent).
- *Explication* : « le poste vise un niveau senior, votre profil est confirmé (écart d'un niveau) ».

**5. Années d'expérience (w=7)**
- *Normalisation* : candidat = somme des durées d'expériences pro (chevauchements fusionnés), arrondi 0,5 an. Offre = fourchette `[min, max]` extraite ; « 5+ ans » → min=5, max=null.
- *Calcul* : dans la fourchette → 1,0. En dessous : `s = max(0, années/min − 0,2)` borné à 1 (ex. 3 ans pour min 5 → 0,4). Au-dessus de max : `s = max(0,7 ; 1 − 0,05×(années−max))`.
- *Manquant* : offre sans exigence → `k=0`.
- *Explication* : « l'offre demande 5 ans minimum, votre profil en totalise 3 » → lacune.

**6. Secteur (w=4)**
- *Calcul* : secteur offre ∈ secteurs préférés → 1,0 ; ∈ secteurs des expériences passées → 0,8 ; secteur adjacent (même parent taxo) → 0,6 ; sinon 0,3 (le secteur est rarement rédhibitoire). Secteur ∈ exclusions utilisateur → **critère bloquant** `sector_excluded`.
- *Manquant* : secteur entreprise inconnu → `k=0`.

**7. Localisation (w=8)**
- *Normalisation* : géocodage (lat/lon) des lieux candidat et offre ; rayon candidat par lieu (défaut 30 km 🟡).
- *Calcul* : si offre full-remote compatible zone (pays/UE selon mention) → 1,0. Sinon distance minimale d aux lieux acceptés : d ≤ rayon → 1,0 ; rayon < d ≤ 2×rayon → décroissance linéaire 1→0 ; d > 2×rayon → 0, et si l'offre est sur-site strict → **bloquant** `location_incompatible`.
- *Manquant* : offre sans lieu ni mention remote → `k=0` + inconnue mise en avant (donnée critique).
- *Explication* : distance affichée (« à 12 km de Lyon »).

**8. Télétravail (w=6)** — matrice préférence × politique :

| candidat \ offre | full-remote | hybride | sur-site | inconnu |
|---|---|---|---|---|
| requis | 1,0 | 0,4 | 0 + **bloquant** `remote_required` | k=0 |
| préféré | 1,0 | 0,8 | 0,3 | k=0 |
| indifférent | 1,0 | 1,0 | 1,0 | k=0 |
| sur-site préféré | 0,5 | 0,8 | 1,0 | k=0 |

**9. Langues (w=8)**
- *Normalisation* : CECRL A1–C2 + « natif » (=C2). Extraction offre : langues explicitement requises ; langue de rédaction de l'annonce = signal faible (jamais une exigence inférée présentée comme un fait).
- *Calcul* : pour chaque langue requise : niveau candidat ≥ requis → 1 ; un cran en dessous → 0,5 ; absente ou ≥ 2 crans en dessous → 0 et **bloquant** `language_missing`. `s = moyenne`.
- *Manquant* : aucune exigence extraite → `k=0` (l'UI affiche « exigences de langue non précisées »).

**10. Type de contrat (w=4)**
- *Calcul* : type offre ∈ types acceptés → 1,0 ; sinon 0 et **bloquant** `contract_excluded` si l'utilisateur a coché « strict », sinon s=0,2.
- *Manquant* : type non extrait → `k=0`.

**11. Salaire (w=3)**
- *Normalisation* : conversion en EUR annuel brut (taux mensuels figés par release 🟡) ; fourchettes ouvertes complétées par ±15 %.
- *Calcul* : recouvrement des fourchettes `s = overlap / largeur_fourchette_candidat` borné [0,1]. Si `max_offre < minimum_strict_candidat` → **bloquant** `salary_below_minimum`.
- *Manquant* : salaire non publié (cas majoritaire) → `k=0` + affiché « salaire non communiqué ».

**12. Préférences fines (w=2)** — entreprise ∈ cibles → 1,0 ; ≥ 1 mot-clé privilégié présent → 0,7 ; sinon 0. Manquant : pas de préférences fines → `k=0`.

## 3. Critères bloquants — récapitulatif

| Code | Condition | Donnée requise des deux côtés |
|---|---|---|
| `location_incompatible` | sur-site strict et d > 2×rayon | oui |
| `remote_required` | candidat exige full-remote, offre sur-site | oui |
| `language_missing` | langue requise absente ou ≥ 2 crans sous le niveau | oui |
| `contract_excluded` | type refusé en mode strict | oui |
| `salary_below_minimum` | max offre < minimum strict déclaré | oui |
| `sector_excluded` | secteur exclu par l'utilisateur | oui |

Règles : un bloquant n'est **jamais** inféré depuis une donnée à confiance < 0,7 ; en dessous, il est rétrogradé en « avertissement possible » avec mention de l'incertitude. Aucun attribut sensible (âge, genre, origine, santé, religion, orientation, situation familiale) n'est extrait, stocké ni utilisé — liste d'exclusion appliquée au parsing (cf. 08 et 09).

## 4. Pipeline d'exécution

1. **Déclencheurs** : (a) profil/préférences modifiés → re-scoring asynchrone des offres actives filtrées (pré-filtre SQL : pays + contrat) ; (b) nouvelle offre normalisée → scoring contre les profils dont le pré-filtre matche ; (c) consultation d'une offre non scorée → calcul synchrone (< 50 ms cible, aucun appel réseau).
2. Le moteur lit uniquement des données **déjà structurées** (aucun appel LLM dans la boucle).
3. Résultats persistés dans `match_results` (upsert par (profil, offre, scoring_version)).
4. Invalidation : changement de `scoring_version` → re-scoring paresseux (au premier accès) + batch nocturne.

## 5. Stratégie d'évaluation (jeu annoté humain)

- **Constitution** : 500 paires (profil, offre) au MVP — 20 profils synthétiques + volontaires anonymisés × 25 offres réelles, stratifiées par verticale (tech, support, vente) et par présence/absence de données (salaire, séniorité).
- **Annotation** : 3 annotateurs par paire ; grille : pertinence 0–4 (guide d'annotation versionné) + repérage des bloquants. Accord inter-annotateurs cible : Krippendorff α ≥ 0,65 ; désaccords arbitrés.
- **Métriques** : Spearman(score, médiane annotateurs) ≥ 0,6 ; NDCG@10 ≥ 0,75 sur le classement par profil ; précision des bloquants ≥ 0,95 et rappel ≥ 0,85 (un faux bloquant est plus grave qu'un manqué) ; calibration de `confidence` (les paires basse-confiance doivent concentrer les erreurs).
- **Processus** : jeu gelé en version (`eval-set-vX`) ; toute modification de `scoring-config.json` exige un run d'évaluation en CI avec non-régression (Spearman −0,02 max toléré) ; rapport archivé.
- **Biais** : jeu contrôlé pour l'équilibre hommes/femmes des prénoms des profils synthétiques ; vérification que masquer le prénom/l'adresse ne change aucun score (test automatique — doit être trivialement vrai puisque ces champs ne sont pas des entrées du moteur).

## 6. Règles d'explication (couche déterministe)

Pour chaque dimension évaluée, un fait est émis :
- `strength` si `s ≥ 0,8` et `w ≥ 6` — ex. « 7/8 compétences indispensables couvertes ».
- `gap` si `s ≤ 0,4` — avec la donnée chiffrée exacte (jamais de paraphrase floue).
- `uncertain` si `k=0` — libellé « non précisé dans l'offre » ou « absent de votre profil » selon le côté manquant.
- Les bloquants sont toujours listés en premier, avec la règle déclenchée.
La reformulation LLM (D14) reçoit **exclusivement** ces faits (`ai-output-schemas.json#match_explanation`) et il est interdit d'y introduire un chiffre ou un fait absent des entrées ; contrôle post-génération par diff des valeurs numériques.
