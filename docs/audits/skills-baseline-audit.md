# Audit de référence des skills

Date de l'audit : 2026-11-17
Commit de référence : `4c3de4479dd5d0bc4b40ef934e4e0f2b697f78dc` (branche `main`)
Branche de travail : `feat/skills-library-v2`
Méthode : lecture intégrale de chaque `SKILL.md`, des règles, de la documentation et de la CI ; validation avec le validateur de référence `skills-ref` (agentskills/agentskills, Apache-2.0) ; recherche de secrets, de liens factices et de doublons ; inspection de l'historique Git (81 commits accessibles).

## 1. Synthèse

Le dépôt n'est pas une bibliothèque de skills au sens de la spécification Agent Skills. Il mélange trois natures de contenu :

1. Une boîte à outils design (4 guides `skills/0x-*`, des règles, une doc de workflow, un skill `component`).
2. Deux applications complètes sans lien avec les skills : `boussole/` (≈ 400 fichiers, Python et Next.js, avec sa propre CI) et `pension-partner-app/` (prototype HTML et JS, polices et images embarquées), plus un dossier de spécifications `cv-job-matching/`.
3. Un fichier `skills-lock.json` qui décrit l'installation globale de 59 skills tiers sur une machine, pas le contenu du dépôt.

Constats majeurs :

* **Les 4 skills historiques sont invalides** : aucun n'a de frontmatter YAML. `skills-ref validate` échoue sur les quatre (`SKILL.md must start with YAML frontmatter`). Ils ne peuvent donc être ni découverts ni activés automatiquement par un agent compatible. Ce sont des guides, pas des skills.
* **Un seul skill conforme** : `.claude/skills/component` (valide, structuré en `references/`, versionné 1.1).
* **Erreurs factuelles d'accessibilité** : le critère 2.5.5 Target Size est cité comme exigence AA alors qu'il est de niveau AAA ; le critère AA pertinent depuis WCAG 2.2 est 2.5.8 (24 × 24 px CSS). La référence est WCAG 2.1 alors que WCAG 2.2 est la Recommandation W3C en vigueur depuis octobre 2023. L'affirmation selon laquelle WCAG serait obligatoire au titre de la FINMA n'est appuyée par aucune source. Les ratios de contraste cités sont faux : recalculés, `#9CA3AF` sur blanc donne 2.54:1 (et non 2.85:1) et `#6B7280` donne 4.83:1, conforme AA (et non 4.48:1). Ces valeurs erronées étaient reprises dans `.claude/CLAUDE.md` et `components/input-documentation.md`, corrigés dans cette branche.
* **Dépôt public contenant des informations d'entreprise** : règles du design system Bridge de Swissquote, correspondances de tokens, identifiants de fichiers Figma. À valider par le propriétaire (risque de confidentialité, voir section 4).
* **Pas de licence** à la racine du dépôt public : juridiquement, rien n'est réutilisable par des tiers. Le skill `component` déclare `license: MIT` sans fichier de licence.
* **Configuration Figma MCP limitée au serveur desktop**, alors que Figma recommande désormais le serveur distant (`https://mcp.figma.com/mcp`), qui expose davantage d'outils.
* **Redondance** : le flux MCP (metadata, design_context, screenshot, variable_defs) est décrit cinq fois avec des variations mineures (`.claude/CLAUDE.md`, `rules/figma-mcp-rules.md`, `docs/workflow-figma-mcp.md`, skills 02 et 03).
* **Aucun test ni CI sur les skills** ; la seule CI (`boussole-ci.yml`) concerne l'application Boussole.

## 2. Inventaire et évaluation

Échelle de qualité : A (prêt), B (utile, à corriger), C (à refondre), D (hors périmètre ou obsolète).

| Actif existant | Rôle actuel | Qualité | Problème identifié | Action recommandée | Risque | Priorité |
|---|---|---|---|---|---|---|
| `skills/01-design-system/SKILL.md` | Guide tokens 4 tiers, composants, Code Connect, spécifique Bridge | C | Pas de frontmatter ; mélange principes universels et règles Bridge ; URL factices `[BRIDGE_FILE_ID]`, `[ID]` ; ignore le format DTCG stable 2025.10 ; 374 lignes chargées d'un bloc | Migrer vers `skills/design-systems/bridge-design-system/` (spécifique projet) ; archiver le texte en `references/legacy-guide.md` ; créer `design-token-architecture` (universel, DTCG) | Faible (contenu préservé) | P0 |
| `skills/02-design-to-code/SKILL.md` | Figma vers React et Jetpack Compose | C | Pas de frontmatter ; mélange web et Android dans un seul skill ; MCP desktop seulement ; affirmation non vérifiée sur la disponibilité des outils | Migrer vers `skills/ai-workflows/figma-design-to-code/` avec découverte des outils à l'exécution et repli documenté ; déléguer Compose à `material3-compose` | Faible | P0 |
| `skills/03-ux-research-specs/SKILL.md` | Specs fonctionnelles et handoff depuis Figma | B | Pas de frontmatter ; le titre parle de recherche UX mais le contenu est du handoff | Migrer vers `skills/ai-workflows/figma-spec-handoff/` ; créer de vrais skills de recherche (`ux-research-planning`, `usability-testing`) | Faible | P0 |
| `skills/04-accessibility/SKILL.md` | Audit WCAG depuis Figma et code | C | Pas de frontmatter ; WCAG 2.1 au lieu de 2.2 ; 2.5.5 présenté comme AA (c'est AAA) ; base légale FINMA non sourcée ; ratios de contraste faux (`#9CA3AF` sur blanc annoncé 2.85:1, réel 2.54:1 ; `#6B7280` annoncé 4.48:1 limite, réel 4.83:1 conforme) | Migrer vers `skills/quality/accessibility-audit/`, corriger les erreurs, ajouter sévérité, confiance et preuve par constat | Moyen (conformité) | P0 |
| `.claude/skills/component/` | Workflow composant DS en 6 actions | A | Valide ; seul skill conforme ; référence `ds/specs/active/` et `ds/audits/active/` | Conserver en place (aucune migration) ; l'inscrire au registre ; ajouter un fichier de licence si MIT est confirmé | Faible | P2 |
| `.claude/CLAUDE.md` | Règles globales Claude Code | B | Duplique les règles MCP ; correspondances Bridge en dur ; mêmes erreurs de touch target | Garder comme règles projet ; pointer vers les skills ; corriger WCAG 2.2 | Faible | P1 |
| `rules/figma-mcp-rules.md` | Règles MCP universelles | B | Redondant avec CLAUDE.md et les skills | Conserver ; renvoyer vers `figma-design-to-code` comme source de vérité | Faible | P2 |
| `rules/bridge-design-system-rules.md` | Règles Bridge Swissquote | B | Contenu d'entreprise dans un dépôt public | Décision du propriétaire : rendre privé ou anonymiser | Élevé (confidentialité) | P0 (décision) |
| `docs/workflow-figma-mcp.md` | Guide pas à pas MCP | B | Redondant | Conserver, lier depuis le README | Faible | P3 |
| `components/input-documentation.md`, `ds/specs/active/button-spec.md` | Livrables générés (exemples) | B | Exemples de sortie utiles mais liés à un fichier Figma réel | Conserver comme exemples de sortie ; ne pas les déplacer (le skill `component` écrit dans `ds/specs/active/`) | Faible | P3 |
| `skills-lock.json` | Lockfile de 59 skills tiers installés globalement | D | Ne décrit pas le dépôt ; 41 skills d'un même éditeur résumant des livres sous droits (provenance des contenus non vérifiée) ; SETUP.md annonce 63 skills | Conserver tel quel (outil `npx skills`) ; documenter son statut ; revue de licence avant toute réutilisation | Moyen (licences) | P2 |
| `SETUP.md` | État de l'installation locale | D | Daté du 2026-03-29, chiffres incohérents (59, 63, 17) | Marquer comme historique ; renvoyer au README | Faible | P3 |
| `README.md` | Présentation | C | Placeholder `TON_USERNAME` ; structure obsolète ; ne mentionne ni Boussole ni Pension Partner ; serveur desktop uniquement | Réécrire | Faible | P1 |
| `.mcp.json` | Config MCP | B | Desktop seulement | Ajouter le serveur distant recommandé | Faible | P1 |
| `boussole/`, `cv-job-matching/` | Application et specs d'un produit distinct | D (hors périmètre) | Rien à voir avec une bibliothèque de skills ; alourdit le dépôt (20 Mo au total) ; CI dédiée | Ne pas toucher dans cette PR ; recommander un dépôt séparé | Moyen (périmètre) | P2 |
| `pension-partner-app/` | Prototype produit avec polices, images, React et Babel vendorisés | D (hors périmètre) | Hors périmètre ; vérifier la licence des polices et des images embarquées | Ne pas toucher ; recommander un dépôt séparé | Moyen (licences d'assets) | P2 |
| `.github/workflows/boussole-ci.yml` | CI de Boussole | A (pour Boussole) | Aucune CI pour les skills | Ajouter `skills-ci.yml` distinct | Faible | P1 |
| `.gitignore` | Ignore `.claude/skills/*` sauf `component` | B | Cohérent avec l'installation par lien symbolique | Conserver | Faible | P3 |

## 3. Contenu réutilisable et contenu spécifique

| Réutilisable (universel) | Spécifique au projet ou à l'entreprise |
|---|---|
| Stratégie de découpage des grandes frames, ordre des appels MCP, traitement de la sortie React + Tailwind comme représentation | Correspondances `Grey/900` vers `--color-text-primary`, tokens Bridge, breakpoints Bridge |
| Hiérarchie de tokens (primitives, sémantique, composant) | Noms de fichiers Figma (`YMXQcB0QWivNJGwH3jJUI7`), nœuds, packages `com.swissquote.bridge` |
| Pièges d'imbrication (double border-radius) | Exigences réglementaires suisses citées sans source |
| Flux spec, review, dev du skill `component` | Exemples Input et Button du laboratoire Innotech |

## 4. Sécurité et licences

* Recherche de secrets (clés API, jetons) : aucun secret détecté dans les fichiers suivis. `boussole/.env.example` ne contient que des gabarits.
* Le dépôt est **public** (vérifié via l'API GitHub). Les règles Bridge et les identifiants Figma internes y sont donc exposés. Décision attendue du propriétaire.
* Pas de fichier `LICENSE` : à décider par le propriétaire. Proposition : MIT pour les skills rédigés ici, en cohérence avec la déclaration du skill `component`. Aucune licence n'a été ajoutée sans décision.
* `pension-partner-app/assets/fonts` : la police principale déclarée est Hanken Grotesk (licence OFL) ; les autres fichiers de police et les images n'ont pas pu être attribués. À vérifier avant toute diffusion.

## 5. Historique Git

81 commits accessibles. Les commits récents concernent presque exclusivement Boussole (PR #4 à #8). Les skills n'ont pas évolué depuis leur création fin mars 2026. Aucune modification non commitée au moment de l'audit.

## 6. Décisions de migration

1. Les 4 guides deviennent des skills valides dans une arborescence par domaine. Le texte d'origine est conservé intégralement (`git mv`, historique préservé) dans `references/legacy-guide.md`, avec un avertissement d'errata en tête de fichier.
2. Le skill `component` reste à son emplacement pour ne pas casser son usage actuel.
3. Boussole, Pension Partner et cv-job-matching ne sont pas modifiés.
4. Toute nouvelle connaissance est rédigée à partir de sources primaires vérifiées (voir `docs/sources/source-registry.md`).
