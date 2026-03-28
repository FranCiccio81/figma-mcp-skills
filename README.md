# figma-mcp-skills

> Agent Skills pour Claude Code + Figma MCP Server  
> Couvre l'ensemble du process design : système de design, design-to-code, UX specs, accessibilité.

## Prérequis

- Claude Code installé (`npm install -g @anthropic-ai/claude-code`)
- Figma Desktop App (dernière version)
- Seat Dev ou Full sur un plan Figma payant
- Claude Pro ou Max

## Setup rapide

### 1. Activer le MCP Desktop dans Figma

1. Ouvrir Figma Desktop
2. Ouvrir un fichier de design
3. Activer le **Dev Mode** (`Shift + D`)
4. Dans le panneau Inspect → section **MCP server** → cliquer **Enable desktop MCP server**
5. Le serveur tourne sur `http://127.0.0.1:3845/mcp`

### 2. Connecter Claude Code au MCP Figma

```bash
# Ajouter le serveur desktop (recommandé — sélection directe dans Figma)
claude mcp add --transport http figma-desktop http://127.0.0.1:3845/mcp

# Vérifier la connexion
claude mcp list
```

### 3. Cloner ce repo dans ton projet

```bash
git clone https://github.com/TON_USERNAME/figma-mcp-skills.git
cd figma-mcp-skills
```

### 4. Copier les rules dans ton projet

```bash
# Copier CLAUDE.md à la racine de ton projet
cp .claude/CLAUDE.md /chemin/vers/ton-projet/.claude/CLAUDE.md
```

## Structure

```
figma-mcp-skills/
├── .mcp.json                           # Config MCP prête à l'emploi
├── .claude/
│   └── CLAUDE.md                       # Rules globales pour Claude Code
├── skills/
│   ├── 01-design-system/
│   │   └── SKILL.md                    # Bridge tokens, composants, tier hierarchy
│   ├── 02-design-to-code/
│   │   └── SKILL.md                    # Figma → React / Jetpack Compose
│   ├── 03-ux-research-specs/
│   │   └── SKILL.md                    # Annotations, flows, specs fonctionnelles
│   └── 04-accessibility/
│       └── SKILL.md                    # WCAG 2.1 AA, audits, ARIA patterns
└── rules/
    ├── figma-mcp-rules.md              # Rules MCP universelles
    └── bridge-design-system-rules.md  # Rules spécifiques Bridge / Swissquote
```

## Utilisation avec Claude Code

```bash
# Lancer Claude Code dans ton projet
cd /chemin/vers/ton-projet
claude

# Vérifier que Figma MCP est connecté
/mcp

# Exemples de prompts
"Implémente ce composant depuis ma sélection Figma en React avec les tokens Bridge"
"Extrait les variables de couleur de cette frame et mappe-les sur les tokens Bridge"
"Génère le code Jetpack Compose pour ma sélection Figma en suivant MD3"
"Audite cette frame pour la conformité WCAG 2.1 AA"
```

## Outils MCP disponibles

| Outil | Description |
|---|---|
| `get_design_context` | Contexte complet (layout, spacing, couleurs, typo) |
| `get_variable_defs` | Variables et tokens de la sélection |
| `get_screenshot` | Capture visuelle pour validation |
| `get_metadata` | Structure XML des layers (utile pour grands fichiers) |
| `get_code_connect_map` | Mapping composants Figma ↔ code |
| `create_design_system_rules` | Génère un fichier de rules depuis ton DS |
| `get_figjam` | Lit les diagrammes FigJam |

## Plans & limites Figma

| Plan | Quota MCP |
|---|---|
| Starter / Viewer | 6 appels/mois |
| Dev ou Full seat (Professional+) | Rate limits API Tier 1 |
