# 09 — Sécurité & Vie privée

> Périmètre : MVP Boussole (phases 1–10). S'appuie sur D08 (couche IA), D09 (privacy by design UE), D10 (human-in-the-loop), sur le modèle de données (11 §3 rétention), les contrats API (12 §1 et §5), la spécification matching (06 §3) et la protection prompt injection (08). Les hypothèses non actées sont marquées 🟡.
> Rien dans ce document ne constitue un avis juridique ; les points de qualification légale sont explicitement renvoyés à la revue juridique (17-open-questions).

---

## 1. Modèle de menaces (STRIDE condensé)

### 1.1 Acteurs

| Acteur | Capacité | Motivation type |
|---|---|---|
| Attaquant externe non authentifié | trafic réseau vers l'edge, création de comptes | vol de données de CV (revente), credential stuffing |
| Utilisateur authentifié malveillant | API complète dans son scope | énumération d'autrui, abus de quotas LLM, contournement des validations |
| Auteur de contenu tiers malveillant | publie une **offre piégée** sur une source légitime, ou soumet un **CV piégé** | prompt injection, XSS stocké, empoisonnement de la déduplication |
| Insider / prestataire | accès infra ou base | exfiltration |
| Sous-traitant compromis (LLM, e-mail, géocodage) | reçoit des données minimisées | fuite en aval |

### 1.2 Surfaces d'attaque

1. **Upload CV** (PDF/DOCX) : fichiers hostiles pour les parseurs, malware, bombes de décompression (DOCX = zip), contenu de prompt injection.
2. **Contenus d'offres externes** : texte non fiable ingéré automatiquement — prompt injection vers les tâches d'extraction, HTML/JS injecté (XSS stocké si rendu sans échappement), données fausses pour polluer dédup et matching.
3. **Prompts / sorties LLM** : injection, exfiltration de données d'autres contextes, sorties non conformes au schéma.
4. **API `/api/v1`** : authentification, IDOR, énumération, abus de rate limit, CSRF.
5. **Sessions et cookies** : vol, fixation, rejeu.
6. **Exports et liens signés** (export RGPD 7 j, exports PDF/DOCX) : fuite de lien.
7. **Egress des workers** (connecteurs, géocodage, LLM) : SSRF, exfiltration.

### 1.3 Grille STRIDE — menaces prioritaires et contrôles

| STRIDE | Menace prioritaire | Contrôles |
|---|---|---|
| **S**poofing | Credential stuffing / brute force sur `/auth/login` | argon2id, rate limit par IP et par compte, backoff progressif après 5 échecs, messages d'erreur neutres, alerte sur pics d'échecs ; MFA TOTP post-MVP 🟡 |
| | Vol/fixation de session | cookie `httpOnly; Secure; SameSite=Lax`, ID de session 128 bits CSPRNG, **rotation de l'ID à la connexion**, invalidation à logout et à tout changement de mot de passe |
| **T**ampering | Altération du scoring (`scoring-config.json`) | config versionnée en repo, modifiable uniquement par PR revue + run d'évaluation CI obligatoire (06 §5) ; `scoring_version` estampillé sur chaque résultat |
| | Injection SQL / manipulation de requêtes | requêtes paramétrées exclusivement (SQLAlchemy), aucun SQL concaténé, validation Pydantic en entrée |
| | Données d'offres empoisonnées | validation de schéma par connecteur, provenance conservée par source (`job_sources`), seuils de confiance d'extraction (06 §1 : conf < 0,5 → inconnu, bloquant jamais inféré sous 0,7) |
| **R**épudiation | Contestation d'actions (suppression, export, validation d'un contenu généré) | `audit_log` en append-only (§5.7), `trace_id` sur toute requête, journal `ai_calls` (prompt_version, modèle, tokens) |
| **I**nformation disclosure | IDOR / énumération de ressources | scoping systématique par `user_id`, réponse **404** sur ressource d'autrui (12 §5), UUID non séquentiels, aucune donnée personnelle en URL |
| | Fuite via prompts LLM | minimisation D09 : jamais nom/email/téléphone dans les prompts de matching/génération ; l'explication ne reçoit que les `explanation_facts` (D14), jamais l'offre brute |
| | Fuite S3 / backups | buckets privés, liens signés courts (7 j exports, minutes pour téléchargements 🟡), chiffrement SSE-KMS, backups chiffrés |
| **D**enial of service | Épuisement des quotas LLM (coût = déni économique, R7) | rate limits 12 §1 (générations 10/h et 40/j, upload 5/j), budget LLM journalier plafonné avec alerte et coupure douce 🟡 |
| | Fichiers hostiles (zip bomb, PDF pathologique) | taille ≤ 10 Mo, limites d'extraction DOCX (ratio de décompression ≤ 100, ≤ 1000 entrées 🟡), timeout de parsing, worker isolé (§5.3) |
| | Saturation Redis / files | politiques mémoire séparées broker vs cache (10 §7), alertes de lag |
| **E**levation of privilege | Compromission d'un worker → pivot | conteneurs non-root, réseau privé, **egress en allowlist** (sources approuvées, LLM providers, géocodage, e-mail) — limite SSRF et exfiltration |
| | Accès admin | aucun rôle admin dans l'application publique ; back-office/runbooks via accès infra nominatif avec MFA 🟡 |

### 1.4 Top 5 des menaces à traiter en priorité

1. **Prompt injection via offres et CV** (R5) — surface ouverte au public par construction (n'importe quel employeur peut publier une offre ingérée). Contrôles : §5.4.
2. **Exfiltration massive de profils** (base de CV = cible de forte valeur). Contrôles : réseau privé, moindre privilège DB par module (10 §2), chiffrement, alerte sur volumes de lecture anormaux 🟡.
3. **Compromission de comptes** (les CV contiennent l'historique professionnel complet). Contrôles : §5.1.
4. **XSS stocké depuis une description d'offre**. Contrôles : échappement systématique côté React (jamais de `dangerouslySetInnerHTML` sur du contenu de source), sanitisation à l'ingestion (texte brut uniquement, HTML supprimé), CSP stricte.
5. **Non-purge effective** (risque de conformité) : purge J+30 testée automatiquement, métrique « deletion_requests en retard » avec alerte critique (10 §6).

---

## 2. RGPD opérationnel

### 2.1 Rôles

- **Boussole = responsable de traitement** pour l'ensemble des traitements ci-dessous.
- Sous-traitants (art. 28) : hébergeur cloud UE, providers LLM, service e-mail transactionnel, géocodage — voir §2.6.
- Point de contact protection des données : DPO externe mutualisé 🟡 (désignation obligatoire ou volontaire — à trancher en revue juridique).

### 2.2 Bases légales par traitement

Cohérent avec la table de rétention de 11 §3 (les durées ci-dessous en sont la reprise, pas une variante).

| Traitement | Base légale (art. 6 §1) | Données | Durée |
|---|---|---|---|
| Création et gestion de compte, authentification | b — exécution du contrat | email, mot de passe haché, consentements, sessions | vie du compte ; purge J+30 après suppression ; sessions TTL 30 j glissants |
| Import et parsing du CV | b — contrat | fichier CV, texte extrait, `extraction_runs` | vie du compte ; purge J+30 |
| Profil structuré (provenance, confiance) | b — contrat | expériences, formations, compétences, langues | vie du compte ; purge J+30 |
| Préférences de recherche | b — contrat | métiers, lieux, salaire, mobilité, exclusions | vie du compte ; purge J+30 |
| Agrégation d'offres publiques | f — intérêt légitime (fournir le service ; données d'employeurs publiées, pas de données candidat) | offres, sources, liens d'origine | 12 mois après expiration, puis archivage/suppression |
| Matching et explications | b — contrat | `match_results`, `match_explanations` (dérivés du profil) | purgés avec le compte |
| Génération de contenus (lettres, e-mails, CV adaptés) | b — contrat | `generated_documents`, ancrage sur version de profil | vie du compte ; purge J+30 |
| Suivi de candidatures | b — contrat | `applications`, `application_events` | vie du compte ; purge J+30 |
| Journal `ai_calls` (métadonnées : modèle, tokens, latence, prompt_version — **sans contenu**) | f — intérêt légitime (maîtrise qualité/coûts/sécurité) | métadonnées techniques | 13 mois ; anonymisé à la suppression du compte |
| Échantillonnage de contenus de prompts pour debug | **a — consentement** (opt-in explicite, révocable) | extraits de prompts/sorties | 30 j max |
| `audit_log` sécurité | f — intérêt légitime (sécurité, traçabilité) | événements d'audit sans contenu sensible (§5.7) | 13 mois ; anonymisé à la suppression |
| E-mails transactionnels (vérification, reset) | b — contrat | email | durée d'envoi + logs courts du prestataire |
| Digest e-mail d'offres (fin de MVP, optionnel) | a — consentement | email, résumé de matches | jusqu'au retrait du consentement |

**Catégories particulières (art. 9)** : aucune collecte recherchée. La liste d'exclusion (§4) empêche l'extraction d'attributs sensibles vers le profil structuré. Le **fichier CV brut** peut néanmoins en contenir incidemment (photo, mentions spontanées) : il est stocké chiffré, n'est jamais indexé ni utilisé par le moteur, n'est transmis au LLM que pour la tâche d'extraction (qui a interdiction structurelle d'en produire), et est purgé à J+30. Cette analyse (donnée incidente non traitée) est à valider dans la DPIA 🟡.

**Art. 22 (décision entièrement automatisée)** : position de travail 🟡 — le score est une aide à la décision destinée au candidat lui-même, sans effet juridique à son égard ni décision de tiers ; la validation humaine est obligatoire pour tout contenu (D10). Cette lecture est documentée dans la DPIA, **pas tranchée ici** — revue juridique requise.

### 2.3 Droits des personnes

| Droit | Mécanisme | Détails |
|---|---|---|
| Accès + portabilité (art. 15, 20) | `POST /privacy/export` → `GET /privacy/exports/{id}` | archive JSON complète (profil, préférences, candidatures, contenus générés, consentements), lien signé 7 j, limité à 2/j, `Idempotency-Key` |
| Effacement (art. 17) | `DELETE /account` (confirmation par mot de passe) | soft delete immédiat (compte inaccessible, sessions invalidées) ; **purge physique ≤ 30 j** de toutes les lignes liées et objets S3 ; `ai_calls`/`audit_log` anonymisés (user_id → NULL, `subject_key` haché irréversible) ; **backups purgés au cycle** : rétention backups ≤ 30 j (10 §8), donc toute donnée supprimée disparaît aussi des backups sous 30 j après la purge ; test automatisé de suppression effective (métrique de conformité, 01 §8) |
| Rectification (art. 16) | édition du profil et des préférences (`PATCH /profile`, CRUD expériences/compétences, `PUT /preferences`) | la provenance par champ (D05) trace ce qui a été corrigé |
| Opposition / limitation (art. 18, 21) | canal support/DPO, traitement manuel au MVP 🟡 | délai de réponse ≤ 1 mois |
| Retrait de consentement | table `consents` + UI paramètres | même simplicité que l'octroi (échantillonnage debug, digest) |

### 2.4 Registre des traitements (art. 30)

Tenu dès le MVP, une fiche par ligne du tableau §2.2 : finalité, base légale, catégories de données et de personnes, destinataires (sous-traitants), durées, transferts éventuels, mesures de sécurité. Revue **trimestrielle**, alignée sur la revue du registre des sources (D04) ; mise à jour obligatoire avant activation de tout nouveau connecteur, provider ou traitement.

### 2.5 DPIA (art. 35)

**Déclencheurs** — au regard des critères CNIL/EDPB, Boussole en cumule au moins trois : (1) évaluation/scoring de personnes (matching), (2) données de personnes en situation de vulnérabilité relative (demandeurs d'emploi), (3) croisement de jeux de données (profil × offres × préférences), (4) traitement à grande échelle visé. → **DPIA requise avant lancement** (déjà actée en D09).

**Plan** :
1. Description systématique des traitements (réutilise 01, 06, 08, 11, ce document).
2. Nécessité et proportionnalité (minimisation LLM, rétentions, provenance).
3. Analyse de risques pour les personnes (les 5 menaces de §1.4 + biais §4 + art. 22).
4. Mesures (ce document) et risques résiduels.
5. Validation par la revue juridique ; avis CNIL sollicité seulement si risque résiduel élevé non mitigé.
6. Révision à chaque changement significatif : nouveau provider, nouvelle source, nouvelle finalité, changement de positionnement AI Act.

### 2.6 Sous-traitants

| Sous-traitant | Service | Données transmises | Localisation | Garanties exigées |
|---|---|---|---|---|
| Provider LLM principal (Anthropic 🟡, D08) | extraction CV/offres, explications, génération | contenu minimisé (jamais nom/email/téléphone hors nécessité validée) | traitement UE 🟡 **à confirmer** ; sinon SCC + analyse d'impact de transfert (TIA) | DPA art. 28 ; **clause de non-entraînement** sur nos données ; non-rétention ou rétention ≤ 30 j ; notification d'incident sans délai indu |
| Provider LLM fallback | idem | idem | idem 🟡 | idem — **mêmes clauses exigées que le principal** (le fallback ne doit pas être le maillon faible) |
| Modèle d'embeddings | vectorisation profils/offres | textes minimisés (intitulés, compétences, descriptions) | UE 🟡 | idem |
| Hébergeur cloud | compute, PostgreSQL, S3, Redis | toutes données au repos (chiffrées) | région UE (D09) | DPA, certifications (ISO 27001 🟡), KMS en UE |
| E-mail transactionnel | vérification, reset, digest | adresse e-mail | UE 🟡 | DPA, pas d'usage marketing |
| Géocodage | lat/lon des lieux | libellés de lieux **sans identifiant utilisateur** (appels côté serveur, non corrélables) | UE 🟡 | DPA ou usage de données non personnelles à documenter |

Registre des sous-traitants versionné ; tout ajout = mise à jour du registre des traitements + information des utilisateurs (politique de confidentialité).

---

## 3. AI Act — positionnement (analyse prudente, non tranchée)

**Faits de conception** : Boussole est un outil au service du candidat. Il évalue des **offres pour un candidat**, jamais des candidats pour un employeur ; il ne prend, ne recommande ni ne transmet aucune décision de recrutement ; il n'envoie aucune candidature (D10) ; le score est déterministe et publié dans sa méthode (D02) ; tout contenu généré est validé par l'humain avant usage.

**Point de vigilance** : l'annexe III du règlement (UE) 2024/1689 vise notamment, au titre de l'emploi, les systèmes d'IA destinés au **recrutement ou à la sélection** de personnes physiques (diffusion ciblée d'offres, tri des candidatures, évaluation des candidats). Boussole ne correspond pas à la lecture la plus directe de ces cas (l'utilisateur est le candidat, pas le recruteur), mais le champ exact d'expressions comme « diffusion ciblée d'offres d'emploi » et la qualification du matching côté candidat **ne sont pas tranchés ici**. **Statut : à confirmer par revue juridique formelle avant lancement** (R2, 17-open-questions). Aucune communication produit ne doit affirmer que Boussole est « hors AI Act » ou « hors haut risque » tant que cette revue n'a pas conclu.

**Obligations déjà couvertes par conception, quel que soit le statut final** :

| Exigence type (haut risque, art. 8–15) | Couverture Boussole |
|---|---|
| Transparence et information des utilisateurs | méthode de scoring publiée dans le produit, score ≠ confiance (D03), badges « incertain/inconnu », mention explicite des contenus assistés par IA |
| Supervision humaine | D10 : relecture + diff + validation avant tout export ; aucune action sortante automatique |
| Exactitude et robustesse | scoring déterministe versionné (D02), jeu annoté avec non-régression en CI (06 §5), validation Pydantic de toute sortie LLM (D08) |
| Journalisation | `ai_calls` (modèle, prompt_version, tokens, latence), `scoring_version` sur chaque résultat, `audit_log` |
| Gestion des risques | registre de risques (01 §7), DPIA, ce modèle de menaces |
| Gouvernance des données | provenance par champ (D05), liste d'exclusion des attributs sensibles (§4), registre des sources (D04) |

**Si la revue conclut au haut risque** : plan d'écart à établir (système de gestion des risques formalisé, documentation technique annexe IV, enregistrement UE, marquage CE, gestion qualité) — effort et calendrier à chiffrer à ce moment-là 🟡. Les obligations de transparence « limitées » (art. 50 : informer que l'on interagit avec un contenu généré par IA) sont couvertes dans tous les cas.

---

## 4. Non-discrimination

### 4.1 Liste d'exclusion des attributs sensibles à l'extraction

Jamais extraits, stockés dans le profil structuré, ni utilisés par le moteur (06 §3, 08 §7) :

- âge, date de naissance
- genre, civilité (M./Mme)
- photo
- origine ethnique, nationalité, lieu de naissance
- situation familiale, état civil, nombre d'enfants, grossesse
- état de santé, handicap
- religion, convictions
- opinions politiques, appartenance syndicale
- orientation sexuelle
- numéro de sécurité sociale et identifiants nationaux
- adresse précise au-delà de la **ville** (seule la ville est conservée, pour la dimension localisation)

Les champs d'identité nécessaires au service (nom, e-mail, téléphone) sont stockés mais ne sont **jamais des entrées du moteur de matching** ni des prompts de matching/génération (D09).

### 4.2 Application technique (défense en profondeur)

1. **Impossibilité structurelle** : les schémas Pydantic d'extraction (`ai-output-schemas.json`) ne contiennent aucun champ de la liste — une sortie LLM qui en produirait échoue à la validation.
2. **Consigne négative** dans les prompts d'extraction (ne pas relayer ces attributs).
3. **Filtre post-extraction** : scan par motifs (dates de naissance, civilités, mentions de nationalité…) sur les champs texte libres du profil (headline, summary) ; détection → champ signalé à l'utilisateur, non publié tel quel 🟡.
4. **Moteur** : les entrées du moteur sont énumérées limitativement (06 §2) ; le nom, l'adresse précise et tout attribut hors dimensions n'y figurent pas.

### 4.3 Tests automatiques (CI)

- **Invariance** : masquer ou permuter le prénom/nom et l'adresse d'un profil ne change **aucun** score (trivialement vrai par construction — le test garantit qu'aucune régression ne réintroduit ces champs comme entrées ; 06 §5).
- **CV adversariaux** : jeu de CV contenant délibérément des attributs sensibles → assertion : absence totale dans le profil extrait.
- **Jeu annoté équilibré** : prénoms des profils synthétiques équilibrés hommes/femmes ; écarts de distribution de scores mesurés par sous-groupe synthétique 🟡.
- Tout changement de `scoring-config.json` déclenche la suite complète (non-régression 06 §5).

### 4.4 Gouvernance

- Changement de poids/seuils : PR + 2 relecteurs 🟡 + rapport d'évaluation archivé.
- Revue trimestrielle « biais » adossée à la revue du registre des sources.
- Canal utilisateur de signalement d'un résultat perçu comme discriminant ; chaque signalement instruit et journalisé.
- La liste d'exclusion est versionnée ; tout retrait d'un item exige une justification écrite et une revue juridique.

---

## 5. Sécurité applicative

### 5.1 Authentification et autorisation

- **Sessions** : Redis, TTL 30 j glissants (12 §1) ; ID 128 bits CSPRNG ; rotation à la connexion ; invalidation à la déconnexion, au reset et au changement de mot de passe ; stockage côté serveur uniquement (le cookie ne porte que l'ID opaque).
- **Cookies** : `httpOnly; Secure; SameSite=Lax`, préfixe `__Host-` 🟡, même origine via proxy Next (D11).
- **CSRF** : double-submit token `X-CSRF-Token` sur toute méthode mutante (12 §1) ; le proxy même-origine réduit la surface mais ne remplace pas le token.
- **Mots de passe** : hachage **argon2id** (paramètres initiaux : m=64 Mio, t=3, p=1 🟡, à recalibrer sur le matériel cible) ; longueur minimale 12 caractères, pas de règles de composition arbitraires, vérification contre corpus de mots de passe compromis (API k-anonymity 🟡) ; pas d'expiration périodique ; reset par token à usage unique valable 30 min, réponse identique que l'e-mail existe ou non.
- **Autorisation** : toute ressource scopée `user_id` (extrait de la session, jamais du payload) ; ressource d'autrui → **404** (12 §5) ; aucun rôle privilégié dans l'app publique.
- **Rate limiting** (Redis, par utilisateur puis IP — valeurs de 12 §1) : global 60/min, recherche 30/min, générations 10/h et 40/j, upload 5/j, export 2/j ; login avec backoff progressif.

### 5.2 Mapping OWASP Top 10 (2021)

| Risque | Contrôles |
|---|---|
| A01 Broken Access Control | scoping user_id systématique, 404 anti-énumération, tests d'accès croisé en CI |
| A02 Cryptographic Failures | §5.6 (TLS, AES-256, KMS), argon2id, aucun secret en clair |
| A03 Injection | requêtes paramétrées, validation Pydantic, échappement React, sanitisation des offres à l'ingestion ; **prompt injection traitée comme une classe d'injection** (§5.4) |
| A04 Insecure Design | ce modèle de menaces, revues de conception, décisions D01–D15 documentées |
| A05 Security Misconfiguration | IaC revue, images minimales non-root, en-têtes CSP/HSTS/`X-Content-Type-Options` à l'edge (12 §5), CORS fermé |
| A06 Vulnerable Components | scan dépendances en CI (§6.3), lockfiles, images scannées |
| A07 Identification & AuthN Failures | §5.1 |
| A08 Software & Data Integrity | CI avec revues obligatoires, lockfiles vérifiés, config de scoring versionnée, pas de plugin/code tiers chargé dynamiquement |
| A09 Logging & Monitoring Failures | §5.7 + observabilité 10 §6 (alertes sécurité : pics d'échecs login, 404 en rafale) |
| A10 SSRF | egress en allowlist par service, URLs de connecteurs figées en config, aucune URL fournie par l'utilisateur n'est récupérée par le serveur au MVP |

### 5.3 Sécurité de l'upload CV

- Validation du type réel par **magic bytes** (PDF, DOCX) — l'extension et le `Content-Type` déclarés ne sont jamais suffisants (12 §5) ; taille ≤ 10 Mo.
- **Antivirus** ClamAV 🟡 sur l'objet avant parsing ; fichier en quarantaine si détection.
- Limites anti-bombe DOCX : ratio de décompression ≤ 100, ≤ 1000 entrées, taille décompressée ≤ 50 Mo 🟡 ; timeout de parsing.
- **Aucune exécution** : les fichiers ne sont jamais servis inline (`Content-Disposition: attachment`), jamais interprétés ; macros DOCX ignorées (extraction texte seule).
- Parsing dans un **worker isolé** : conteneur non privilégié, système de fichiers en lecture seule hors répertoire temporaire, egress limité au gateway LLM 🟡.
- Stockage S3 privé chiffré, clé d'objet aléatoire, nom de fichier original stocké comme métadonnée échappée.

### 5.4 Prompt injection (référence : 08)

Principe : **tout document importé (CV, offre) est une donnée non fiable, jamais une instruction** (R5).

- Séparation stricte instructions/données : consignes dans le message système, contenu utilisateur dans des blocs délimités ; les délimiteurs présents dans le contenu sont échappés.
- **Sorties JSON contraintes** validées Pydantic contre `ai-output-schemas.json` (D08) : une injection réussie ne peut produire qu'un JSON conforme au schéma attendu, pas une action.
- Les tâches LLM d'extraction/génération n'ont **aucun outil, aucun accès réseau, aucune capacité d'action** — le pire cas est une donnée fausse, traitée par les seuils de confiance (06 §1) et la validation humaine (D10).
- L'explication ne reçoit que les `explanation_facts` (D14) : une offre piégée ne peut pas injecter de texte dans le prompt d'explication.
- Génération ancrée : le prompt de génération reçoit le profil validé + les faits structurés de l'offre, pas l'offre brute 🟡 (précisé dans 08) ; contrôle post-génération des claims d'ancrage (12 §4).
- Filtrage des sorties : aucune URL absente des entrées dans les contenus générés 🟡.
- **Tests adversariaux en CI** : corpus d'offres et de CV piégés (instructions d'exfiltration, demandes de changement de rôle) avec assertions sur les sorties.

### 5.5 Secrets

- Gestionnaire de secrets de la plateforme (vault cloud 🟡) → injection en variables d'environnement au déploiement ; jamais en repo, en image, ni en logs.
- Rotation : clés API LLM et e-mail 90 j 🟡 ; credentials DB rotation au déploiement majeur et immédiate sur suspicion ; procédure de révocation documentée par secret.
- Détection de fuite en CI (scan type gitleaks 🟡) ; secrets distincts par environnement (10 §9).

### 5.6 Chiffrement

- **Transit** : TLS 1.2 minimum, 1.3 préféré, HSTS ; TLS aussi sur les liens internes API↔Postgres/Redis 🟡.
- **Repos** : AES-256 sur volumes PostgreSQL, S3 (SSE-KMS), Redis persistant et backups.
- **Clés** : KMS géré du cloud, résidant en UE ; rotation annuelle automatique ; accès aux clés restreint par rôle IAM ; pas de chiffrement applicatif par champ au MVP (réévaluer si exigence client ou champ ultra-sensible apparaît) 🟡.

### 5.7 Journalisation d'audit (sans données sensibles)

- Table `audit_log` (11 §1), **append-only** : l'utilisateur applicatif PostgreSQL n'a que `INSERT`/`SELECT` sur cette table.
- Événements journalisés : inscription, login (succès/échec), logout, reset mot de passe, upload CV, validation de profil, création/validation/export de génération, export RGPD, demande de suppression, changements de consentements.
- Champs : timestamp, `user_id`, action, type et id de ressource, `trace_id`, IP tronquée (/24, /48 en IPv6) 🟡, user-agent.
- **Jamais** : contenu de CV/profil, prompts, mots de passe, tokens, corps de requêtes.
- Rétention 13 mois ; anonymisation à la suppression du compte (11 §2) ; accès restreint et lui-même audité.
- Les logs applicatifs (10 §6) suivent la même règle : identifiants et métadonnées, jamais de contenu personnel.

---

## 6. Sécurité infrastructure

### 6.1 Réseau

- Seul le front/edge (Next + proxy) est exposé publiquement ; l'API FastAPI n'est joignable que depuis le proxy ; PostgreSQL, Redis, workers : réseau privé, aucune IP publique.
- Egress contrôlé par **allowlist** par composant : workers ingestion → sources approuvées + géocodage ; workers ai → providers LLM ; API → e-mail. Tout autre flux sortant refusé.
- Accès d'administration : bastion/VPN avec MFA, accès nominatifs, journalisés 🟡.

### 6.2 Sauvegardes

- Chiffrées (mêmes clés KMS), stockées en UE, **rétention ≤ 30 j** — condition nécessaire de la purge RGPD « backups au cycle » (§2.3).
- **Testées** : restauration mensuelle automatisée sur environnement isolé avec vérifications d'intégrité (détail : 10 §8).

### 6.3 Gestion des vulnérabilités

- Dépendances scannées en CI à chaque PR + scan quotidien (pip-audit/npm audit + Dependabot ou équivalent 🟡) ; images conteneur scannées avant déploiement.
- SLA de correction 🟡 : critique 48 h, haute 7 j, moyenne 30 j.
- Veille sur les CVE des composants critiques (FastAPI, parseurs PDF/DOCX — surface d'attaque directe de l'upload).
- Pentest externe avant lancement public 🟡.

### 6.4 Réponse à incident et notification CNIL

1. **Détection** : alertes d'observabilité (10 §6), remontées support, notifications de sous-traitants (obligation « sans délai indu » dans chaque DPA).
2. **Qualification** (≤ 4 h ouvrées 🟡) : incident de sécurité ? violation de données personnelles (art. 4.12) ? Sévérité, périmètre, personnes concernées.
3. **Containment** : révocation de secrets, invalidation de sessions, isolation de composant, coupure d'un connecteur ou provider.
4. **Notification** : si violation de données personnelles présentant un risque → **CNIL ≤ 72 h** après constat (art. 33), notification par paliers si l'investigation est en cours ; information des personnes concernées **sans retard injustifié** si risque élevé (art. 34) ; registre interne de **toutes** les violations, y compris non notifiées, avec justification.
5. **Post-mortem** sans blâme ≤ 7 j, actions correctives suivies.
- Rôles définis à l'avance (responsable incident, communication, contact CNIL) ; procédure testée par exercice sur table annuel 🟡.

---

## Questions ouvertes

1. **AI Act** : qualification formelle de Boussole vis-à-vis de l'annexe III (recrutement/sélection) — revue juridique à commanditer ; qui la réalise et pour quand ? (bloquant lancement, R2)
2. **Localisation du traitement LLM** : les providers pressentis offrent-ils un traitement en région UE avec clauses de non-entraînement et non-rétention ? Sinon, la combinaison SCC + TIA est-elle jugée suffisante par la revue juridique ?
3. **DPO** : désignation obligatoire (suivi à grande échelle de données de profil ?) ou volontaire ? Interne ou externalisé ?
4. **Art. 22** : la lecture « aide à la décision pour le candidat, hors art. 22 » tient-elle si un utilisateur affirme avoir renoncé à candidater sur la foi d'un score ? Formulation produit à ajuster ?
5. **Antivirus** : ClamAV auto-hébergé vs service managé — décision d'implémentation (marqué 🟡 dans 12 §5).
6. **MFA** : TOTP au MVP ou post-MVP ? (le compte protège des données très riches — arbitrage friction/risque)
7. **Anonymisation vs pseudonymisation** de `ai_calls`/`audit_log` après suppression : le `subject_key` haché est-il juridiquement une anonymisation (sel détruit ?) — à valider avec la revue juridique.
8. **IP dans l'audit log** : la troncature /24 est-elle le bon équilibre traçabilité/minimisation, ou faut-il l'IP complète à rétention courte pour l'anti-abus ?
9. **Back-office** : quel outillage d'administration au MVP (accès DB nominatif en lecture seule ? mini-admin séparé ?) et sous quel contrôle d'accès ?
10. **Pentest** : budget et fenêtre avant lancement public.
