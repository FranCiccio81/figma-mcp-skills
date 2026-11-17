# figma-mcp-skills

Bibliothèque d'Agent Skills pour le design produit, l'UX, les design systems, les plateformes natives Apple et Android, l'ingénierie frontend, la qualité et les workflows Figma MCP.

Objectif : peu de skills, mais fiables. Chaque skill est conforme à la [spécification Agent Skills](https://github.com/agentskills/agentskills), sourcé auprès des éditeurs officiels, testé par la CI et accompagné d'au moins un cas d'évaluation réaliste.

## Sommaire

1. [Vision](#vision)
2. [Catalogue](#catalogue)
3. [Installation](#installation)
4. [Configuration Claude Code](#configuration-claude-code)
5. [Figma MCP](#figma-mcp)
6. [Exemples d'usage](#exemples-dusage)
7. [Contribuer](#contribuer)
8. [Mettre à jour un skill](#mettre-à-jour-un-skill)
9. [Dépannage](#dépannage)
10. [Licence et attribution](#licence-et-attribution)

## Vision

* **Précision plutôt que volume** : un skill dit quand l'utiliser, quoi produire, comment vérifier le résultat, et sur quelles sources il s'appuie.
* **Pas d'invention** : aucun skill n'autorise à fabriquer des insights utilisateurs, des métriques, des valeurs Figma inaccessibles ou des noms d'API.
* **Plateformes respectées** : les conventions Apple et Android sont traitées séparément ; un pattern iOS n'est jamais transposé tel quel sur Android.
* **Précédence explicite** en cas de conflit : sécurité et exigences légales, puis contraintes projet validées, guides officiels de plateforme, design system du projet, skills réutilisables, bonnes pratiques communautaires.

## Catalogue

Le registre complet (version, statut, confiance, sources, compatibilité) est généré dans [docs/skill-registry.md](docs/skill-registry.md).

| Domaine | Skills |
|---|---|
| Produit | `product-discovery`, `jobs-to-be-done`, `value-proposition-design`, `opportunity-solution-tree`, `product-strategy`, `product-requirements`, `experiment-design`, `prioritization`, `product-metrics` |
| UX | `ux-research-planning`, `usability-testing`, `heuristic-evaluation`, `journey-mapping`, `information-architecture`, `interaction-design`, `ux-writing`, `cognitive-accessibility`, `design-critique` |
| Design systems | `design-token-architecture`, `component-api-design`, `design-system-governance` |
| Bridge 2.0 (Swissquote, PostFinance) | Entrée : `bridge-design-system`. Plateformes : `bridge-ios`, `bridge-android`, `bridge-tablet`, `bridge-foldables`, `bridge-web`. Rôles : `bridge-designer-workflow`, `bridge-developer-workflow`, `bridge-product-manager`. Transverses : `bridge-content-and-formats`, `bridge-accessibility`, `bridge-compliance-review` |
| Apple | `apple-hig-review`, `swiftui-implementation`, `apple-accessibility` |
| Android | `material3-compose`, `android-adaptive-layouts`, `android-accessibility` |
| Ingénierie | `react-typescript-components`, `semantic-html-css`, `frontend-testing`, `frontend-performance`, `frontend-security`, `code-review`, `technical-specification` |
| Qualité | `accessibility-audit`, `visual-regression-qa` |
| Workflows IA | `figma-design-to-code`, `figma-spec-handoff`, `figma-design-code-drift`, `skill-router` |
| Historique | `component` (dans `.claude/skills/component`, workflow composant DS en 6 actions) |

Tous les nouveaux skills sont en statut `beta` : ils passent en `stable` après exécution et relecture de leurs évaluations (voir [l'architecture](docs/architecture/skill-architecture.md)).

### Bridge 2.0 : quel skill pour qui

| Rôle | Commencer par | Puis |
|---|---|---|
| Designer | `bridge-designer-workflow` | le skill de la plateforme, `bridge-accessibility`, `bridge-compliance-review` avant le handoff |
| Développeur | `bridge-developer-workflow` | le skill de la plateforme, `bridge-content-and-formats` pour les formateurs, `bridge-compliance-review` avant le merge |
| Product manager | `bridge-product-manager` | `product-requirements`, `bridge-content-and-formats`, `bridge-accessibility` |

Règles communes : 2 niveaux de tokens (primitives jamais utilisées, tokens sémantiques seuls utilisés), 6 modes (SQ, Default, PF en clair et sombre), aucune valeur brute ni teinte par opacité, actions produit en encre sombre, orange de marque réservé aux moments de marque, Buy bleu et Sell rouge, WCAG 2.2 AA minimum et AAA visé sur confirmation d'ordre, authentification et frais.

Les cinq skills plateforme proviennent de l'archive `bridge-platform-skills` v0.2 (12 novembre 2026), importés sans modification de fond puis complétés (métadonnées, sections, évaluations). L'instantané des foundations vit dans `skills/bridge/_shared/bridge-foundations.md` ; chaque skill Bridge en porte une copie synchronisée par `tools/sync_bridge_foundations.py` (vérifiée en CI). Le script `skills/bridge/bridge-compliance-review/scripts/check_tokens.py` vérifie les noms de tokens couleur contre l'index exact.

### Skills officiels recommandés en complément

Ces skills ne sont pas copiés ici (licences et maintenance chez leurs éditeurs). Installez-les à côté :

* Android : https://github.com/android/skills (`edge-to-edge`, `adaptive`, `navigation-3`, `testing-setup`, `migrate-xml-views-to-jetpack-compose`)
* Figma : https://github.com/figma/mcp-server-guide (plugin Figma, skills `figma-use`, `figma-code-connect`, etc.)
* Anthropic : https://github.com/anthropics/skills (`skill-creator` pour écrire et évaluer des skills)

## Installation

```bash
git clone https://github.com/FranCiccio81/figma-mcp-skills.git
cd figma-mcp-skills

# Installer des skills dans un projet (liens symboliques, à plat)
tools/install.sh /chemin/vers/mon-projet/.claude/skills --domain ux --domain apple

# Ou quelques skills précis, au niveau utilisateur
tools/install.sh ~/.claude/skills --skill skill-router --skill accessibility-audit

# Copier au lieu de lier
tools/install.sh /chemin/vers/mon-projet/.claude/skills --copy --domain product
```

Le script n'écrase jamais un dossier existant sans `--force` et ignore les skills spécifiques à un projet (tous les skills Bridge) sans `--include-project` :

```bash
# Tous les skills Bridge dans un projet Swissquote
tools/install.sh /chemin/vers/app-swissquote/.claude/skills --domain bridge --include-project
```

## Configuration Claude Code

1. Installez Claude Code (voir la documentation officielle d'Anthropic).
2. Installez les skills voulus dans `.claude/skills/` du projet ou dans `~/.claude/skills/` (voir ci-dessus). Claude Code les découvre automatiquement par leur `description`.
3. Facultatif : copiez `.claude/CLAUDE.md` comme base de règles projet et adaptez la partie Bridge à votre design system.
4. Pour les demandes multi-disciplines, commencez par le routeur :
   `python3 skills/ai-workflows/skill-router/scripts/route.py "votre demande"`

## Figma MCP

`.mcp.json` déclare les deux serveurs officiels :

| Serveur | URL | Usage |
|---|---|---|
| Distant (recommandé par Figma) | `https://mcp.figma.com/mcp` | Fonctionne avec un lien Figma contenant `node-id` ; outils les plus complets |
| Desktop | `http://127.0.0.1:3845/mcp` | Sélection directe dans l'app Figma Desktop (Dev Mode) ; jeu d'outils réduit |

```bash
claude mcp add --transport http figma https://mcp.figma.com/mcp
claude mcp add --transport http figma-desktop http://127.0.0.1:3845/mcp
claude mcp list
```

Les skills Figma découvrent les outils disponibles au moment de l'exécution et basculent sur un mode dégradé documenté (captures d'écran, liste de variables) si le serveur est absent. Ils n'inventent jamais une valeur qu'ils n'ont pas pu lire. Les quotas d'appels dépendent du plan et du type de siège Figma : vérifiez la documentation Figma à jour.

Guide pas à pas historique : [docs/workflow-figma-mcp.md](docs/workflow-figma-mcp.md).

## Exemples d'usage

```text
"Conçois et implémente un onboarding bancaire accessible pour iOS."
  → skill-router sélectionne product-requirements, interaction-design, apple-hig-review,
    swiftui-implementation, apple-accessibility, accessibility-audit (+ design system projet)

"Implémente cette frame Figma dans notre app Next.js : <lien avec node-id>"
  → figma-design-to-code, react-typescript-components, frontend-testing

"Audite cet écran de connexion pour WCAG 2.2 AA."
  → accessibility-audit

"Nos 300 variables Figma 'Blue/500' sont utilisées directement : propose une architecture de tokens DTCG avec dark mode."
  → design-token-architecture

"Notre app est en portrait seul et passe en targetSdk 36 : que faut-il changer pour tablettes et pliables ?"
  → android-adaptive-layouts (+ skill officiel android/skills adaptive)
```

## Contribuer

1. Créez le skill dans `skills/<domaine>/<nom>/` avec `SKILL.md` et `evals/evals.json` (modèle : n'importe quel skill existant ; règles : [docs/architecture/skill-architecture.md](docs/architecture/skill-architecture.md)).
2. Ajoutez toute nouvelle source au [registre des sources](docs/sources/source-registry.md) avant de la citer.
3. Ajoutez le skill à `skills/ai-workflows/skill-router/references/routing-table.json`.
4. Vérifiez localement :
   ```bash
   pip install pyyaml
   python3 tools/sync_bridge_foundations.py   # si les foundations Bridge ont changé
   python3 tools/validate_skills.py
   python3 tools/build_registry.py
   python3 -m unittest discover -s tools/tests -t .
   ```
5. Ouvrez une PR. La CI `skills-ci` rejoue ces contrôles et le validateur de référence `skills-ref`.

Règles : pas de contenu copié d'une documentation protégée, pas de PDF de référence, pas de secret, pas d'information confidentielle d'entreprise dans les skills universels.

## Mettre à jour un skill

* Correction sans changement de comportement : version patch.
* Nouveau comportement compatible : version mineure. Changement des entrées ou sorties : version majeure.
* Mettez à jour `last-reviewed`, relancez `tools/build_registry.py`.
* Revue trimestrielle des sources (WCAG, DTCG, versions iOS et Android, outils Figma MCP).

## Dépannage

| Symptôme | Cause probable | Solution |
|---|---|---|
| Le skill ne se déclenche pas | Skill installé dans un sous-dossier | Les skills doivent être à plat : `.claude/skills/<nom>/SKILL.md` (utilisez `tools/install.sh`) |
| `metadata must map strings to strings` | Version ou date non quotée | Écrire `version: "1.0.0"` |
| `source host not in docs/sources/source-registry.md` | Source non enregistrée | Ajouter la source au registre après vérification |
| Aucun outil Figma listé | Serveur non connecté ou app Figma fermée | `claude mcp list`, relancer Figma Desktop, ou utiliser le serveur distant |
| `Large MCP response` | Frame volumineuse | Normal ; découper avec `get_metadata` |

## Licence et attribution

* **Licence du dépôt : à définir par le propriétaire.** Aucun fichier `LICENSE` n'existe encore ; tant qu'il n'est pas ajouté, les contenus ne sont pas réutilisables par des tiers.
* Sources et décisions d'adoption : [docs/sources/source-registry.md](docs/sources/source-registry.md).
* Les marques citées (Apple, Android, Material, Figma, WCAG) appartiennent à leurs propriétaires. Les skills résument et renvoient aux sources officielles sans les reproduire.

## Autres contenus du dépôt

Ce dépôt contient aussi des projets sans lien direct avec la bibliothèque de skills : `boussole/` (application, avec sa propre CI), `cv-job-matching/` (spécifications) et `pension-partner-app/` (prototype). Ils ne sont pas modifiés par la bibliothèque. Voir l'[audit de référence](docs/audits/skills-baseline-audit.md) pour la recommandation de les séparer.
