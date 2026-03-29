# SETUP — figma-mcp-skills

> 63 skills installés le 2026-03-29

## Architecture

```
~/.claude/skills/          → Skills globaux (symlinks vers ~/.agents/skills/)
~/figma-mcp-skills/skills/ → Skills projet (Figma/Design System)
skills-lock.json           → Registry des 59 skills installés via /skills
```

## Skills projet (4)

| Skill | Description |
|-------|-------------|
| `01-design-system` | Gestion du Design System Bridge |
| `02-design-to-code` | Conversion Figma → code React/Tailwind |
| `03-ux-research-specs` | Specs UX et handoff Figma |
| `04-accessibility` | Audit WCAG 2.1 AA |

## Skills globaux — ~/.claude/skills/ (17 symlinks)

| Skill | Source |
|-------|--------|
| `ai-image-generation` | ~/.agents/skills/ |
| `brainstorming` | ~/.agents/skills/ |
| `browser-use` | ~/.agents/skills/ |
| `component` | ~/.agents/skills/ |
| `copywriting` | ~/.agents/skills/ |
| `docx` | ~/.agents/skills/ |
| `frontend-design` | ~/.agents/skills/ |
| `marketing-psychology` | ~/.agents/skills/ |
| `notebooklm` | local (~/figma-mcp-skills/skills/) |
| `pdf` | ~/.agents/skills/ |
| `pptx` | ~/.agents/skills/ |
| `seo-audit` | ~/.agents/skills/ |
| `shadcn-ui` | ~/.agents/skills/ |
| `ui-ux-pro-max` | ~/.agents/skills/ |
| `vercel-composition-patterns` | ~/.agents/skills/ |
| `vercel-react-best-practices` | ~/.agents/skills/ |
| `xlsx` | ~/.agents/skills/ |

## Skills installés via skills-lock.json (59)

### Design & UX (14)

| # | Skill | Source | Catégorie |
|---|-------|--------|-----------|
| 1 | `design-everyday-things` | wondelai/skills | Principes design |
| 2 | `design-sprint` | wondelai/skills | Sprint design 5 jours |
| 3 | `frontend-design` | anthropics/skills | Interfaces production |
| 4 | `ios-hig-design` | wondelai/skills | Apple HIG |
| 5 | `microinteractions` | wondelai/skills | Micro-interactions UI |
| 6 | `refactoring-ui` | wondelai/skills | Audit visuel UI |
| 7 | `top-design` | wondelai/skills | Expériences web immersives |
| 8 | `ui-ux-pro-max` | nextlevelbuilder/ui-ux-pro-max-skill | Intelligence UI/UX complète |
| 9 | `ux-designer` | szilu/ux-designer-skill | Bonnes pratiques UX |
| 10 | `ux-heuristics` | wondelai/skills | Évaluation heuristique |
| 11 | `web-artifacts-builder` | anthropics/skills | Artefacts HTML multi-composants |
| 12 | `web-design-guidelines` | vercel-labs/agent-skills | Web Interface Guidelines |
| 13 | `web-typography` | wondelai/skills | Typographie web |
| 14 | `lean-ux` | wondelai/skills | UX lean / hypothèses |

### Développement & Architecture (10)

| # | Skill | Source | Catégorie |
|---|-------|--------|-----------|
| 1 | `clean-architecture` | wondelai/skills | Dependency Rule |
| 2 | `clean-code` | wondelai/skills | Code lisible/maintenable |
| 3 | `domain-driven-design` | wondelai/skills | DDD / Bounded Contexts |
| 4 | `high-perf-browser` | wondelai/skills | Performance web |
| 5 | `pragmatic-programmer` | wondelai/skills | DRY, orthogonalité |
| 6 | `refactoring-patterns` | wondelai/skills | Patterns de refactoring |
| 7 | `release-it` | wondelai/skills | Stabilité production |
| 8 | `shadcn-ui` | giuseppe-trisciuoglio/developer-kit | Composants shadcn/ui |
| 9 | `software-design-philosophy` | wondelai/skills | Deep modules |
| 10 | `system-design` | wondelai/skills | Systèmes distribués |

### React & Next.js (2)

| # | Skill | Source | Catégorie |
|---|-------|--------|-----------|
| 1 | `vercel-composition-patterns` | vercel-labs/agent-skills | Patterns composition React |
| 2 | `vercel-react-best-practices` | vercel-labs/agent-skills | Perf React/Next.js |

### Marketing & Growth (15)

| # | Skill | Source | Catégorie |
|---|-------|--------|-----------|
| 1 | `blue-ocean-strategy` | wondelai/skills | Stratégie océan bleu |
| 2 | `contagious` | wondelai/skills | Viralité / STEPPS |
| 3 | `copywriting` | coreyhaines31/marketingskills | Copy marketing |
| 4 | `cro-methodology` | wondelai/skills | Optimisation conversion |
| 5 | `crossing-the-chasm` | wondelai/skills | Adoption technologique |
| 6 | `hundred-million-offers` | wondelai/skills | Offres irrésistibles |
| 7 | `influence-psychology` | wondelai/skills | 6 principes persuasion |
| 8 | `made-to-stick` | wondelai/skills | Messages mémorables |
| 9 | `marketing-psychology` | coreyhaines31/marketingskills | Psychologie marketing |
| 10 | `obviously-awesome` | wondelai/skills | Positionnement produit |
| 11 | `one-page-marketing` | wondelai/skills | Plan marketing complet |
| 12 | `predictable-revenue` | wondelai/skills | Ventes B2B outbound |
| 13 | `scorecard-marketing` | wondelai/skills | Quiz funnels |
| 14 | `seo-audit` | coreyhaines31/marketingskills | Audit SEO |
| 15 | `storybrand-messaging` | wondelai/skills | Messaging narratif |

### Produit & Stratégie (10)

| # | Skill | Source | Catégorie |
|---|-------|--------|-----------|
| 1 | `continuous-discovery` | wondelai/skills | Discovery continue |
| 2 | `design-sprint` | wondelai/skills | Sprint design |
| 3 | `drive-motivation` | wondelai/skills | Motivation AMP |
| 4 | `hooked-ux` | wondelai/skills | Boucles d'engagement |
| 5 | `improve-retention` | wondelai/skills | Rétention B=MAP |
| 6 | `inspired-product` | wondelai/skills | Équipes produit |
| 7 | `jobs-to-be-done` | wondelai/skills | JTBD |
| 8 | `lean-startup` | wondelai/skills | MVP / Build-Measure-Learn |
| 9 | `mom-test` | wondelai/skills | Interviews clients |
| 10 | `traction-eos` | wondelai/skills | EOS / V/TO |

### Négociation & Communication (1)

| # | Skill | Source | Catégorie |
|---|-------|--------|-----------|
| 1 | `negotiation` | wondelai/skills | Empathie tactique |

### Documents & Fichiers (4)

| # | Skill | Source | Catégorie |
|---|-------|--------|-----------|
| 1 | `docx` | anthropics/skills | Word documents |
| 2 | `pdf` | anthropics/skills | PDF manipulation |
| 3 | `pptx` | anthropics/skills | PowerPoint |
| 4 | `xlsx` | anthropics/skills | Spreadsheets |

### Agents & Outils (3)

| # | Skill | Source | Catégorie |
|---|-------|--------|-----------|
| 1 | `brainstorming` | obra/superpowers | Brainstorming créatif |
| 2 | `context-engineering-collection` | muratcankoylan/Agent-Skills-for-Context-Engineering | Context engineering |
| 3 | `skill-creator` | anthropics/skills | Créer/modifier des skills |

## Sources

| Source | Nombre | Type |
|--------|--------|------|
| `wondelai/skills` | 35 | Business, UX, Architecture |
| `anthropics/skills` | 7 | Documents, Frontend, Outils |
| `coreyhaines31/marketingskills` | 3 | Marketing |
| `vercel-labs/agent-skills` | 3 | React, Web Guidelines |
| `nextlevelbuilder/ui-ux-pro-max-skill` | 1 | UI/UX |
| `giuseppe-trisciuoglio/developer-kit` | 1 | shadcn/ui |
| `szilu/ux-designer-skill` | 1 | UX |
| `obra/superpowers` | 1 | Brainstorming |
| `muratcankoylan/Agent-Skills-for-Context-Engineering` | 1 | Agents |
| Projet local | 4 | Figma/Design System |
| **Total** | **63** | |

## MCP Server

```json
{
  "mcpServers": {
    "figma-desktop": {
      "type": "sse",
      "url": "http://127.0.0.1:3845/sse"
    }
  }
}
```

## Commandes rapides

```bash
# Lister les skills disponibles
/skills

# Utiliser un skill
/component spec          # Spec composant depuis Figma
/copywriting             # Rédaction marketing
/brainstorming           # Session créative
/pdf                     # Manipulation PDF
/seo-audit               # Audit SEO
```
