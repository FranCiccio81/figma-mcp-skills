# 03 — Architecture de l'information

> Boussole — application web desktop-first responsive (D11 : Next.js App Router, UI FR au lancement, i18n prête D15).
> Statut : v1.0 — 2026-07-23. Références : `01-product-brief.md`, `12-api-contracts.md` / `openapi.yaml` (endpoints), `06-matching-specification.md`, `04-user-flows.md` (parcours utilisant les IDs SCR-xx définis ici).
> Les IDs **SCR-xx** sont stables et réutilisés dans 04 (parcours) et 05 (wireframes). 🟡 = hypothèse.

---

## 1. Arborescence complète

```
Boussole
├── Zone publique (non authentifié)
│   ├── SCR-01  Connexion
│   ├── SCR-02  Inscription (email + mot de passe + consentements)
│   ├── SCR-03  Mot de passe oublié — demande
│   └── SCR-04  Réinitialisation du mot de passe — confirmation
│
├── Onboarding (authentifié, profil non validé — séquence progressive, reprenable)
│   ├── SCR-05  Import du CV (upload + suivi du parsing)
│   ├── SCR-06  Validation du profil extrait (revue provenance/confiance)
│   └── SCR-07  Préférences de recherche (même écran que l'entrée « Préférences »)
│
├── Navigation principale (sidebar desktop / barre inférieure + menu mobile)
│   ├── Tableau de bord
│   │   └── SCR-10  Tableau de bord
│   ├── Offres
│   │   ├── SCR-20  Recherche & liste d'offres
│   │   ├── SCR-21  Détail d'une offre (+ panneau match)
│   │   │   ├── SCR-22  Panneau d'explication du score (déterministe + reformulation LLM)
│   │   │   └── SCR-74  Méthode de calcul (page pédagogique, aussi accessible depuis Paramètres)
│   │   └── SCR-23  Offres sauvegardées / masquées (onglets)
│   ├── Candidatures
│   │   ├── SCR-40  Suivi des candidatures (liste + regroupement par statut)
│   │   ├── SCR-41  Détail d'une candidature (statuts historisés, notes, documents liés)
│   │   └── SCR-42  Ajouter une candidature externe (formulaire)
│   ├── Profil
│   │   ├── SCR-50  Profil canonique (consultation + édition par section)
│   │   └── SCR-51  Réimporter un CV (réutilise SCR-05 en mode « mise à jour ») 
│   ├── Préférences
│   │   └── SCR-07  Préférences de recherche (écran unique, deux contextes d'entrée)
│   └── Paramètres
│       ├── SCR-70  Compte & sécurité (email, mot de passe, sessions)
│       ├── SCR-71  Confidentialité & données (export RGPD, consentements)
│       ├── SCR-72  Suppression du compte (sous-page + modale de confirmation)
│       ├── SCR-73  Sources des offres (transparence : liste, nature, fraîcheur)
│       └── SCR-74  Méthode de calcul du score (transparence de la méthode)
│
├── Surfaces transverses (modales / panneaux, invoquées depuis plusieurs écrans)
│   ├── SCR-30  Configurer une génération (type, ton, langue, longueur) + avertissement anti-invention
│   ├── SCR-31  Relecture & validation d'un document généré (diff, claims d'ancrage, édition)
│   └── SCR-32  Export d'un document validé (copie / PDF / DOCX)
│
└── Écrans système
    ├── SCR-90  Page introuvable (404 — aussi rendue pour toute ressource d'autrui, cf. 12 §5)
    ├── SCR-91  Erreur serveur / service indisponible (500/503, avec trace_id)
    └── SCR-92  Session expirée (retour SCR-01 avec conservation de l'URL cible)
```

Notes de structure :
- **SCR-07 est un écran unique** utilisé dans deux contextes (onboarding et navigation « Préférences ») — même formulaire, même endpoint `PUT /preferences`, seule la coquille change (stepper vs page).
- **SCR-30/31/32 sont des surfaces transverses** : invocables depuis SCR-21 (offre), SCR-41 (candidature) et SCR-50 (optimisation générale du CV, `cv_optimization` sans `job_id`).
- Les offres **masquées ne disparaissent jamais silencieusement** : elles vivent dans SCR-23 et restent restaurables (`DELETE /jobs/{id}/saved-state`).

---

## 2. Inventaire des écrans

Convention des états : **Vide** (aucune donnée) / **Chargement** (squelettes, jamais de spinner bloquant plein écran sauf auth) / **Erreur** (problem+json → message + `trace_id` + action de récupération) / **Succès** (nominal). Les états additionnels spécifiques sont nommés.

### Zone publique

#### SCR-01 — Connexion
- **Objectif** : ouvrir une session (cookie httpOnly, cf. 12 §1).
- **Contenu** : email, mot de passe, lien SCR-03, lien SCR-02, rappel valeur (« Vos données restent en Europe. Aucune candidature envoyée sans vous. »).
- **États** : Succès → redirection selon l'état d'onboarding (`GET /me`) ; Erreur identifiants (message générique, sans révéler l'existence du compte) ; Erreur 429 (rate limit : message + `Retry-After`).
- **API** : `POST /auth/login`, puis `GET /me`.

#### SCR-02 — Inscription
- **Objectif** : créer le compte avec consentements explicites (D09).
- **Contenu** : email, mot de passe (règles affichées), cases de consentement distinctes (CGU/traitement des données obligatoire ; contenu échantillonné debug 30 j optionnel, cf. 11 §3 🟡), mention hébergement UE.
- **États** : Succès → connexion automatique → SCR-05 ; Erreur de validation (`errors[]` par champ) ; Email déjà utilisé (message générique anti-énumération 🟡).
- **API** : `POST /auth/register`, `POST /auth/login`.

#### SCR-03 / SCR-04 — Réinitialisation du mot de passe
- **Objectif** : demande (03) puis confirmation par jeton (04).
- **Contenu** : 03 : champ email + confirmation neutre (« Si un compte existe, un e-mail a été envoyé. ») ; 04 : nouveau mot de passe ×2.
- **États** : 04 — Jeton invalide/expiré → message + renvoi vers SCR-03 ; Succès → SCR-01.
- **API** : `POST /auth/password-reset/request`, `POST /auth/password-reset/confirm`.

### Onboarding

#### SCR-05 — Import du CV
- **Objectif** : uploader le CV (PDF/DOCX ≤ 10 Mo) et suivre le parsing asynchrone.
- **Contenu** : zone de dépôt + bouton fichier ; contraintes affichées (formats, taille, 5 uploads/jour) ; pendant le parsing : étapes (« Lecture du document → Extraction des informations → Préparation de votre profil ») ; option « Passer et saisir manuellement » 🟡 (crée un profil vierge — voir Questions ouvertes Q3).
- **États** : Vide (dropzone) ; Chargement = **Parsing en cours** (`status=uploaded|parsing`, polling 2 s ×1,5, annonce ARIA) ; **Échec de parsing** (`status=failed` + `error_code` ∈ `unreadable` / `image_only_pdf` / `too_large` / `unsupported_format` / `extraction_failed` — message dédié par code, cf. 04 §Flux 1) ; **Parsing partiel** (`status=parsed` + `extraction_warnings[]` → bandeau en SCR-06) ; Erreur 429 (quota 5/j) ; Succès (`parsed`) → SCR-06.
- **API** : `POST /cv-documents` (202), `GET /cv-documents/{id}` (polling).

#### SCR-06 — Validation du profil extrait
- **Objectif** : relire, corriger et valider le profil (promotion `cv_extraction` → `user_confirmed`, cf. 11 §2). Cœur de H2.
- **Contenu** : sections Identité pro (headline, résumé, séniorité) / Expériences / Formations / Compétences / Langues ; **chaque champ extrait porte son badge de provenance et de confiance** (« Extrait du CV — confiance 62 % ») ; champs à confiance < 0,5 mis en avant en tête (« À vérifier ») ; compteur des prérequis de validation (≥ 3 compétences, ≥ 1 expérience ou formation) ; bouton « Valider mon profil ».
- **États** : Chargement ; **Prérequis non remplis** (bouton désactivé + explication) ; Erreur de sauvegarde par champ (inline) ; Erreur de validation 422 ; Succès → SCR-07 (onboarding) ou SCR-50 (réimport).
- **API** : `GET /profile`, `PATCH /profile`, `POST/PATCH/DELETE /profile/experiences[/{id}]` (idem educations, skills, languages), `POST /profile/validate`.

#### SCR-07 — Préférences de recherche
- **Objectif** : définir les critères qui alimentent filtres, matching et bloquants (feature D).
- **Contenu** : métiers cibles (intitulés) ; localisations + rayon (défaut 30 km 🟡) ; télétravail (`required`/`preferred`/`indifferent`/`onsite_preferred`) ; types de contrat + case « strict » (déclenche le bloquant `contract_excluded`) ; fourchette de salaire + « minimum strict » optionnel (bloquant `salary_below_minimum`) ; langues + niveau CECRL ; secteurs préférés et **exclus** (bloquant `sector_excluded`) ; entreprises cibles, mots-clés. Chaque option « stricte » affiche sa conséquence (« Les offres incompatibles seront signalées comme bloquées, jamais masquées »).
- **États** : Vide (valeurs par défaut proposées, rien de pré-coché en strict) ; Chargement ; Erreur de validation 422 par champ ; Succès (enregistré → re-scoring asynchrone lancé, bandeau « Vos scores sont en cours de mise à jour ») .
- **API** : `GET /preferences`, `PUT /preferences` (remplacement complet).

### Tableau de bord

#### SCR-10 — Tableau de bord
- **Objectif** : point d'entrée quotidien — reprendre là où on en était.
- **Contenu** : (a) **checklist d'onboarding** tant qu'incomplète (importer CV → valider profil → définir préférences), chaque item lien direct ; (b) meilleures offres récentes (top `GET /matches`, score + confiance + badges) ; (c) candidatures à relancer (statut `applied` sans événement récent 🟡 seuil J+10) ; (d) rappel transparence : nombre de sources actives + lien SCR-73.
- **États** : **Vide-onboarding** (profil non validé : checklist plein écran, pas de scores) ; **Vide-offres** (profil validé, 0 match : message + lien préférences, cf. 04 Flux 3 cas « 0 offre ») ; Chargement (squelettes par bloc, indépendants) ; Erreur par bloc (le reste de la page vit) ; Succès.
- **API** : `GET /me`, `GET /matches?limit=5`, `GET /applications?limit=5`, `GET /sources`.

### Offres

#### SCR-20 — Recherche & liste d'offres
- **Objectif** : chercher, filtrer, trier ; décider en quelques secondes quelles offres ouvrir (JTBD-04).
- **Contenu** : champ `q` ; filtres = localisation (`location_id` ou lat/lon+rayon), `remote[]`, `contract[]`, `seniority[]`, `language`, `salary_min`, `posted_since`, `source[]`, interrupteur « Afficher les offres bloquées » (`include_blocked`, **défaut activé** — badgées, jamais retirées silencieusement), tri `match` (défaut si profil validé) / `date` / `relevance`. Cartes d'offre : titre, entreprise, lieu, contrat, remote, **score + confiance côte à côte**, badge bloquant le cas échéant, badge « salaire non communiqué » le cas échéant, source, actions sauvegarder/masquer.
- **États** : Chargement (squelettes) ; **0 résultat** (suggestions : élargir rayon, retirer filtres — cf. 04 Flux 3) ; **Profil non validé** (tri `match` indisponible, bandeau explicatif + lien SCR-06, tri `relevance` par défaut) ; **Score gris `low_data`** (état d'une carte, pas de l'écran) ; Erreur 429 recherche (30/min) ; Erreur serveur ; Succès (pagination par curseur, « Charger plus »).
- **API** : `GET /jobs` (paramètres cf. 12 §3), `PUT /jobs/{id}/saved-state`, `DELETE /jobs/{id}/saved-state`.

#### SCR-21 — Détail d'une offre
- **Objectif** : lire l'offre complète et son évaluation ; déclencher génération ou candidature.
- **Contenu** : en-tête (titre, entreprise, lieu(x), contrat, remote, date, **source(s) + lien(s) d'origine obligatoires** — une ligne par `job_source`) ; **panneau match** : score /100 + indice de confiance /100 (jamais fusionnés, D03), liste `blocking_criteria[]` en premier, `unknown_dimensions[]` (« non précisé »), détail `dimensions[]` (sous-score, poids, valeurs comparées) ; bouton « Pourquoi ce score ? » → SCR-22 ; corps de l'offre ; actions : Sauvegarder / Masquer / « Générer une candidature » (SCR-30) / « J'ai postulé » (crée une candidature, Flux 7) ; lien « Comment ce score est calculé » → SCR-74.
- **États** : Chargement ; **Non scorée** (calcul synchrone < 50 ms — squelette bref sur le panneau match uniquement) ; **`low_data=true`** (score grisé + bandeau « données insuffisantes ») ; **Offre expirée** (bandeau `job_expired`, actions de génération désactivées 🟡 cf. Questions ouvertes, lien d'origine conservé) ; Erreur 404 (offre supprimée → SCR-90) ; Succès.
- **API** : `GET /jobs/{id}`, `GET /jobs/{id}/match`, `PUT/DELETE /jobs/{id}/saved-state`.

#### SCR-22 — Panneau d'explication du score
- **Objectif** : explication à la demande (H1) — couche 1 déterministe toujours affichée, couche 2 LLM optionnelle (D14).
- **Contenu** : bloquants d'abord (règle déclenchée en toutes lettres) ; puis forces (`s ≥ 0,8`, `w ≥ 6`) ; lacunes (`s ≤ 0,4`, chiffrées) ; inconnues (`k=0`, libellé par côté manquant : « non précisé dans l'offre » / « absent de votre profil ») ; bouton « Reformuler en langage clair » → texte LLM (cache par version) avec mention « Reformulation générée à partir des faits ci-dessus ».
- **États** : Succès-déterministe (immédiat, depuis `GET /jobs/{id}/match` déjà chargé) ; Chargement-reformulation ; **Reformulation indisponible** (échec LLM : les faits déterministes restent — dégradation douce) ; Erreur 429 (quota LLM).
- **API** : `POST /jobs/{id}/explanation`.

#### SCR-23 — Offres sauvegardées / masquées
- **Objectif** : retrouver ses sauvegardes ; restaurer des offres masquées (rien n'est jamais perdu).
- **Contenu** : onglets « Sauvegardées » / « Masquées » ; mêmes cartes que SCR-20 ; action « Restaurer » sur les masquées.
- **États** : Vide par onglet (message dédié) ; Chargement ; Erreur ; Succès.
- **API** : `GET /jobs?...` avec état sauvegardé 🟡 (paramètre exact de filtre saved à confirmer dans openapi — cf. Questions ouvertes Q2), `include_hidden=true` pour l'onglet Masquées ; `DELETE /jobs/{id}/saved-state`.

### Surfaces de génération (transverses)

#### SCR-30 — Configurer une génération
- **Objectif** : lancer une génération ancrée (features L, M, N, O) avec consentement éclairé.
- **Contenu** : type (`email` / `cover_letter` / `cv_variant` / `cv_optimization` — les trois premiers exigent un `job_id`, `cv_optimization` non) ; options : ton (`sobre`/`chaleureux`/`direct`), langue (`fr`/`en` — proposée selon la langue de l'offre), longueur (`court`/`standard`) ; **avertissement anti-invention systématique** (microcopie exacte en 04 §M4) ; compteur de quota restant (10/h, 40/j).
- **États** : Succès → 202 + bascule sur SCR-31 en état « Génération en cours » ; **Profil non validé** (bouton désactivé, erreur `profile_not_validated` sinon) ; **Quota atteint** (429 : message + `Retry-After`) ; **Offre expirée** (`job_expired` 🟡) ; Erreur.
- **API** : `POST /generations` (avec `Idempotency-Key`).

#### SCR-31 — Relecture & validation d'un document généré
- **Objectif** : le passage obligé D10 — relire, éditer, valider. Aucun export sans validation.
- **Contenu** : selon le type — lettre/e-mail : texte + panneau « Affirmations et leurs sources » (chaque `claim` liée à son `profile_ref`, cliquable vers la section du profil) ; `cv_variant`/`cv_optimization` : **diff côte à côte** canonique → variante (ajouts/retraits/reformulations par section) ; résultat du contrôle d'ancrage (`anchoring_check`) ; édition manuelle (PATCH) ; métadonnées (basé sur profil v4, `prompt_version`) ; bouton « J'ai relu, je valide » puis « Exporter » (SCR-32).
- **États** : **Génération en cours** (`pending`, polling, annonce ARIA) ; **Brouillon** (`draft`) ; **Échec de génération** (`failed` : message + « Réessayer » — nouvelle `Idempotency-Key`) ; **Ancrage douteux** (`anchoring_check.status=failed` : les `unanchored_claims` surlignées, validation possible uniquement après édition ou confirmation explicite 🟡 cf. Q5) ; **Validé** (`validated`) ; **Exporté** (`exported`, lecture seule) ; Erreur.
- **API** : `GET /generations/{id}` (polling), `PATCH /generations/{id}`, `POST /generations/{id}/validate`.

#### SCR-32 — Export d'un document validé
- **Objectif** : sortir le contenu validé (copie, PDF, DOCX). Refusé si non validé (409 `generation_not_validated`).
- **Contenu** : choix du format (`text`/`pdf`/`docx`) ; rappel « Boussole n'envoie rien : c'est vous qui transmettez ce document » ; proposition « Créer le suivi de candidature » → SCR-42 pré-rempli.
- **États** : Succès (copie faite / lien signé de téléchargement) ; Erreur 409 non validé (retour SCR-31) ; Erreur.
- **API** : `POST /generations/{id}/export`.

### Candidatures

#### SCR-40 — Suivi des candidatures
- **Objectif** : vue d'ensemble par statut (feature P — saisie manuelle, H5).
- **Contenu** : regroupement par statut (`draft`, `to_apply`, `applied`, `interviewing`, `offer`, `rejected`, `withdrawn`) en colonnes (desktop) / liste segmentée (mobile) ; carte : poste, entreprise, date du dernier événement, source (offre interne avec lien, ou externe) ; filtre par statut ; bouton « Ajouter une candidature » → SCR-42.
- **États** : Vide (explication + deux portes d'entrée : depuis une offre, ou ajout externe) ; Chargement ; Erreur ; Succès.
- **API** : `GET /applications` (+ `?status=`), `POST /applications`.

#### SCR-41 — Détail d'une candidature
- **Objectif** : gérer une candidature : statut, notes, historique, documents liés.
- **Contenu** : en-tête (poste, entreprise, lien vers SCR-21 si offre interne — avec badge « offre expirée » le cas échéant — ou `external_url`) ; **frise des statuts historisés** (`application_events`) ; changement de statut + note (≤ 1000 car.) ; notes libres ; documents générés liés (lettre, e-mail, CV adapté) avec leur statut ; actions : générer un document (SCR-30 avec `application_id`), supprimer la candidature (confirmation).
- **États** : Chargement ; Erreur 404 ; **Transition invalide** (422 sur `POST .../status` : message) ; Succès.
- **API** : `GET /applications/{id}`, `PATCH /applications/{id}`, `POST /applications/{id}/status`, `DELETE /applications/{id}`.

#### SCR-42 — Ajouter une candidature externe
- **Objectif** : suivre aussi les candidatures hors plateforme (contrainte du modèle : `job_posting_id` **ou** `external_title` + `external_company`, cf. 11 §5).
- **Contenu** : intitulé, entreprise, URL (optionnelle), notes, statut initial (`to_apply` ou `applied`).
- **États** : Erreur de validation 422 ; Succès → SCR-41.
- **API** : `POST /applications` (avec `Idempotency-Key`).

### Profil

#### SCR-50 — Profil canonique
- **Objectif** : consulter et maintenir le profil après l'onboarding ; même composants d'édition que SCR-06.
- **Contenu** : mêmes sections que SCR-06, badges de provenance conservés (`user_confirmed` / `user_input` / `cv_extraction` restant) ; version du profil affichée ; encart « Optimiser mon CV » (génération `cv_optimization` → SCR-30 sans `job_id`, feature N) ; lien « Réimporter un CV » → SCR-51/SCR-05.
- **États** : Chargement ; **Profil jamais validé** (bandeau + CTA SCR-06) ; **Modifié depuis la dernière validation** 🟡 (les nouveaux champs `user_input` sont valides sans re-validation ; bandeau « vos scores se recalculent ») ; Erreur ; Succès.
- **API** : `GET /profile`, `PATCH /profile`, CRUD sous-ressources, `POST /profile/validate` (si re-validation requise).

#### SCR-51 — Réimporter un CV
- **Objectif** : mettre à jour le profil depuis un nouveau CV sans écraser silencieusement les données confirmées.
- **Contenu** : SCR-05 en mode « mise à jour » + écran de fusion 🟡 (les champs `user_confirmed` existants ne sont jamais écrasés sans revue — cf. Questions ouvertes Q4).
- **API** : `POST /cv-documents`, `GET /cv-documents/{id}`, puis revue type SCR-06.

### Paramètres

#### SCR-70 — Compte & sécurité
- **Objectif** : email, mot de passe, déconnexion.
- **Contenu** : email (lecture 🟡 — pas d'endpoint de changement d'email dans 12), changement de mot de passe (via flux reset), « Se déconnecter ».
- **API** : `GET /me`, `POST /auth/logout`, `POST /auth/password-reset/request`.

#### SCR-71 — Confidentialité & données
- **Objectif** : droits RGPD — export, consentements (feature Q, D09).
- **Contenu** : « Exporter mes données » (archive JSON, lien signé 7 j, quota 2/j) avec suivi d'état ; consentements modifiables ; liens registre/politique ; entrée « Supprimer mon compte » → SCR-72.
- **États** : **Export en préparation** (`pending`, polling) ; **Export prêt** (`ready` + lien) ; **Export expiré** (`expired` → relancer) ; Erreur 429 (2/j) ; Succès.
- **API** : `POST /privacy/export`, `GET /privacy/exports/{id}`.

#### SCR-72 — Suppression du compte
- **Objectif** : suppression conforme (soft delete immédiat, purge ≤ 30 j) avec confirmation par mot de passe.
- **Contenu** : explication des conséquences + proposition d'export préalable ; modale de confirmation (microcopie exacte en 04 §M5) ; champ mot de passe.
- **États** : **Confirmation** (modale) ; Erreur mot de passe (401/422) ; Succès → déconnexion → SCR-01 avec message de confirmation.
- **API** : `DELETE /account`.

#### SCR-73 — Sources des offres
- **Objectif** : transparence (contrainte : « le produit affiche le nombre et la nature de ses sources », métrique conformité 100 % des offres avec source + lien).
- **Contenu** : liste des sources actives : nom, nature (`public_api` / `ats_feed` / `partner`), dernière synchronisation ; mention explicite « Boussole n'agrège pas tout le web ».
- **API** : `GET /sources`.

#### SCR-74 — Méthode de calcul du score
- **Objectif** : « méthode publiée dans le produit » (différenciateur, brief §2). Version pédagogique de 06 : dimensions et poids, score vs confiance, bloquants, règle < 40 % de poids connu, `scoring_version` courante.
- **Contenu** : statique versionné (synchronisé avec `scoring-config.json`) ; aucun appel LLM.
- **API** : aucune (contenu embarqué) 🟡.

### Écrans système

- **SCR-90 — Introuvable (404)** : aussi affiché pour toute ressource appartenant à autrui (anti-énumération, 12 §5). Lien retour Tableau de bord.
- **SCR-91 — Erreur serveur (500/503)** : message + `trace_id` copiable + « Réessayer ».
- **SCR-92 — Session expirée (401)** : redirection SCR-01 avec conservation de l'URL demandée et message.

---

## 3. Modèle de navigation

### Desktop (≥ 1024 px)
- **Sidebar fixe gauche** : Tableau de bord / Offres / Candidatures / Profil / Préférences / Paramètres + indicateur d'onboarding (pastille sur les étapes incomplètes). Item actif marqué (`aria-current="page"`).
- **Zone de contenu** : liste ↔ détail. Sur SCR-20 → SCR-21 : navigation vers une page dédiée (URL propre, partageable en interne, back du navigateur fiable) ; le panneau d'explication SCR-22 est un panneau latéral (non-modal, fermable à Échap).
- **Modales** réservées aux confirmations destructrices (SCR-72, suppression candidature) et à SCR-30 ; SCR-31 est une **page pleine** (la relecture D10 mérite l'espace, pas une modale).

### Responsive (< 1024 px)
- Sidebar → **barre inférieure 5 entrées** (Tableau de bord, Offres, Candidatures, Profil, « Plus » regroupant Préférences + Paramètres) ; cibles tactiles ≥ 44 px.
- SCR-22 devient une feuille montante (bottom sheet) plein écran ; les colonnes de SCR-40 deviennent une liste segmentée par statut.
- Aucun contenu sacrifié : mêmes écrans, mêmes états (desktop-first mais intégralement utilisable au doigt — cf. question ouverte P3 dans 02).

### Onboarding progressif
- **Séquence** : SCR-02 → SCR-05 (import) → SCR-06 (validation) → SCR-07 (préférences) → SCR-10. Chaque étape est **quittable et reprenable** : l'état vient de `GET /me` (état d'onboarding) — jamais d'état local seul.
- **Gating fonctionnel, pas d'écran verrouillé** : avant validation du profil, l'app entière est navigable mais (a) tri `match` indisponible sur SCR-20 (fallback `relevance` + bandeau), (b) génération refusée (`profile_not_validated`), (c) SCR-10 affiche la checklist. On peut chercher des offres **avant** d'avoir validé son profil — la valeur du matching sert d'incitation à finir l'onboarding (métrique activation ≥ 60 %).
- **Divulgation progressive des préférences** : en onboarding, SCR-07 ne rend obligatoires que métiers cibles + localisation/remote + contrat 🟡 ; salaire, langues, secteurs, préférences fines sont repliés (« Affiner plus tard ») — réduire l'abandon, tout reste éditable.

### Règles transverses
- **Opérations asynchrones** (parsing, génération, export RGPD) : l'UI reflète l'état de la ressource (202 + polling 2 s ×1,5) ; jamais d'écran bloquant — l'utilisateur peut naviguer et revenir (le Tableau de bord ré-affiche les tâches en cours 🟡).
- **Erreurs** : mapping systématique problem+json → message français (`Accept-Language: fr`) + action de récupération ; `trace_id` visible dans le détail technique repliable.
- **429** : tous les écrans à quota affichent le message dédié + temps d'attente (`Retry-After`) ; les compteurs de quota génération sont affichés **avant** l'action (SCR-30).

---

## 4. Matrice écrans × endpoints (récapitulatif)

| Endpoint (12 §2) | Écrans consommateurs |
|---|---|
| `POST /auth/register` / `login` / `logout` | SCR-02 / SCR-01 / SCR-70 |
| `POST /auth/password-reset/request` / `confirm` | SCR-03, SCR-70 / SCR-04 |
| `GET /me` | Coquille de l'app (routage onboarding), SCR-10, SCR-70 |
| `POST /cv-documents`, `GET /cv-documents/{id}` | SCR-05, SCR-51 |
| `GET /profile`, `PATCH /profile`, CRUD sous-ressources | SCR-06, SCR-50 |
| `POST /profile/validate` | SCR-06 (SCR-50 si re-validation) |
| `GET /preferences`, `PUT /preferences` | SCR-07 |
| `GET /jobs` | SCR-20, SCR-23 |
| `GET /jobs/{id}` | SCR-21 |
| `GET /jobs/{id}/match` | SCR-21 (alimente SCR-22 couche 1), cartes SCR-20 via `GET /matches` |
| `POST /jobs/{id}/explanation` | SCR-22 |
| `PUT`/`DELETE /jobs/{id}/saved-state` | SCR-20, SCR-21, SCR-23 |
| `GET /matches` | SCR-10, SCR-20 (tri match) |
| `POST /generations` | SCR-30 |
| `GET /generations/{id}`, `PATCH`, `POST .../validate`, `POST .../export` | SCR-31, SCR-32 |
| `GET`/`POST /applications`, `GET`/`PATCH`/`DELETE /applications/{id}` | SCR-40, SCR-41, SCR-42 |
| `POST /applications/{id}/status` | SCR-41 |
| `POST /privacy/export`, `GET /privacy/exports/{id}` | SCR-71 |
| `DELETE /account` | SCR-72 |
| `GET /sources` | SCR-73, SCR-10 |

Tous les endpoints utilisateur de 12 §2 sont couverts par au moins un écran (hors `/healthz`, `/readyz`, internes).

---

## 5. Questions ouvertes

1. 🟡 **Liste des documents générés** : 12 n'expose que `GET /generations/{id}` — aucun endpoint de **liste**. Sans lui, impossible de proposer une « bibliothèque de documents » (retrouver une lettre passée hors du contexte candidature). Décider : ajouter `GET /generations` (recommandé), ou n'accéder aux documents que via SCR-41 (candidature liée) — auquel cas un document généré sans candidature devient inaccessible après navigation.
2. 🟡 **Filtre « sauvegardées » dans `GET /jobs`** : 12 §3 documente `include_hidden` mais pas de paramètre pour filtrer les seules offres sauvegardées (SCR-23 onglet 1). À préciser dans `openapi.yaml` (ex. `saved_state=saved`).
3. 🟡 **Onboarding sans CV** : « Passer et saisir manuellement » est-il permis au MVP ? Le brief impose ≥ 3 compétences et ≥ 1 expérience/formation pour valider, ce qui reste satisfiable à la main, mais la métrique d'activation (« importent un CV **et** valident ») suggère que l'import est le chemin nominal. Trancher.
4. 🟡 **Réimport de CV (SCR-51)** : politique de fusion non spécifiée dans 05/11/12 — un nouveau parsing peut-il proposer d'écraser des champs `user_confirmed` ? Hypothèse retenue : jamais d'écrasement automatique, revue champ par champ. À valider côté back (nouvel `extraction_run` vs nouveau profil versionné).
5. 🟡 **`anchoring_check.status=failed`** : le contrat 12 montre le cas `passed`. Si `failed`, la validation humaine doit-elle être bloquée tant que les `unanchored_claims` ne sont pas éditées, ou permise avec confirmation renforcée ? Hypothèse UI : blocage doux (édition ou suppression des claims requises) — cohérent avec « 0 invention » (métrique §8 du brief).
6. 🟡 **Offre expirée** : le code d'erreur `job_expired` existe (12 §1) mais la liste des actions concernées n'est pas spécifiée. Hypothèse : génération refusée sur offre expirée ; sauvegarde et suivi de candidature autorisés (une candidature déjà envoyée reste à suivre). À confirmer.
7. 🟡 **Changement d'email** : aucun endpoint. SCR-70 l'affiche en lecture seule au MVP — confirmer que c'est un choix et non un oubli.
8. 🟡 **Tâches en cours sur le Tableau de bord** : afficher les générations/parsings `pending` sur SCR-10 nécessite un endpoint de liste (cf. Q1) ou un état local persisté — à trancher.
