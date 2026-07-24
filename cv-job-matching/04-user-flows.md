# 04 — Parcours utilisateurs

> Boussole — parcours détaillés du MVP. Statut : v1.0 — 2026-07-23.
> Les IDs d'écrans **SCR-xx** sont définis dans `03-information-architecture.md`. Endpoints : `12-api-contracts.md` / `openapi.yaml`. Règles de matching : `06-matching-specification.md`. Invariants non négociables : D03 (score ≠ confiance), D10 (validation humaine avant export), bloquants badgés jamais masqués, inconnues affichées « non précisé », provenance/confiance par champ, source + lien d'origine sur chaque offre, aucune candidature automatique.
> 🟡 = hypothèse. Les microcopies critiques exactes sont regroupées en §M (référencées M1–M6 dans les flux).

Conventions accessibilité (WCAG 2.1 AA), applicables à **tous** les flux, complétées par flux :
- Contrastes : 4,5:1 texte, 3:1 composants UI et focus ring. Ne jamais utiliser une couleur de type `Grey/400` (2,85:1 sur blanc) pour du texte porteur d'information — y compris les scores grisés `low_data`, qui doivent rester lisibles (griser ≠ illisible).
- Cibles tactiles ≥ 44 px (web) ; focus visible sur tout élément interactif ; navigation clavier complète ; Échap ferme panneaux et modales avec retour du focus à l'élément déclencheur.
- États asynchrones : conteneur `role="status"` + `aria-live="polite"` pour les progressions ; `role="alert"` (assertive) pour les erreurs ; jamais d'information portée par la couleur seule (les badges combinent icône + libellé).

---

## Flux 1 — Onboarding : inscription, import du CV, validation du profil

**Objectif** : compte créé → profil validé en < 10 min (H2). Features A, B, C.
**Préconditions** : aucune (visiteur). CV PDF ou DOCX ≤ 10 Mo disponible.

**Étapes.**
1. **SCR-02** — saisie email + mot de passe + consentements (obligatoire : CGU/traitement ; optionnel : échantillonnage debug 30 j). `POST /auth/register` puis `POST /auth/login`. → redirection SCR-05.
2. **SCR-05** — dépôt du fichier. Contrôles client immédiats (extension, taille) avant upload. `POST /cv-documents` → 202 `{task}`.
3. **SCR-05 (état Parsing en cours)** — polling `GET /cv-documents/{id}` (2 s, backoff ×1,5). Étapes affichées : « Lecture du document » → « Extraction des informations » → « Préparation de votre profil ». Annonce ARIA à chaque changement d'étape ; l'utilisateur peut naviguer ailleurs, la reprise se fait depuis SCR-10 (checklist).
4. `status=parsed` → **SCR-06**. `GET /profile` : chaque champ affiche provenance + confiance (M3). Les champs à confiance < 0,5 sont regroupés en tête de page dans un bloc « À vérifier (n) » — rappel : ces données sont déjà traitées comme inconnues par le moteur (06 §1), les corriger améliore directement l'indice de confiance.
5. L'utilisateur corrige/complète : `PATCH /profile`, CRUD `experiences` / `educations` / `skills` / `languages`. Sauvegarde par champ (optimiste, rollback si erreur inline).
6. **Point de décision — validation** : bouton « Valider mon profil » actif si ≥ 3 compétences ET ≥ 1 expérience ou formation. `POST /profile/validate` → promotion `cv_extraction` → `user_confirmed` (11 §2). Message de succès : « Profil validé. Vos scores de compatibilité sont désormais calculés sur ces informations. » → **SCR-07** (Flux 2).

**Points de décision.**
- Étape 2 : « Passer et saisir manuellement » 🟡 (question ouverte 03-Q3) → SCR-06 vide en mode saisie.
- Étape 6 : quitter sans valider → autorisé ; SCR-10 garde la checklist ; tri `match` et génération restent indisponibles (gating 03 §3).

**Cas limites et récupération.**

| Cas | Détection | Comportement |
|---|---|---|
| CV illisible | `status=failed`, `error_code=unreadable` | Message : « Nous n'avons pas réussi à lire ce fichier. Vérifiez qu'il s'ouvre correctement, ou essayez un export PDF récent. » + boutons « Réessayer » / « Choisir un autre fichier » |
| PDF image (scan) | `error_code=image_only_pdf` | Message : « Ce PDF ne contient que des images, sans texte extractible. Exportez votre CV en PDF depuis votre traitement de texte, ou importez le fichier DOCX d'origine. » (pas d'OCR au MVP 🟡) |
| Fichier trop lourd | contrôle client, sinon `too_large` | « Fichier trop volumineux (max 10 Mo). » |
| Format non supporté | contrôle client, sinon `unsupported_format` | « Formats acceptés : PDF et DOCX. » |
| Échec d'extraction | `error_code=extraction_failed` | « L'extraction a échoué de notre côté. Réessayez ; si le problème persiste, vous pouvez saisir votre profil manuellement. » + `trace_id` repliable |
| **Parsing partiel** | `status=parsed` + `extraction_warnings[]` | SCR-06 s'ouvre avec bandeau : « Certaines sections n'ont pas pu être entièrement extraites : {liste}. Les champs concernés sont marqués “À vérifier”. » Jamais présenté comme un échec — le profil partiel est éditable |
| Quota upload atteint | 429 (5/j) | « Limite de 5 imports par jour atteinte. Réessayez demain — votre dernier import reste disponible. » + `Retry-After` |
| Session interrompue en cours de parsing | reconnexion | `GET /me` → checklist SCR-10 pointe vers l'état réel (`GET /cv-documents/{id}`) |

**Accessibilité spécifique.** Dropzone SCR-05 : utilisable au clavier (bouton « Choisir un fichier » équivalent au glisser-déposer) ; progression du parsing annoncée par `aria-live="polite"` (une annonce par étape, pas de spam) ; en SCR-06, chaque badge de provenance est un texte (« Extrait du CV — confiance 62 % »), pas une pastille de couleur seule ; le bloc « À vérifier » est un landmark accessible en premier via lien d'évitement ; focus déplacé sur le titre de SCR-06 à l'arrivée.

---

## Flux 2 — Définition des préférences

**Objectif** : critères complets → matching personnalisé. Feature D.
**Préconditions** : connecté. Nominal : juste après Flux 1 (profil validé) ; accessible à tout moment via l'entrée « Préférences ».

**Étapes.**
1. **SCR-07** — `GET /preferences` (vide au premier passage : valeurs par défaut proposées, aucune option stricte pré-cochée).
2. Saisie du bloc obligatoire 🟡 : métiers cibles (≥ 1 intitulé), localisation(s) + rayon (défaut 30 km 🟡) et/ou télétravail, type(s) de contrat.
3. Blocs repliés « Affiner » : salaire (fourchette + case « minimum strict »), langues (CECRL), secteurs préférés / **exclus**, entreprises cibles, mots-clés.
4. **Point de décision — options strictes** : cocher « strict » (contrat, salaire minimum) ou exclure un secteur affiche la conséquence : « Les offres incompatibles seront marquées “Critère bloquant”. Elles resteront visibles, jamais supprimées de vos résultats. »
5. Enregistrement : `PUT /preferences` (remplacement complet — l'UI envoie toujours l'état entier du formulaire). Succès : « Préférences enregistrées. Vos scores sont en cours de mise à jour. » (re-scoring asynchrone, 06 §4) → CTA « Voir mes offres » (SCR-20).

**Cas limites.**
- Rayon sans localisation, fourchette salaire min > max, niveau CECRL manquant sur une langue ajoutée → 422 `errors[]` mappées par champ, focus déplacé sur la première erreur.
- Aucun métier cible : autorisé par le moteur (fallback : 2 derniers intitulés occupés, 06 dim. 3) — l'UI le signale : « Sans métier cible, nous utiliserons vos derniers intitulés de poste. »
- Modification des préférences plus tard : mêmes écrans ; bandeau de re-scoring en cours sur SCR-20 tant que les scores ne sont pas à jour 🟡 (pas d'endpoint d'état de re-scoring — question ouverte Q4).

**Accessibilité.** Groupes de cases à cocher avec `fieldset`/`legend` ; le libellé de conséquence des options strictes est lié par `aria-describedby` ; les listes à ajout dynamique (langues, lieux) annoncent l'ajout/suppression (`aria-live`) ; toutes les commandes de suppression d'item ≥ 44 px.

---

## Flux 3 — Découverte et recherche d'offres

**Objectif** : de l'arrivée sur la liste à une sélection d'offres à examiner. Features E, F, G, H, I, K.
**Préconditions** : connecté. Profil validé pour le tri `match` ; sinon parcours dégradé assumé.

**Étapes.**
1. **SCR-20** — `GET /jobs` (tri `match` par défaut si profil validé, sinon `relevance` + bandeau « Validez votre profil pour trier par compatibilité »).
2. Lecture des cartes : score + confiance (M1 format court), badge « Critère bloquant » le cas échéant (M2), « Salaire non communiqué » le cas échéant (M3), source de l'offre.
3. Affinage : `q`, filtres (localisation, remote, contrat, séniorité, langue, salaire min, fraîcheur, source). Chaque changement relance `GET /jobs` (debounce 300 ms 🟡, quota recherche 30/min).
4. **Point de décision — offres bloquées** : interrupteur « Afficher les offres bloquées » (défaut **activé**, `include_blocked=true`). Le tri par défaut les relègue en fin de liste (06 §1) mais elles restent badgées, jamais retirées sans action explicite de l'utilisateur.
5. Actions par carte : ouvrir (SCR-21, Flux 4) ; sauvegarder (`PUT /jobs/{id}/saved-state` `state=saved`) ; masquer (`state=hidden` — toast avec « Annuler », l'offre reste restaurable en SCR-23).
6. Pagination par curseur : « Charger plus » (jamais de scroll infini sans bouton 🟡 — accessibilité et repérage).

**Cas limites.**

| Cas | Comportement |
|---|---|
| **0 offre** (résultat vide) | État vide actionnable : « Aucune offre ne correspond à ces critères. » + suggestions ordonnées : élargir le rayon, retirer le dernier filtre appliqué (chip cliquable), vérifier les métiers cibles. + rappel transparence : « Boussole interroge {n} sources — voir les sources » (SCR-73). Jamais de résultats « approchants » injectés silencieusement |
| 0 offre au premier passage (profil pilote hors vertical, R6/H3) | Même état vide + mention explicite du périmètre : « Nos sources couvrent principalement la tech en France pour ce lancement. » 🟡 formulation à valider par le marketing |
| Score grisé `low_data=true` sur une carte | Score affiché grisé + libellé « Données insuffisantes » (M1) — pas d'omission du score |
| Re-scoring en cours (préférences modifiées) | Bandeau : « Vos scores sont en cours de mise à jour — certains résultats peuvent encore refléter vos anciennes préférences. » |
| 429 recherche | « Vous filtrez plus vite que nous ! Réessayez dans {Retry-After} s. » 🟡 ton à valider ; les résultats courants restent affichés |
| Erreur serveur | Liste précédente conservée si disponible + `role="alert"` ; bouton « Réessayer » |

**Accessibilité.** Résultats dans une région `aria-live="polite"` annonçant « {n} offres trouvées » après chaque filtrage ; les filtres actifs sont des chips supprimables au clavier ; l'interrupteur des offres bloquées est un vrai `switch` avec état annoncé ; les cartes sont des liens (titre = intitulé d'accessibilité complet : poste, entreprise, score, confiance, badge éventuel).

---

## Flux 4 — Consultation d'une offre : score, confiance, explication

**Objectif** : comprendre en < 1 min si l'offre vaut une candidature (H1 : ≥ 40 % ouvrent l'explication). Features H, I, J, K.
**Préconditions** : connecté ; offre existante. Profil validé pour le panneau match complet.

**Étapes.**
1. **SCR-21** — `GET /jobs/{id}` + `GET /jobs/{id}/match` (calcul synchrone < 50 ms si non scorée — squelette bref sur le panneau match uniquement).
2. En-tête : titre, entreprise, lieu(x), contrat, remote, date de publication, **source(s) avec lien(s) d'origine** — une ligne par source (« Publiée sur {source} — voir l'annonce d'origine », lien externe marqué comme tel).
3. **Panneau match** : double affichage score/confiance (M1) ; puis dans l'ordre : (a) `blocking_criteria[]` (M2), (b) `unknown_dimensions[]` (M3), (c) dimensions détaillées (sous-score, poids, valeurs comparées — ex. compétences couvertes/proches/manquantes nominatives).
4. **Point de décision — explication** : « Pourquoi ce score ? » → **SCR-22**. Couche déterministe immédiate (bloquants → forces → lacunes chiffrées → inconnues, 06 §6). Bouton « Reformuler en langage clair » → `POST /jobs/{id}/explanation` (LLM, cache par version) ; le texte porte la mention « Reformulation générée à partir des faits ci-dessus ».
5. Lien permanent « Comment ce score est calculé » → SCR-74.
6. Actions de sortie : Sauvegarder / Masquer ; « Générer une candidature » → Flux 5 ; « J'ai postulé » → Flux 7 (création de candidature pré-remplie).

**Points de décision.**
- Bloquant présent : l'offre reste consultable et toutes les actions restent disponibles 🟡 (générer une lettre pour une offre bloquée est permis — le badge informe, il n'interdit pas ; cohérent avec « l'offre reste visible, badgée »).
- `low_data=true` : score grisé + M1-c ; l'explication liste les inconnues en priorité.

**Cas limites.**

| Cas | Comportement |
|---|---|
| Offre expirée | Bandeau : « Cette offre n'est plus publiée par sa source (expirée le {date}). » Lien d'origine conservé ; génération désactivée 🟡 (03-Q6) ; « J'ai postulé » reste actif (candidature réelle possible avant expiration) |
| Bloquant sur donnée à confiance < 0,7 | Jamais affiché comme bloquant (06 §3) : rétrogradé en avertissement (M2-b) |
| Reformulation LLM échoue | Les faits déterministes restent affichés ; note : « La reformulation est momentanément indisponible. Les éléments ci-dessus restent exacts et complets. » |
| Quota LLM atteint (10/h, 40/j) | 429 → M4-b ; la couche déterministe reste intégralement disponible |
| Offre supprimée / d'autrui | 404 → SCR-90 |

**Accessibilité.** Le double score est un groupe avec libellé complet lisible par lecteur d'écran (« Compatibilité 72 sur 100. Confiance 61 sur 100. ») — jamais deux chiffres orphelins ; SCR-22 en panneau latéral : focus déplacé à l'ouverture sur son titre, piégé dans le panneau, Échap referme et rend le focus au bouton « Pourquoi ce score ? » ; l'arrivée de la reformulation LLM est annoncée (`aria-live="polite"`) ; les jauges de sous-scores ont des équivalents textuels ; contrainte contraste sur le score grisé (voir conventions).

---

## Flux 5 — Génération d'une lettre ou d'un e-mail : relecture, diff, validation, export

**Objectif** : contenu fidèle au profil validé, exporté après validation humaine (D10, H4 : ≥ 50 % exportés). Features L, M.
**Préconditions** : profil validé (sinon `profile_not_validated`) ; offre cible active 🟡 ; quota LLM disponible.

**Étapes.**
1. Depuis SCR-21 ou SCR-41 : « Générer une candidature » → **SCR-30**.
2. Choix : type (`email` / `cover_letter`), ton (`sobre` défaut / `chaleureux` / `direct`), langue (`fr`/`en`, pré-sélectionnée selon la langue de l'offre), longueur (`court`/`standard`). Quota restant affiché (« {n} générations restantes aujourd'hui »).
3. **Avertissement anti-invention systématique** (M4) affiché dans SCR-30, au-dessus du bouton « Générer ».
4. `POST /generations` (avec `Idempotency-Key`) → 202 → **SCR-31** en état « Génération en cours » (polling `GET /generations/{id}`, annonce ARIA « Rédaction en cours »).
5. `status=draft` → **SCR-31 (relecture)** : texte intégral + panneau « Affirmations et leurs sources » : chaque `claim` (ex. « 5 ans d'expérience backend ») reliée à son `profile_ref`, cliquable vers la section du profil ; résultat du contrôle d'ancrage (`anchoring_check`) ; métadonnées (« Basé sur votre profil v{n} »).
6. **Point de décision — édition** : modification libre du texte (`PATCH /generations/{id}`) ; l'édition manuelle est de la responsabilité de l'utilisateur (contenu `user_input` par nature).
7. **Validation humaine** : bouton « J'ai relu ce document, je le valide » → `POST /generations/{id}/validate` → `status=validated`. Tant que non validé, le bouton « Exporter » est désactivé avec l'explication : « Relisez et validez ce document pour pouvoir l'exporter. »
8. **SCR-32** — export : « Copier le texte » / « Télécharger en PDF » / « Télécharger en DOCX » (`POST /generations/{id}/export`) ; rappel : « Boussole n'envoie rien à votre place : c'est vous qui transmettez ce document. » Puis proposition : « Créer le suivi de cette candidature ? » → Flux 7.

**Cas limites.**

| Cas | Comportement |
|---|---|
| **Génération échouée** (`status=failed`) | « La rédaction a échoué. Aucun contenu n'a été produit. » + « Réessayer » (nouvelle `Idempotency-Key`) + `trace_id`. Le quota consommé n'est pas re-décompté 🟡 (à confirmer côté back — question ouverte Q5) |
| **Quota LLM atteint** | 429 avant lancement : M4-b avec heure de déblocage (`Retry-After`). Le bouton « Générer » de SCR-30 est désactivé tant que le quota est nul |
| `anchoring_check.status=failed` | Bandeau d'alerte + `unanchored_claims` surlignées dans le texte : « {n} affirmation(s) n'ont pas pu être reliées à votre profil. Supprimez-les ou corrigez-les avant validation. » Validation bloquée tant qu'elles subsistent 🟡 (03-Q5) |
| Double-clic / rejeu | `Idempotency-Key` → `Idempotent-Replay: true`, une seule génération créée |
| Tentative d'export non validé (URL directe, état obsolète) | 409 `generation_not_validated` → retour SCR-31 avec message : « Ce document doit être relu et validé avant export. » (libellé API repris tel quel) |
| Profil modifié après génération | Le document garde `based_on_profile_version` ; si le profil courant est plus récent, bandeau informatif : « Ce document est basé sur une version antérieure de votre profil (v{n}). » + « Regénérer » 🟡 |
| Offre expirée entre-temps | `job_expired` au lancement → message + l'offre reste consultable |

**Accessibilité.** Progression de génération : `role="status"`, annonces espacées (pas à chaque poll) ; le passage à `draft` est annoncé (« Brouillon prêt à relire ») et le focus déplacé sur le titre du document ; le panneau des claims est navigable au clavier, chaque lien de `profile_ref` a un intitulé explicite (« Voir la source dans votre profil : expérience Développeuse backend, ACME ») ; les surlignages d'`unanchored_claims` combinent couleur + icône + liste textuelle récapitulative ; la zone d'édition est un vrai `textarea`/éditeur accessible (pas de contentEditable non labellisé).

---

## Flux 6 — Adaptation du CV à une offre

**Objectif** : variante de CV dérivée du canonique, chaque changement visible et validé (feature O ; D05 : la variante référence le canonique, jamais l'inverse). Même invariants que Flux 5.
**Préconditions** : profil validé ; offre cible. (Variante sans offre = optimisation générale, feature N : même parcours avec `doc_type=cv_optimization`, sans `job_id`, lancé depuis SCR-50.)

**Étapes.**
1. Depuis SCR-21 : « Adapter mon CV à cette offre » → **SCR-30** avec `doc_type=cv_variant` pré-sélectionné. Avertissement M4 (variante : « … ne réordonne et reformule que des éléments présents dans votre profil validé »).
2. `POST /generations` → 202 → **SCR-31** (génération en cours).
3. `status=draft` → **SCR-31 en mode diff** : vue côte à côte (desktop) / empilée (mobile) canonique → variante, par section : éléments **mis en avant** (réordonnés), **reformulés** (ancien/nouveau texte), **retirés de la variante** (jamais supprimés du canonique — mention explicite : « Votre profil d'origine n'est pas modifié »). Aucun ajout de fait nouveau possible par construction ; le contrôle d'ancrage s'applique aux reformulations.
4. **Point de décision — arbitrage par changement** 🟡 : accepter/refuser chaque modification individuellement (recommandé) ou éditer globalement (`PATCH`). Question ouverte Q6 sur la granularité supportée par le contrat.
5. Validation (« J'ai relu, je valide ») → export **SCR-32** (PDF/DOCX prioritaires pour un CV).
6. Proposition de liaison : « Joindre ce CV au suivi de votre candidature ? » → Flux 7.

**Cas limites.** Identiques au Flux 5 (échec, quota, ancrage, idempotence, offre expirée), plus :
- Profil canonique modifié pendant la relecture : la variante reste figée sur `based_on_profile_version` ; bandeau + « Regénérer depuis le profil actuel ».
- Variante quasi identique au canonique (offre déjà très alignée) : message honnête : « Votre CV actuel couvre déjà bien cette offre — peu de modifications proposées. » (pas de changements cosmétiques pour « justifier » la génération).

**Accessibilité.** Le diff n'est jamais porté par la couleur seule : préfixes textuels (« Ajouté à la variante », « Reformulé », « Retiré de la variante ») + icônes ; navigation de changement en changement au clavier (raccourcis n/p 🟡 + boutons visibles) ; en vue empilée mobile, chaque paire ancien/nouveau est un groupe labellisé ; cibles des boutons accepter/refuser ≥ 44 px.

---

## Flux 7 — Suivi de candidature

**Objectif** : chaque candidature suivie, statuts à jour (feature P, H5 : ≥ 40 % avec ≥ 1 mise à jour). Saisie **manuelle** : l'état « envoyée » est toujours déclaré par l'utilisateur (D10).
**Préconditions** : connecté. Une candidature référence une offre interne **ou** un couple externe (intitulé + entreprise).

**Étapes.**
1. **Création** — trois portes d'entrée : (a) SCR-21 « J'ai postulé » → `POST /applications` pré-rempli (`job_posting_id`, statut initial `applied`) ; (b) SCR-32 après export → statut initial `to_apply` (« à envoyer ») ; (c) **SCR-42** ajout externe (`external_title` + `external_company` + URL optionnelle), statut `to_apply` ou `applied`.
2. **SCR-40** — vue par statut : `draft` → `to_apply` → `applied` → `interviewing` → `offer` / `rejected` / `withdrawn` (libellés FR : Brouillon / À envoyer / Envoyée / Entretiens / Offre reçue / Refusée / Retirée).
3. **SCR-41** — détail : frise des événements historisés (`application_events`), notes, documents générés liés (avec leur statut draft/validated/exported), lien vers l'offre (SCR-21) ou `external_url`.
4. **Changement de statut** : sélection du nouveau statut + note optionnelle (≤ 1000 car.) → `POST /applications/{id}/status`. Chaque transition est historisée, l'historique n'est jamais réécrit.
5. **Relance** : SCR-10 remonte les candidatures `applied` sans événement depuis J+10 🟡 (« À relancer ? ») ; la relance elle-même est une note + éventuel e-mail généré (Flux 5 avec `application_id`).

**Points de décision.**
- Candidature sur offre également masquée : autorisé (masquer une offre n'affecte pas son suivi).
- Suppression d'une candidature : confirmation (« Supprimer ce suivi ? L'historique de cette candidature sera définitivement effacé. Les documents générés associés ne seront pas supprimés 🟡. ») → `DELETE /applications/{id}`.

**Cas limites.**

| Cas | Comportement |
|---|---|
| Offre expirée après candidature | SCR-41 garde le lien + badge « offre expirée » ; le suivi continue normalement (l'expiration d'une annonce n'annule pas un processus de recrutement) |
| Doublon (même offre, deuxième « J'ai postulé ») | Détection côté client : « Vous suivez déjà une candidature pour cette offre. » + lien vers SCR-41 existant 🟡 (pas de contrainte d'unicité documentée côté API — question ouverte Q7) |
| Transition rejetée | 422 → message : « Ce changement de statut n'est pas permis depuis “{statut actuel}”. » 🟡 (matrice de transitions non documentée — Q7) |
| Candidature externe incomplète | 422 (contrainte 11 §5 : intitulé + entreprise requis) → erreurs par champ |

**Accessibilité.** Les colonnes de statut (desktop) sont des listes labellisées, pas un kanban à glisser-déposer obligatoire : le changement de statut passe toujours par un menu accessible (le drag-and-drop, s'il existe, est un raccourci 🟡) ; la frise d'événements est une liste ordonnée datée ; les compteurs par statut sont annoncés ; changement de statut confirmé par annonce `aria-live` (« Statut mis à jour : Entretiens »).

---

## Flux 8 — Suppression de compte

**Objectif** : suppression conforme RGPD — soft delete immédiat, purge effective ≤ 30 jours (D09, feature Q). Aucune rétention cachée (hors anonymisation `ai_calls`/`audit_log`, 11 §2).
**Préconditions** : connecté ; mot de passe connu.

**Étapes.**
1. **SCR-71** — Confidentialité & données → « Supprimer mon compte » → **SCR-72**.
2. SCR-72 explique les conséquences (liste exhaustive : profil, CV importés, préférences, candidatures et historique, documents générés, sauvegardes) et **propose l'export préalable** : « Avant de partir, vous pouvez télécharger une copie de vos données. » → `POST /privacy/export` (Flux annexe : polling `GET /privacy/exports/{id}`, lien signé 7 j, quota 2/j).
3. **Point de décision — modale de confirmation** (M5) : texte exact + champ mot de passe + boutons « Supprimer mon compte » (destructif) / « Annuler » (défaut).
4. `DELETE /account` (body : `password`) → succès : session terminée, redirection SCR-01 avec message : « Votre compte a été supprimé. Vos données seront définitivement effacées sous 30 jours. » 🟡 + e-mail de confirmation avec date de purge (recommandé — Q8).

**Cas limites.**

| Cas | Comportement |
|---|---|
| Mot de passe erroné | Erreur inline sur le champ, compteur de tentatives (rate limit global), la modale reste ouverte |
| Export demandé en même temps | La suppression n'attend pas l'export : avertissement dans la modale si un export est `pending` : « Votre export en cours sera perdu si vous supprimez le compte maintenant. » 🟡 |
| Reconnexion après suppression | Identifiants invalides (message générique — le compte soft-deleted est inaccessible, anti-énumération) ; annulation de la suppression pendant la fenêtre de 30 j **non offerte** au MVP 🟡 (Q8) |
| Quota export atteint (2/j) | 429 → « Limite de 2 exports par jour atteinte. » — n'empêche pas la suppression |

**Accessibilité.** Modale : focus initial sur le champ mot de passe 🟡 (ou sur « Annuler » — à trancher en test ; jamais sur le bouton destructif) ; `role="alertdialog"` avec titre et description liés ; Échap = annuler ; le bouton destructif est distinct par le libellé, pas seulement par la couleur ; confirmation finale annoncée avant la redirection.

---

## §M — Microcopies critiques exactes (français)

Chaîne de référence pour l'i18n (clés indicatives 🟡). Tout écart à ces libellés doit repasser par la revue produit.

### M1 — Double affichage score / confiance (D03)

- **M1-a — Format carte (SCR-20, SCR-10)** :
  > **Compatibilité 72** · Confiance 61
  (les deux valeurs toujours côte à côte, jamais l'une sans l'autre, jamais fusionnées)
- **M1-b — Format détail (SCR-21), avec libellés complets** :
  > **Compatibilité : 72 / 100** — la qualité du match, calculée uniquement sur les critères connus.
  > **Confiance : 61 / 100** — la part des informations réellement disponibles pour ce calcul.
- **M1-c — Info-bulle / aide (icône « ? »)** :
  > « Deux chiffres, deux questions. La compatibilité répond à : “ce qui est connu correspond-il à votre profil ?”. La confiance répond à : “que sait-on vraiment de cette offre et de votre profil ?”. Un score élevé avec une confiance basse repose sur peu d'informations : les éléments manquants sont listés sous “Non précisé”. »
- **M1-d — Score en données insuffisantes (`low_data=true`, < 40 % du poids connu)** :
  > « **Données insuffisantes** — moins de 40 % des critères sont connus pour cette offre. Le score de 68 est donné à titre indicatif. »

### M2 — Badge critère bloquant

- **M2-a — Badge (liste et détail)** : `⛔ Critère bloquant` — toujours accompagné, au détail, de la règle en toutes lettres :

  | Code (06 §3) | Microcopie exacte |
  |---|---|
  | `remote_required` | « Vous exigez du télétravail complet ; ce poste est sur site. » |
  | `location_incompatible` | « Poste sur site à {ville}, à {d} km de vos lieux acceptés (au-delà du double de votre rayon de {r} km). » |
  | `language_missing` | « {Langue} niveau {niveau} exigé ; cette langue est absente de votre profil (ou plus de deux niveaux en dessous). » |
  | `contract_excluded` | « Contrat {type}, que vous avez exclu (mode strict). » |
  | `salary_below_minimum` | « Salaire maximum annoncé ({montant} €) inférieur à votre minimum strict ({montant} €). » |
  | `sector_excluded` | « Secteur {secteur}, que vous avez exclu de votre recherche. » |

- **M2-b — Phrase d'accompagnement systématique (transparence, jamais de masquage)** :
  > « Cette offre reste affichée par transparence. Un critère bloquant n'annule pas le score : il signale une incompatibilité avec vos exigences. Modifiable dans vos préférences. »
- **M2-c — Bloquant rétrogradé (donnée à confiance < 0,7, 06 §3)** :
  > « ⚠️ Incompatibilité possible — {règle}, mais cette information extraite de l'offre est incertaine. Vérifiez l'annonce d'origine. »

### M3 — Données inconnues et champs incertains

- **M3-a — Dimension inconnue côté offre** (libellés API repris tels quels) :
  > « Salaire non communiqué » · « Niveau non précisé dans l'offre » · générique : « {Critère} : non précisé dans l'offre »
- **M3-b — Dimension inconnue côté profil** :
  > « {Critère} : absent de votre profil — complétez votre profil pour évaluer ce critère. »
- **M3-c — Règle d'affichage (rappel, 06 §1)** : une donnée inconnue n'est **jamais** remplacée par une estimation ; elle est listée sous « Non précisé » et abaisse l'indice de confiance, pas le score.
- **M3-d — Champ de profil incertain (SCR-06/SCR-50)** :
  > « Extrait du CV — confiance {p} %. Vérifiez cette information : en dessous de 50 %, elle n'est pas utilisée pour vos scores. »

### M4 — Avertissement anti-invention (avant toute génération, SCR-30)

- **M4-a — Texte principal (systématique, non désactivable)** :
  > « **Rédigé uniquement à partir de votre profil validé.** Boussole n'inventera aucune compétence, expérience ou formation. Chaque affirmation du texte sera reliée à sa source dans votre profil. Vous devrez relire et valider le document avant de pouvoir l'exporter — rien n'est envoyé à votre place. »
- **M4-b — Quota LLM atteint (429)** :
  > « Limite de générations atteinte ({n} par heure, {m} par jour). Prochaine génération possible à {heure}. Vos brouillons existants restent accessibles. »

### M5 — Confirmation de suppression de compte (SCR-72)

- **Titre** : « Supprimer définitivement votre compte ? »
- **Corps** :
  > « Votre compte sera désactivé immédiatement. Toutes vos données — profil, CV importés, préférences, candidatures et documents générés — seront définitivement effacées sous 30 jours, conformément à notre engagement RGPD. Cette action est irréversible.
  > Astuce : vous pouvez d'abord télécharger une copie de vos données depuis “Confidentialité & données”.
  > Pour confirmer, saisissez votre mot de passe. »
- **Boutons** : « Supprimer mon compte » (action destructive) · « Annuler » (action par défaut).
- **Après succès (SCR-01)** : « Votre compte a été supprimé. Vos données seront définitivement effacées sous 30 jours. »

### M6 — Rappels transverses

- **Aucune candidature automatique (SCR-32, pied de SCR-30)** :
  > « Boussole n'envoie jamais de candidature à votre place. »
- **Transparence des sources (état vide SCR-20, SCR-73)** :
  > « Boussole interroge {n} sources d'offres identifiées — pas “tout le web”. Chaque offre conserve le lien vers son annonce d'origine. »

---

## Questions ouvertes

1. 🟡 **Génération sur offre bloquée** (Flux 4/5) : autorisée dans cette spec (le badge informe, il n'interdit pas). Confirmer produit — alternative : interstitiel de confirmation (« Cette offre présente un critère bloquant, générer quand même ? »).
2. 🟡 **Offre expirée × génération** (Flux 4/5, 03-Q6) : périmètre exact des actions renvoyant `job_expired` à préciser dans `openapi.yaml`.
3. 🟡 **OCR des PDF image** (Flux 1) : `image_only_pdf` est traité en échec définitif au MVP. Confirmer qu'aucun OCR n'est prévu (impact P3 — CV scannés plus fréquents chez certains publics).
4. 🟡 **État du re-scoring** (Flux 2/3) : aucun endpoint n'expose « scores à jour / en cours de recalcul ». Le bandeau UI repose sur une heuristique client. Ajouter un indicateur (ex. champ sur `GET /me` ou `GET /matches`) ?
5. 🟡 **Quota et génération échouée** (Flux 5) : une génération `failed` consomme-t-elle le quota 10/h–40/j ? Recommandation : non. À fixer dans 12.
6. 🟡 **Granularité du diff CV** (Flux 6) : accepter/refuser changement par changement suppose un format de `PATCH /generations/{id}` structuré par section — le contrat actuel (content jsonb libre) le permet mais ne le spécifie pas. À détailler dans `ai-output-schemas.json`.
7. 🟡 **Candidatures : unicité et transitions** (Flux 7) : pas de contrainte d'unicité (user, job_posting) ni de matrice de transitions de statut documentées. La spec UI suppose : doublon détecté côté client, toutes transitions autorisées sauf retour depuis `withdrawn` 🟡. À fixer côté back.
8. 🟡 **Fenêtre de rétractation** (Flux 8) : le soft delete de 30 j permettrait techniquement une annulation ; le MVP ne l'offre pas et l'e-mail de confirmation de suppression n'est pas spécifié dans 12. Trancher (l'e-mail est recommandé : preuve RGPD + protection contre suppression malveillante).
9. 🟡 **Focus initial de la modale de suppression** (Flux 8) : champ mot de passe vs bouton « Annuler » — à trancher en test d'accessibilité.
