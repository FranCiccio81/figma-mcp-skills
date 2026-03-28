# Bridge Design System Rules — Swissquote

> Rules spécifiques au design system Bridge de Swissquote.  
> À combiner avec les Figma MCP Rules universelles.

---

## Contexte Bridge

```
Bridge est le design system de Swissquote.
Il couvre les produits web (React) et mobile (Android Jetpack Compose, iOS SwiftUI).
Il est compatible Tokens Studio + Style Dictionary.
Les tokens suivent une hiérarchie 4 tiers : core → semantic → component → breakpoint.
```

---

## Rules tokens Bridge

```
## Bridge Design System — Token Rules

- Toujours utiliser les tokens Bridge, jamais de valeurs hardcodées
- Hiérarchie 4 tiers obligatoire :
    Tier 1 Core       : primitives (jamais utilisées directement dans les composants)
    Tier 2 Semantic   : alias fonctionnels (color.action.primary, spacing.md...)
    Tier 3 Component  : tokens spécifiques au composant (button.primary.background)
    Tier 4 Breakpoint : variantes responsive (spacing.md.mobile)
- Convention de nommage : [catégorie].[sous-catégorie].[état].[modificateur]
- Format CSS custom properties : var(--color-action-primary-default)
- Format JSON Style Dictionary : {"value": "{semantic.color.action.primary}", "type": "color"}
- Format Jetpack Compose : MaterialTheme.colorScheme.primary (via BridgeTheme)
```

---

## Rules composants Bridge

```
## Bridge — Component Rules

- Architecture Atomic Design : atoms → molecules → organisms → templates
- Nommage BEM pour les classes CSS
- Chaque composant doit avoir :
    - Le fichier composant principal (.tsx ou .kt)
    - L'index d'export (index.ts)
    - Les stories Storybook (.stories.tsx)
    - Les tests unitaires (.test.tsx)
    - Le fichier Code Connect (.figma.tsx) si lié à Figma
- Réutiliser les composants existants avant d'en créer de nouveaux
- Documenter avec JSDoc (React) ou KDoc (Kotlin)
```

---

## Rules accessibilité Bridge

```
## Bridge — Accessibility Rules

- Niveau de conformité cible : WCAG 2.1 AA (EN 301 549)
- Ratios de contraste minimaux :
    Texte standard : 4.5:1
    Texte large (≥18px ou ≥14px bold) : 3:1
    Composants UI et états : 3:1
    Focus ring : 3:1 vs arrière-plan adjacent
- Touch targets minimum : 44×44px sur mobile (48dp sur Android MD3)
- Navigation clavier obligatoire pour tous les éléments interactifs
- Focus ring toujours visible (jamais outline: none sans alternative)
- ARIA approprié pour tous les composants complexes
- Live regions pour les mises à jour dynamiques
```

---

## Rules Material Design 3 (Android)

```
## Bridge Android — MD3 Rules

- Utiliser BridgeTheme (wrapper de MaterialTheme) pour les tokens
- Mapping typographie Figma → MD3 :
    Display Large/Medium/Small → displayLarge/Medium/Small
    Headline Large/Medium/Small → headlineLarge/Medium/Small
    Title Large/Medium/Small → titleLarge/Medium/Small
    Body Large/Medium → bodyLarge/Medium
    Label Large/Medium/Small → labelLarge/Medium/Small
- Mapping couleurs via colorScheme Bridge → MD3 :
    color.action.primary → colorScheme.primary
    color.text.on-primary → colorScheme.onPrimary
    color.feedback.error → colorScheme.error
    color.surface.default → colorScheme.surface
- Touch targets : minimum 48dp (Button height minimum = 48.dp)
- Elevation via CardDefaults, ButtonDefaults, etc. (jamais hardcodée)
- Shapes via MaterialTheme.shapes (small/medium/large = 4/8/12dp Bridge)
```

---

## Structure fichiers Bridge (React)

```
src/
  components/
    atoms/           # Boutons, inputs, badges, icônes, chips
    molecules/       # Cards, form fields, list items, toasts
    organisms/       # Headers, nav, modals, data tables, forms
    templates/       # Layouts de pages
  tokens/
    core/            # Tokens primitifs
    semantic/        # Alias sémantiques
    component/       # Tokens de composants
  styles/
    global.scss      # Variables CSS globales (tokens exportés)
    reset.scss
    typography.scss
  utils/
    accessibility/   # Hooks a11y (useFocusTrap, useAnnounce, etc.)
    tokens/          # Helpers token resolution
```

---

## Structure fichiers Bridge (Android/Compose)

```
ui/
  theme/
    BridgeTheme.kt         # MaterialTheme wrapper
    BridgeColorScheme.kt   # colorScheme light + dark
    BridgeTypography.kt    # MD3 typography scale
    BridgeShapes.kt        # MD3 shapes
  components/
    atoms/
      PrimaryButton.kt
      SecondaryButton.kt
      InputField.kt
    molecules/
      CardComponent.kt
      ListItem.kt
    organisms/
      AppBar.kt
      BottomNav.kt
  tokens/
    BridgeTokens.kt        # Constantes de tokens core
```

---

## Prompts types Bridge

```
# Design System
"Génère ce composant Figma en React avec les tokens Bridge (4 tiers)"
"Mappe ces variables Figma sur les tokens Bridge semantic"
"Audite cette frame : quels composants ne sont pas de la librairie Bridge ?"
"Génère le Code Connect pour ce composant Bridge"

# Android / MD3
"Implémente ce composant Figma en Jetpack Compose avec BridgeTheme"
"Mappe cette typographie Figma sur le scale MD3 de Bridge"
"Génère le BridgeTheme depuis les variables Figma de cette page Tokens"

# Accessibilité
"Audite ce composant Bridge pour la conformité WCAG 2.1 AA"
"Génère les attributs ARIA complets pour ce composant Bridge complexe"
"Vérifie les ratios de contraste de tous les tokens de couleur Bridge"

# Documentation
"Génère la doc Storybook de ce composant Bridge depuis Figma"
"Crée les stories pour toutes les variantes de ce composant"
"Génère les critères d'acceptance pour cette feature Bridge"
```
