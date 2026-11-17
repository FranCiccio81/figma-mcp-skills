# figma-mcp-skills

Bibliothèque d'Agent Skills pour le design produit, l'UX, les design systems, le design et le développement natifs Apple et Android, le frontend, l'accessibilité et les workflows Figma MCP.

36 skills, conformes à la [spécification Agent Skills](https://agentskills.io/specification), validées automatiquement, chacune avec ses sources, ses critères d'acceptation et au moins un cas d'évaluation réaliste.

## Vision

Un système expert fiable plutôt qu'une collection de fichiers Markdown :

- **Sources officielles d'abord** (Apple HIG, Android et Material 3, W3C WCAG 2.2, DTCG 2025.10, documentation Figma MCP), tracées dans un [registre des sources](docs/sources/source-registry.md).
- **Aucune donnée inventée** : chaque skill distingue `[Observed]`, `[Validated]`, `[Assumption]` et `[Recommendation]`, et déclare ce qu'elle n'a pas pu vérifier.
- **Orchestration** : un routeur active seulement les skills utiles selon l'intention et la plateforme.
- **Le projet a priorité** : les règles du projet consommateur (`CLAUDE.md`, `rules/`) l'emportent sur les skills génériques.

## Catalogue

Le catalogue complet, avec version, statut, sources, compatibilité et état des tests, est généré dans [docs/registry/skills-registry.md](docs/registry/skills-registry.md).

| Domaine | Skills |
|---|---|
| Produit | `product-discovery`, `jobs-to-be-done`, `product-strategy`, `product-requirements`, `experiment-design`, `prioritization`, `product-metrics` |
| UX | `ux-heuristic-evaluation`, `usability-testing`, `research-planning`, `journey-mapping`, `information-architecture`, `ux-writing`, `interaction-design-spec` |
| Design systems | `component`, `design-token-architecture`, `design-system-governance` |
| Apple | `apple-hig-review`, `swiftui-implementation`, `apple-accessibility` |
| Android | `material3-design-review`, `compose-implementation`, `android-accessibility` |
| Ingénierie | `react-component-engineering`, `semantic-html-and-css`, `frontend-testing`, `frontend-performance`, `frontend-security`, `frontend-code-review`, `technical-specification` |
| Qualité | `accessibility-audit`, `design-implementation-qa` |
| Workflows IA et Figma | `skill-router`, `figma-design-context`, `figma-token-mapping`, `figma-implementation-spec` |

## Structure du dépôt

```
skills/<domaine>/<nom>/        copie canonique de chaque skill (SKILL.md, references/, evals/, scripts/)
skills/registry.json           registre généré, lu par le routeur
.claude/CLAUDE.md              règles Claude Code (Figma MCP, Bridge, accessibilité)
.claude/skills/component       lien de compatibilité vers skills/design-systems/component
rules/                         règles Figma MCP universelles et règles Bridge (Swissquote)
docs/architecture/             architecture et conventions des skills
docs/sources/                  registre des sources (provenance, licences, décisions)
docs/registry/                 catalogue généré
docs/audits/                   audit de référence
docs/legacy-skills/            anciennes skills 01 à 04, archivées avec table de correspondance
scripts/                       validation, registre, installation, vérification des liens
tests/                         tests de l'outillage et des scripts embarqués
components/, ds/specs/         exemples de livrables produits avec les skills
boussole/, cv-job-matching/, pension-partner-app/   projets applicatifs, hors périmètre de la bibliothèque
```

## Installation

Prérequis : [Claude Code](https://docs.anthropic.com/en/docs/claude-code) ou tout outil compatible Agent Skills, Python 3.11 et plus pour l'outillage.

```bash
git clone https://github.com/FranCiccio81/figma-mcp-skills.git
cd figma-mcp-skills

# Toutes les skills, au niveau utilisateur
scripts/install-skills.sh --target ~/.claude/skills

# Seulement certains domaines, dans un projet
scripts/install-skills.sh --target ../mon-app/.claude/skills --domain apple --domain quality --domain ai-workflows

# Quelques skills, en copie (Windows ou instantané figé)
scripts/install-skills.sh --target ../mon-app/.claude/skills --skill skill-router --skill figma-design-context --copy

# Lister
scripts/install-skills.sh --list
```

Claude Code découvre les skills à plat (`.claude/skills/<nom>/SKILL.md`) : le script aplatit l'arborescence par domaine en liens symboliques (par défaut) ou en copies. Il ne fait aucun accès réseau et refuse d'écraser un dossier qui n'est pas une skill.

### Skills officielles complémentaires (recommandées)

Nos skills orchestrent et délèguent l'implémentation détaillée aux skills officielles plutôt que de les recopier :

```bash
# Android (Google) : adaptive, edge-to-edge, navigation-3, testing-setup...
/plugin marketplace add android/skills
/plugin install android-skills@android-skills

# Figma : figma-use, figma-design-to-code, figma-code-connect, figma-swiftui...
# Voir https://github.com/figma/mcp-server-guide pour l'installation du plugin Figma
```

## Configuration Claude Code

1. Copier `.claude/CLAUDE.md` dans le projet consommateur et l'adapter (les règles Bridge sont propres à Swissquote).
2. Installer les skills (ci-dessus).
3. Pour une demande en plusieurs étapes, demander à Claude d'utiliser `skill-router`, ou laisser les descriptions déclencher les skills.

## Configuration Figma MCP

Figma recommande le **serveur distant** ; le **serveur desktop** reste utile pour travailler sur la sélection courante.

```bash
# Serveur distant (OAuth)
claude mcp add --transport http figma https://mcp.figma.com/mcp

# Serveur desktop : Figma Desktop > Dev Mode > panneau Inspect > Enable desktop MCP server
claude mcp add --transport http figma-desktop http://127.0.0.1:3845/mcp

claude mcp list
```

Le fichier `.mcp.json` du dépôt configure le serveur desktop. Les outils exposés diffèrent selon le serveur et évoluent : la skill `figma-design-context` impose de vérifier la liste réelle avant tout appel, et documente le repli sans MCP. Quotas et accès : https://developers.figma.com/docs/figma-mcp-server/

## Exemples d'usage

```text
Utilise skill-router : conçois et implémente un onboarding bancaire accessible pour iOS.
→ product-requirements, interaction-design-spec, apple-hig-review, swiftui-implementation, apple-accessibility

Génère le handoff développeur de https://www.figma.com/design/<fileKey>/...?node-id=729-14491 en français, format Notion.
→ figma-design-context, figma-token-mapping, figma-implementation-spec

Vérifie le contraste #9CA3AF sur #FFFFFF.
→ accessibility-audit (python3 skills/quality/accessibility-audit/scripts/contrast.py "#9CA3AF" "#FFFFFF" → 2.54:1)

Revois cette PR React : composant PromoBanner.
→ frontend-code-review
```

Le routeur est aussi utilisable en ligne de commande :

```bash
python3 skills/ai-workflows/skill-router/scripts/route.py "Design and implement an accessible banking onboarding flow for iOS"
```

## Qualité et tests

```bash
python3 -m pip install pyyaml pytest
python3 scripts/validate_skills.py          # 10 quality gates
python3 scripts/build_registry.py --check   # registre à jour
python3 -m pytest -q tests                  # outillage, routeur, calcul de contraste, installeur
python3 scripts/check_links.py              # liens externes (réseau requis)
```

Les gates : spécification Agent Skills, frontmatter et métadonnées, liens relatifs, provenance (identifiants et domaines du registre des sources), doublons, sécurité (commandes dangereuses, injection de prompt, secrets, scripts non revus), licence, évaluations, complétude de la documentation, budget de taille. La CI (`.github/workflows/skills-ci.yml`) exécute aussi le validateur officiel `skills-ref` épinglé sur un commit revu, et vérifie les liens chaque semaine sans bloquer les PR.

## Contribuer

1. Lire [l'architecture](docs/architecture/skill-architecture.md) : structure, frontmatter, sections obligatoires, étiquettes de preuve, ordre de priorité.
2. Ajouter toute nouvelle source au [registre des sources](docs/sources/source-registry.md) avant de la citer.
3. Créer la skill sous `skills/<domaine>/<nom>/` avec `evals/evals.json` (au moins un cas, deux assertions).
4. Un script dans une skill doit être relu, sans dépendance ni réseau, listé dans `skills/.validator.json` et testé.
5. Lancer les trois commandes de qualité, régénérer le registre, ouvrir une PR.

Préférer 30 skills excellentes à 300 superficielles : une nouvelle skill doit couvrir un besoin qu'aucune autre ne couvre (le validateur signale les descriptions quasi identiques).

## Mettre à jour les skills

- Revoir les sources au moins tous les 6 mois et à chaque WWDC, Google I/O, nouvelle version WCAG, DTCG ou Figma MCP ; mettre à jour `metadata.last-reviewed` (le validateur avertit au-delà de 6 mois).
- Changement de comportement : version mineure ; changement de sortie attendue : version majeure.
- Consigner les exécutions d'évaluation dans `evals/RESULTS.md`.

## Dépannage

| Symptôme | Cause probable | Action |
|---|---|---|
| Une skill n'apparaît pas dans Claude Code | Arborescence par domaine non aplatie | `scripts/install-skills.sh --target <projet>/.claude/skills` |
| `You don't have edit access to this file` (Figma) | Fichier non partagé avec le compte, ou plan insuffisant | `whoami` pour diagnostiquer, demander l'accès au propriétaire |
| Aucun outil Figma listé | Serveur non connecté | `claude mcp list`, relancer Figma Desktop ou refaire l'OAuth |
| `Large MCP response` | Frame volumineuse | Normal ; passer par `get_metadata` puis des appels par section |
| Validateur : `Source ID ... not declared` | Source absente du registre | L'ajouter dans `docs/sources/source-registry.md` |
| Validateur : `Script ... not listed` | Script non revu | Le relire, le tester, l'ajouter à `skills/.validator.json` |

## Licence et attribution

Aucune licence n'est encore déclarée au niveau du dépôt (décision du propriétaire, voir l'audit). Les skills déclarent `license: MIT` dans leur frontmatter en attendant cette décision.

Les skills paraphrasent et citent leurs sources sans en copier la documentation ; voir le [registre des sources](docs/sources/source-registry.md) pour la provenance et les licences. Les frameworks cités par leur nom (Opportunity Solution Tree, RICE, HEART, SUS, Value Proposition Canvas...) appartiennent à leurs auteurs. Apple, Android, Material Design, Figma et WCAG sont des marques ou publications de leurs propriétaires respectifs.
