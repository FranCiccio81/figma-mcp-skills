# 02 — Personas & Jobs-to-be-done

> Boussole — assistant de candidature transparent. Marché : Europe, lancement France (vertical tech prioritaire, cf. R6).
> Statut : v1.0 — 2026-07-23. Références : `01-product-brief.md` (features A–Q, problèmes §3, hypothèses H1–H6), `decisions.md`.
> 🟡 = hypothèse à confirmer en alpha fermée.

---

## 1. Personas primaires

### P1 — Clara, développeuse backend confirmée en veille active

| Attribut | Valeur |
|---|---|
| Âge / situation | 32 ans, Lyon, en poste (CDI), 7 ans d'expérience (Python, FastAPI, PostgreSQL) |
| Statut de recherche | **Veille active** : en poste, ouverte aux opportunités, 1–2 sessions de recherche par semaine, le soir |
| Objectif | Trouver un poste senior backend, hybride ou full-remote, mieux payé, sans y passer ses week-ends |

**Contexte.** Clara reçoit déjà des sollicitations LinkedIn mal ciblées. Elle ne cherche pas « plus d'offres » mais un tri fiable : elle n'a que 2–3 h par semaine à consacrer à sa veille. Elle candidate peu (2–4 candidatures/mois) mais soignées.

**Frustrations.**
- Les scores « magiques » des job boards ne sont ni explicables ni contestables (problème 5 du brief) — elle ne leur fait aucune confiance.
- 80 % des offres « senior backend » qu'elle ouvre sont en réalité sur-site strict ou sous-payées, mais il faut lire toute l'annonce pour le découvrir (problème 2).
- Le salaire n'est presque jamais publié ; les outils qui affichent quand même une « estimation » la font fuir.

**Comportements de recherche.** Filtres stricts (remote, salaire minimum, stack technique) ; lit les explications quand elles existent ; masque agressivement ce qui ne l'intéresse pas ; tient un tableur de suivi qu'elle abandonne au bout de 3 semaines (problème 4).

**Aisance IA.** Élevée — et précisément pour cela, **sceptique** : elle sait ce qu'est une hallucination et refusera tout outil qui invente une ligne sur son CV (risque R4). Elle testera la promesse « zéro invention » en relisant mot à mot les premières générations.

**Critères de succès (pour elle → métriques produit).**
- En < 15 min/semaine, une liste courte d'offres à score ≥ 60 avec bloquants visibles (H3 : ≥ 30 offres à score ≥ 60).
- Comprendre chaque score en un clic (H1) ; jamais un « salaire non communiqué » présenté comme un fait.
- Une lettre générée exploitable après < 2 min de relecture (H4).

---

### P2 — Malik, chef de projet en reconversion

| Attribut | Valeur |
|---|---|
| Âge / situation | 41 ans, Île-de-France, chef de projet IT depuis 12 ans, vise Product Owner / Product Manager |
| Statut de recherche | **Recherche active structurée** : licenciement économique il y a 2 mois, 10–15 h/semaine |
| Objectif | Convertir son expérience projet en profil produit crédible, cibler les bonnes offres malgré un intitulé de CV qui ne « matche » pas |

**Contexte.** Son CV dit « chef de projet », les offres disent « Product Owner » : les moteurs par mots-clés le classent mal. Il a besoin que ses compétences transférables (backlog, priorisation, relation métier) soient reconnues — et de comprendre où sont ses vraies lacunes (certifications, discovery) pour se former.

**Frustrations.**
- Trie des centaines d'offres redondantes multi-diffusées, sans savoir lesquelles se recoupent (problèmes 1 et 2).
- Les rejets ne lui disent jamais si le problème est la séniorité, le titre ou les compétences ; un score opaque ne l'aide pas plus (problème 5).
- Adapter CV + lettre à chaque offre lui prend 1 h 30 ; il craint que les outils IA « vendent » une expérience produit qu'il n'a pas et qu'il se fasse démonter en entretien (problème 3, risque R4).

**Comportements de recherche.** Sessions longues le matin ; candidate en volume moyen (8–12/mois) ; suit tout dans un Google Sheet à 9 colonnes qu'il met réellement à jour (bon candidat pour H5) ; relance à J+10.

**Aisance IA.** Moyenne — utilise ChatGPT pour reformuler, mais ne sait pas juger la fiabilité d'une sortie ; a besoin que l'outil **montre** ce qui vient de son profil (diff, claims d'ancrage) plutôt que de le lui demander sur parole.

**Critères de succès.**
- La similarité de métier par embedding (dimension 3 du matching) fait remonter des offres PO malgré son intitulé « chef de projet ».
- Les lacunes sont nominatives et chiffrées (« l'offre demande 5 ans d'expérience produit, votre profil en totalise 0 sur cet intitulé ») → plan de formation.
- Adaptation CV par offre en < 10 min, relecture-diff comprise (D10), zéro invention.
- Suivi : chaque candidature a un statut à jour, relances visibles (feature P).

---

### P3 — Léa, jeune diplômée

| Attribut | Valeur |
|---|---|
| Âge / situation | 24 ans, Lille, M2 marketing digital, 2 stages + 1 alternance |
| Statut de recherche | **Premier emploi** : recherche intensive, quotidienne, CDI ou CDD, ouverte à la mobilité régionale |
| Objectif | Décrocher un premier CDI ; compenser un CV court par des candidatures mieux ciblées et mieux rédigées |

**Contexte.** Peu d'expérience → les fourchettes « 2 ans minimum » la bloquent partout sans qu'elle sache si c'est rédhibitoire. Son CV d'étudiante est mal structuré (rubriques mélangées) : cas exigeant pour le parsing (R3, H2). Elle candidate beaucoup (30+/mois) et se décourage vite.

**Frustrations.**
- Ne sait pas si candidater « en dessous » des années demandées vaut le coup — le moteur répond précisément (dimension 5 : 1 an pour min 2 → sous-score 0,3, affiché comme lacune, **pas** comme bloquant).
- Lettres de motivation : la page blanche, chaque fois (problème 3).
- A déjà vu un outil IA lui inventer une « maîtrise de SEO technique » — panique à l'idée qu'un recruteur creuse.

**Comportements de recherche.** Mobile-first 🟡 (l'app MVP est desktop-first responsive — à surveiller pour ce persona) ; sessions courtes et fréquentes ; sauvegarde beaucoup, candidate par rafales ; ne suit rien (candidatures perdues, doublons).

**Aisance IA.** Élevée en usage, faible en recul critique : elle exporterait sans relire si l'outil le permettait — la validation obligatoire D10 la protège d'elle-même.

**Critères de succès.**
- Profil validé en < 10 min malgré un CV imparfait (H2) ; les champs incertains clairement badgés, faciles à corriger.
- Comprendre « pourquoi 45/100 » sans se le prendre comme un verdict : lacunes formulées factuellement, jamais de jugement.
- Une lettre sobre, fidèle à ses 3 expériences réelles, prête en 5 min.
- Alternance et CDD correctement filtrés (types de contrat `internship`, `apprenticeship`, `fixed_term`).

---

## 2. Persona secondaire

### P4 — Bruno, cadre senior en recherche confidentielle

| Attribut | Valeur |
|---|---|
| Âge / situation | 51 ans, Nantes, directeur commercial en poste, 25 ans d'expérience |
| Statut de recherche | **Confidentielle et lente** : ne doit surtout pas être visible de son employeur ; 1 session/semaine |
| Aisance IA | Faible — méfiance de principe envers « l'IA qui lit mon CV » |

**Pourquoi secondaire :** volumétrie faible, hors vertical de lancement (tech), mais persona **critique pour la conformité** : il représente l'exigence privacy (D09, feature Q) et la population la moins tolérante à l'opacité. S'il comprend l'interface, tout le monde la comprend.

**Attentes spécifiques.** Aucune donnée revendue ni candidature envoyée à son insu (le MVP ne candidate jamais — à dire explicitement) ; savoir d'où viennent les offres (`GET /sources`) ; pouvoir exporter puis tout supprimer, avec une garantie datée (« purge sous 30 jours ») ; microcopies sans jargon (« indice de confiance » doit être expliqué en une phrase).

---

## 3. Problèmes utilisateurs priorisés (mapping persona × problème)

Problèmes 1–5 = §3 du brief. Échelle : ●●● critique · ●● important · ● présent · — marginal.

| # | Problème (brief §3) | Clara (P1) | Malik (P2) | Léa (P3) | Bruno (P4) | Priorité produit |
|---|---|---|---|---|---|---|
| 1 | Tri d'offres redondantes et mal ciblées, chronophage | ●●● | ●●● | ●● | ● | **P0** — cœur du matching (E, F, G, H) |
| 2 | Impossible de juger une offre sans tout lire | ●●● | ●● | ●● | ●● | **P0** — score + bloquants + inconnues (H, I, J) |
| 3 | Adapter CV/lettre coûteux ; outils IA qui inventent | ●● | ●●● | ●●● | ● | **P0** — génération ancrée + validation (L, M, N, O + D10) |
| 4 | Suivi de candidatures bricolé (tableurs) | ● | ●●● | ●● | ● | **P1** — suivi manuel (P), H5 à valider |
| 5 | Scores opaques, ni explicables ni contestables | ●●● | ●● | ● | ●●● | **P0** — différenciateur (I, J, D03, D14) |
| 6 🟡 | *(dérivé)* Méfiance sur l'usage des données personnelles | ● | ● | ● | ●●● | **P1** — transparence sources + export/suppression (Q, D09) |

Lecture : les problèmes 1, 2, 3, 5 sont P0 et portés par les trois personas primaires ; le problème 4 est P1 (une candidature sans suivi reste une candidature) ; le problème 6 est une extension 🟡 justifiée par P4 et le positionnement RGPD/AI Act (R2).

---

## 4. Jobs-to-be-done

Format : « Quand [situation], je veux [motivation], afin de [résultat] ». Chaque JTBD est relié aux features A–Q du brief (§4) et aux personas porteurs.

| ID | Job-to-be-done | Features | Personas |
|---|---|---|---|
| **JTBD-01** | Quand je démarre ma recherche, je veux transformer mon CV en profil structuré fiable sans tout ressaisir, afin de partir d'une base exacte que je contrôle champ par champ. | A, B, C | Toutes ; critique P3 (CV mal structuré) |
| **JTBD-02** | Quand un champ de mon profil a été extrait automatiquement, je veux voir d'où il vient et à quel point l'extraction est sûre, afin de corriger vite ce qui est douteux et de valider le reste en bloc. | B, C | P1, P2 ; conformité P4 (provenance D05) |
| **JTBD-03** | Quand je définis mes critères (métiers, lieux, télétravail, contrat, salaire, langues, secteurs exclus), je veux qu'ils soient réellement appliqués au tri et aux bloquants, afin de ne plus jamais ouvrir une offre incompatible « pour vérifier ». | D, G, H | P1 (remote/salaire strict), P3 (contrats) |
| **JTBD-04** | Quand j'ouvre ma liste d'offres, je veux voir en un coup d'œil le score, la confiance et les éventuels bloquants de chaque offre, afin de décider en secondes lesquelles méritent lecture. | E, F, G, H, I, K | P1, P2, P3 — problème 1 et 2 |
| **JTBD-05** | Quand un score me surprend (trop haut ou trop bas), je veux l'explication dimension par dimension — forces, lacunes chiffrées, données inconnues, afin de contester ou d'accepter le verdict en connaissance de cause. | H, I, J | P1, P4 — problème 5, hypothèse H1 |
| **JTBD-06** | Quand une donnée clé manque (salaire, séniorité), je veux qu'elle soit affichée « non précisé » et reflétée dans l'indice de confiance, afin de ne jamais décider sur une estimation déguisée en fait. | I, J, F | P1 (salaire), P4 (défiance) — D03 |
| **JTBD-07** | Quand une offre me plaît, je veux générer un e-mail ou une lettre rédigés uniquement à partir de mon profil validé, puis relire et valider avant tout export, afin de candidater vite sans risquer une invention qui me grillerait en entretien. | L, M | P2, P3 — problème 3, D10, R4, H4 |
| **JTBD-08** | Quand une offre exigeante est à ma portée, je veux adapter mon CV à cette offre en voyant précisément chaque modification proposée (diff), afin de mettre en avant le pertinent sans jamais altérer les faits. | O (et N pour l'optimisation générale) | P2 (reconversion), P1 |
| **JTBD-09** | Quand je multiplie les candidatures, je veux les suivre dans un seul endroit avec statuts, notes et historique — y compris celles envoyées hors plateforme, afin de relancer au bon moment et de ne jamais candidater deux fois au même poste. | P, K | P2 (tableur remplacé), P3 (doublons) — H5 |
| **JTBD-10** | Quand j'arrête ma recherche ou que je perds confiance, je veux exporter toutes mes données puis supprimer mon compte avec une garantie de purge datée, afin de rester maître de mes données personnelles. | Q, A | P4 ; toutes (RGPD, D09) |

**Couverture des features.** A (01, 10) · B (01, 02) · C (01, 02) · D (03) · E (04) · F (04, 06) · G (03, 04) · H (03, 04, 05) · I (04, 05, 06) · J (05, 06) · K (04, 09) · L (07) · M (07) · N (08) · O (08) · P (09) · Q (10). Toutes les features A–Q sont portées par au moins un JTBD.

---

## 5. Questions ouvertes

1. 🟡 **P3 et le desktop-first** : Léa est mobile-first alors que le MVP est desktop-first responsive (pas d'app native, hors périmètre). Faut-il définir un seuil de qualité mobile web (parcours consultation + suivi utilisables au doigt, cibles 44 px) comme exigence MVP, ou assumer que P3 est mal servie au lancement ?
2. 🟡 **Vertical de lancement vs personas** : le lancement est « tech France » (R6), mais P2 (produit) et P3 (marketing) débordent du vertical strict. Confirmer le périmètre exact des verticales alpha (tech seulement, ou tech + produit + support comme le jeu annoté du 06 §5 le suggère : tech, support, vente).
3. 🟡 **Digest e-mail de fin de MVP** (brief §4 « possible en fin de MVP ») : quel persona prioritaire ? La veille passive de P1 en dépend fortement (fréquence hebdo suffirait) — à instruire avant tout travail d'IA/notification.
4. 🟡 **Multi-CV** : P2 (reconversion) est le persona le plus susceptible de demander deux profils (« chef de projet » vs « PO »). Le MVP impose un canonique unique + variantes par offre (D05). Mesurer explicitement cette demande en alpha (déclencheur de réévaluation D05).
5. 🟡 **Seuil de « décourageant » pour P3** : un jeune diplômé verra beaucoup de scores < 50. Faut-il un traitement UX spécifique (mise en avant des offres accessibles, ton des microcopies de lacunes) au-delà de la neutralité factuelle déjà spécifiée ?
