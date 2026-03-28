# SKILL : Design System — Tokens, Composants & Bridge

> Skill pour travailler avec un design system structuré en 4 tiers de tokens,  
> compatible Tokens Studio, Style Dictionary, et le design system Bridge de Swissquote.

---

## ✅ Validé en conditions réelles — Learnings du test (2026-03-28)

> Test effectué sur la frame `Input` du fichier **Foundations – Laboratoire Innotech International**

### Ce que le MCP révèle automatiquement sur les tokens

**Détection des valeurs hardcodées :** Le MCP identifie précisément les éléments non liés à des variables Figma. Sur le test Input, 8 valeurs hardcodées ont été détectées automatiquement :
- `border-radius` : 2px (wrapper) et 4px (inner container)
- Paddings internes par taille : 8px / 12px / 16px
- Gap label → champ → caption : 8px
- Border width : 1px

**Ce que `get_variable_defs` retourne réellement :**
```json
{
  "Shades/ Black": "#000000",
  "Shades/ White": "#FFFFFF",
  "Grey/100": "#F3F4F6",
  "Grey/200": "#E5E7EB",
  "Grey/300": "#D1D5DB",
  "Grey/400": "#9CA3AF",
  "Grey/500": "#6B7280",
  ...
}
```
→ Uniquement les variables Figma liées à la sélection, avec leur valeur hex résolue. Pas les tokens non utilisés.

**Anatomie de composant imbriqué détectée automatiquement :**
Le MCP a correctement identifié la structure 3 couches du composant Input :
```
Input (assemblage final)
  └── base.input-style (enveloppe visuelle)
        └── base.input-content (zone de saisie)
```

### Warning Code Connect — à ne pas confondre

Quand aucun Code Connect n'est configuré, le MCP affiche :
```
Components in the design the user selected is missing code connect mappings.
Please ask the user if they would like to map these components.
```
→ **Ignorer ce message** pour les tâches de documentation/specs. Il n'impacte pas la qualité du handoff.

---

## Contexte & périmètre

Ce skill couvre :
- L'architecture des tokens (4 tiers)
- La création et la maintenance de composants
- L'audit et la migration de tokens existants
- La génération de documentation de design system
- Le travail avec Code Connect pour mapper Figma ↔ code

---

## Architecture des tokens — 4 tiers

```
Tier 1 — Core (primitives)
  └── Valeurs brutes : #0057FF, 16px, 400, "Inter"
      Jamais utilisées directement dans les composants

Tier 2 — Semantic (aliases)
  └── Signification fonctionnelle : color.action.primary, spacing.md, text.body
      Pointent vers des tokens Core

Tier 3 — Component (spécifiques)
  └── Contexte précis : button.primary.background, input.border.focus
      Pointent vers des tokens Semantic

Tier 4 — Breakpoint (responsive)
  └── Variantes responsive : spacing.md.mobile, grid.columns.tablet
      Pointent vers des tokens Core ou Semantic
```

### Conventions de nommage

```
[catégorie].[sous-catégorie].[état].[modificateur]

Exemples :
  color.action.primary.default
  color.action.primary.hover
  color.feedback.error.background
  spacing.component.button.padding-x
  typography.body.size
  radius.button.default
  shadow.card.default
  motion.duration.fast
```

---

## Flux MCP pour les tokens

### Extraire les tokens d'une frame Figma

```
Prompt : "Get the variables used in my Figma selection and map them to Bridge token names"

Outils appelés automatiquement :
1. get_variable_defs → liste les variables Figma
2. get_design_context → contexte complet avec les valeurs
```

### Mapper des tokens Figma vers Style Dictionary

```json
// Output attendu (Style Dictionary format)
{
  "color": {
    "action": {
      "primary": {
        "default": { "value": "{core.blue.600}", "type": "color" },
        "hover": { "value": "{core.blue.700}", "type": "color" }
      }
    }
  }
}
```

### Prompts types pour les tokens

```
"Extrait tous les tokens de couleur de cette frame et génère le fichier JSON Style Dictionary"
"Audite cette frame : quels tokens hardcodés ne sont pas liés à des variables Figma ?"
"Génère la liste des tokens manquants pour ce composant en les comparant aux tokens Bridge existants"
"Crée les tokens semantic pour cette nouvelle palette de couleurs Core"
```

---

## Création de composants

### Structure Atomic Design

```
atoms/
  Button/
    Button.tsx
    Button.stories.tsx
    Button.test.tsx
    index.ts
molecules/
  Card/
    Card.tsx
    Card.stories.tsx
    index.ts
organisms/
  Header/
    Header.tsx
    index.ts
```

### Flux MCP pour générer un composant

```
1. Sélectionner le composant dans Figma (Dev Mode activé)
2. Prompt : "Implémente ce composant depuis ma sélection Figma"

Flux automatique :
  get_design_context → structure React + Tailwind
  get_screenshot → validation visuelle
  get_variable_defs → tokens utilisés
  get_code_connect_map → composants existants à réutiliser
```

### Template composant React + tokens Bridge

```tsx
import { tokens } from '@bridge/tokens'

interface ButtonProps {
  variant: 'primary' | 'secondary' | 'ghost'
  size: 'sm' | 'md' | 'lg'
  disabled?: boolean
  children: React.ReactNode
  onClick?: () => void
}

/**
 * Button — Bridge Design System
 * @see https://figma.com/file/[BRIDGE_FILE_ID]
 */
export const Button = ({ variant, size, disabled, children, onClick }: ButtonProps) => {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      aria-disabled={disabled}
      className={`button button--${variant} button--${size}`}
    >
      {children}
    </button>
  )
}
```

### Conventions BEM + tokens

```scss
.button {
  // Toujours des tokens, jamais de valeurs hardcodées
  border-radius: var(--radius-button-default);
  font-family: var(--typography-label-font-family);
  transition: background-color var(--motion-duration-fast);

  &--primary {
    background: var(--color-action-primary-default);
    color: var(--color-text-on-primary);

    &:hover { background: var(--color-action-primary-hover); }
    &:focus-visible { outline: 2px solid var(--color-focus-ring); }
    &:disabled { background: var(--color-action-disabled); }
  }
}
```

---

## Code Connect — Mapping Figma ↔ code

### Configurer Code Connect

```bash
# Installer Code Connect
npm install @figma/code-connect

# Générer les mappings depuis Figma
npx figma connect create

# Publier les mappings
npx figma connect publish
```

### Exemple de fichier Code Connect

```tsx
// Button.figma.tsx
import figma from '@figma/code-connect'
import { Button } from './Button'

figma.connect(Button, 'https://figma.com/file/[ID]?node-id=[NODE]', {
  props: {
    variant: figma.enum('Variant', {
      'Primary': 'primary',
      'Secondary': 'secondary',
      'Ghost': 'ghost',
    }),
    size: figma.enum('Size', {
      'Small': 'sm',
      'Medium': 'md',
      'Large': 'lg',
    }),
    disabled: figma.boolean('Disabled'),
    children: figma.string('Label'),
  },
  example: ({ variant, size, disabled, children }) => (
    <Button variant={variant} size={size} disabled={disabled}>
      {children}
    </Button>
  ),
})
```

### Prompts MCP avec Code Connect actif

```
"Génère ce composant en utilisant les composants existants de src/components/ui"
"Vérifie si ce node Figma a un Code Connect configuré avant de générer du code"
"Liste tous les composants Figma qui n'ont pas encore de Code Connect"
```

---

## Audit de design system

### Checklist d'audit via Claude Code

```
Prompt : "Audite ce fichier Figma et identifie :
  1. Les layers avec des valeurs hardcodées (pas de variables)
  2. Les composants non liés à la librairie Bridge
  3. Les écarts de typographie non conformes à la scale
  4. Les couleurs qui ne matchent pas les tokens Core"
```

### Migration tokens — ancien format → 4 tiers

```
Prompt : "J'ai cet ancien token : primary-blue: #0057FF
  Génère la migration complète vers la hiérarchie 4 tiers Bridge :
  - Core token
  - Semantic alias
  - Component tokens associés
  - Documentation des usages"
```

---

## Documentation automatique

### Générer la doc d'un composant depuis Figma

```
Prompt : "Pour ce composant sélectionné dans Figma, génère :
  1. La description fonctionnelle
  2. La liste des props avec types TypeScript
  3. Les variantes disponibles
  4. Les tokens utilisés
  5. Les guidelines d'usage (do / don't)
  6. Un exemple de code complet"
```

### Format de documentation attendu

```markdown
## ComponentName

**Description** : Ce que fait le composant et quand l'utiliser.

**Props**
| Prop | Type | Default | Description |
|------|------|---------|-------------|
| variant | 'primary' \| 'secondary' | 'primary' | Style visuel |

**Tokens utilisés**
- `color.action.primary.default`
- `spacing.component.button.padding-x`

**Usage**
✅ À faire : Utiliser pour les actions principales
❌ À éviter : Ne pas utiliser pour la navigation

**Code**
\`\`\`tsx
<Button variant="primary">Confirmer</Button>
\`\`\`
```

---

## Commandes de référence rapide

```bash
# Lister les MCP servers connectés
claude mcp list

# Vérifier le statut dans Claude Code
/mcp

# Lancer Claude Code dans le projet Bridge
cd /chemin/bridge && claude
```

```
# Prompts essentiels design system

"Get the variables used in my Figma selection"
"Map this Figma component to the Bridge token system"
"Generate a complete component with Bridge tokens from my selection"
"Audit this frame for hardcoded values"
"Create Code Connect for all components in this page"
"Generate the Style Dictionary JSON for these Figma variables"
```
