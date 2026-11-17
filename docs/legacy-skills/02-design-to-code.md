# SKILL : Design-to-Code — Figma → React / Jetpack Compose

> Skill pour convertir des designs Figma en code production-ready,  
> ciblant React (web) et Jetpack Compose (Android / Material Design 3).

---

## ✅ Validé en conditions réelles — Learnings du test (2026-03-28)

> Test effectué sur la frame `Input` du fichier **Foundations – Laboratoire Innotech International**  
> Frame : 1697 × 4407 px · 4 sections · ~14k tokens MCP

### Stratégie de découpage automatique sur grande frame

Sur une frame > 800px de haut, Claude Code adopte automatiquement cette stratégie sans qu'on ait à le demander :

```
1. get_metadata sur la frame entière      → identifier les sections (node IDs)
2. get_design_context × N en parallèle   → une par section
3. get_screenshot                         → référence visuelle globale
4. get_variable_defs                      → tokens de toute la frame
```

**⚠️ Warning `Large MCP response (~14.0k tokens)`** : normal sur les grandes frames, ça n'indique pas une erreur. Claude Code continue correctement.

### Ce que `get_design_context` retourne concrètement

L'output est du **React + Tailwind** avec :
- Les assets en URL localhost : `http://localhost:3845/assets/[hash].svg`
- Les `data-node-id` sur chaque élément pour traçabilité
- Les styles inline en commentaire : `Grey/900: #111827, Headings/Heading 03/Extra Bold: Font(...)`

```jsx
// Exemple d'output réel
const imgVector = "http://localhost:3845/assets/5878d420d0a0a6329f7ad4839e5c551e9b7f5b7d.svg";

<div data-node-id="729:14491" className="flex flex-col gap-2">
  <label className="text-sm font-semibold text-gray-900">Label</label>
  <div className="border border-gray-300 rounded px-3 py-2">
    <input placeholder="Placeholder" className="text-gray-500" />
  </div>
</div>
```

→ **Ne jamais utiliser ce code directement.** Le convertir vers les tokens et conventions du projet.

### Nommage Figma → mapping CSS — pattern détecté

| Nom Figma | Valeur | Token CSS attendu |
|-----------|--------|-------------------|
| `Grey/900` | `#111827` | `--color-text-primary` |
| `Grey/300` | `#D1D5DB` | `--color-border-default` |
| `Primary/500` | `#3B82F6` | `--color-action-primary` |
| `Danger/500` | `#EF4444` | `--color-feedback-error` |
| `Input/Focus` | shadow `#3B82F6` 10% | `--shadow-input-focus` |

### Piège double border-radius

Sur le composant Input, deux `border-radius` différents ont été détectés :
- Wrapper externe : `2px`
- Container interne : `4px`

→ Toujours vérifier les composants imbriqués — le `border-radius` visible peut ne pas être celui du layer racine.

---

## Contexte & périmètre

Ce skill couvre :
- La conversion Figma → React avec tokens Bridge
- La conversion Figma → Jetpack Compose (MD3)
- Le mapping typographie Figma → Material Design 3
- Les patterns de composants adaptatifs (responsive / multi-breakpoint)
- La gestion des assets (images, icônes, SVG)
- Les workflows de validation pixel-perfect

---

## Flux MCP — Procédure obligatoire

**Ne jamais sauter ces étapes. Dans cet ordre.**

```
Étape 1 : get_design_context
  → Structure complète : layout, spacing, couleurs, typo, composants

Étape 2 : get_screenshot
  → Référence visuelle pour la validation finale

Étape 3 : get_variable_defs (si tokens présents)
  → Noms des variables Figma à mapper sur les tokens du projet

Étape 4 : get_code_connect_map (si Code Connect configuré)
  → Composants existants à réutiliser

Étape 5 : Implémentation
  → En respectant les conventions du projet

Étape 6 : Validation
  → Comparaison visuelle screenshot vs rendu
```

**Si la frame est grande :** utiliser `get_metadata` d'abord pour la structure,  
puis `get_design_context` sur les nodes spécifiques.

---

## React — Patterns d'implémentation

### Prompt type — Composant isolé

```
"Implémente ce composant depuis ma sélection Figma en React TypeScript.
Utilise les tokens Bridge depuis @bridge/tokens.
Respecte la structure de fichiers src/components/[atom|molecule|organism].
Ne génère pas de valeurs hardcodées."
```

### Prompt type — Page complète

```
"Implémente cette page depuis ma sélection Figma.
Découpe en composants selon l'Atomic Design.
Réutilise les composants existants de src/components/ui.
Génère un fichier par composant dans le bon dossier."
```

### Prompt type — Variantes de composant

```
"Ce composant a 3 variantes dans Figma (Default, Hover, Disabled).
Génère le composant React avec les props correspondantes
et les états CSS gérés via les tokens Bridge."
```

### Structure de fichiers attendue

```
src/
  components/
    atoms/
      Button/
        index.ts          ← export public
        Button.tsx        ← composant
        Button.module.scss ← styles avec tokens
        Button.stories.tsx ← Storybook
        Button.test.tsx   ← tests
    molecules/
      Card/
        index.ts
        Card.tsx
        Card.module.scss
    organisms/
      ProductList/
        index.ts
        ProductList.tsx
```

### Template React complet

```tsx
// src/components/atoms/Button/Button.tsx
import React from 'react'
import styles from './Button.module.scss'
import clsx from 'clsx'

export type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'destructive'
export type ButtonSize = 'sm' | 'md' | 'lg'

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant
  size?: ButtonSize
  isLoading?: boolean
  leftIcon?: React.ReactNode
  rightIcon?: React.ReactNode
}

/**
 * Button component — Bridge Design System
 *
 * @example
 * <Button variant="primary" size="md" onClick={handleSubmit}>
 *   Confirmer
 * </Button>
 */
export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ variant = 'primary', size = 'md', isLoading, leftIcon, rightIcon, children, disabled, className, ...props }, ref) => {
    return (
      <button
        ref={ref}
        disabled={disabled || isLoading}
        aria-disabled={disabled || isLoading}
        aria-busy={isLoading}
        className={clsx(
          styles.button,
          styles[`button--${variant}`],
          styles[`button--${size}`],
          { [styles['button--loading']]: isLoading },
          className
        )}
        {...props}
      >
        {leftIcon && <span className={styles.button__icon} aria-hidden="true">{leftIcon}</span>}
        <span className={styles.button__label}>{children}</span>
        {rightIcon && <span className={styles.button__icon} aria-hidden="true">{rightIcon}</span>}
      </button>
    )
  }
)

Button.displayName = 'Button'
```

---

## Jetpack Compose — Patterns d'implémentation

### Contexte Material Design 3

```
Figma (Bridge/MD3)     →     Jetpack Compose
─────────────────────────────────────────────
Text Style "Body Large"  →   MaterialTheme.typography.bodyLarge
Color "Primary"          →   MaterialTheme.colorScheme.primary
Spacing 16dp             →   16.dp
Corner Radius 8          →   RoundedCornerShape(8.dp)
Elevation 2              →   CardDefaults.cardElevation(2.dp)
```

### Mapping typographie Figma → MD3

```
Figma Text Style        MD3 Token                    Usage
────────────────────────────────────────────────────────────
Display Large           displayLarge (57sp/64sp)     Hero titles
Display Medium          displayMedium (45sp/52sp)    Section headers
Display Small           displaySmall (36sp/44sp)     Sub-headers
Headline Large          headlineLarge (32sp/40sp)    Page titles
Headline Medium         headlineMedium (28sp/36sp)   Card titles
Headline Small          headlineSmall (24sp/32sp)    Widget titles
Title Large             titleLarge (22sp/28sp)       List headers
Title Medium            titleMedium (16sp/24sp)      Dialog titles
Title Small             titleSmall (14sp/20sp)       Captions importantes
Body Large              bodyLarge (16sp/24sp)        Corps de texte principal
Body Medium             bodyMedium (14sp/20sp)       Corps secondaire
Body Small              bodySmall (12sp/16sp)        Labels, footnotes
Label Large             labelLarge (14sp/20sp)       Boutons
Label Medium            labelMedium (12sp/16sp)      Chips, tabs
Label Small             labelSmall (11sp/16sp)       Badges
```

### Prompt type — Composant Compose

```
"Implémente ce composant depuis ma sélection Figma en Jetpack Compose.
Utilise MaterialTheme pour les couleurs, typography et shapes.
Respecte les tokens MD3 : colorScheme, typography, shapes.
Génère le fichier dans ui/components/[NomComposant].kt"
```

### Template Jetpack Compose complet

```kotlin
// ui/components/PrimaryButton.kt
package com.swissquote.bridge.ui.components

import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp

/**
 * PrimaryButton — Bridge Design System
 *
 * Correspond au composant Button/Primary dans Figma Bridge.
 * Utilise MaterialTheme.colorScheme.primary pour le fond,
 * MaterialTheme.colorScheme.onPrimary pour le texte.
 */
@Composable
fun PrimaryButton(
    text: String,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    enabled: Boolean = true,
    isLoading: Boolean = false,
    leadingIcon: (@Composable () -> Unit)? = null,
) {
    Button(
        onClick = onClick,
        enabled = enabled && !isLoading,
        modifier = modifier
            .height(48.dp)
            .semantics { },
        colors = ButtonDefaults.buttonColors(
            containerColor = MaterialTheme.colorScheme.primary,
            contentColor = MaterialTheme.colorScheme.onPrimary,
            disabledContainerColor = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.12f),
            disabledContentColor = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.38f),
        ),
        shape = MaterialTheme.shapes.small, // 4dp — Bridge spec
        contentPadding = PaddingValues(horizontal = 24.dp, vertical = 0.dp),
    ) {
        if (isLoading) {
            CircularProgressIndicator(
                modifier = Modifier.size(20.dp),
                color = MaterialTheme.colorScheme.onPrimary,
                strokeWidth = 2.dp
            )
        } else {
            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                leadingIcon?.invoke()
                Text(
                    text = text,
                    style = MaterialTheme.typography.labelLarge,
                )
            }
        }
    }
}

@Preview(showBackground = true)
@Composable
private fun PrimaryButtonPreview() {
    BridgeTheme {
        Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
            PrimaryButton(text = "Confirmer", onClick = {})
            PrimaryButton(text = "Chargement", onClick = {}, isLoading = true)
            PrimaryButton(text = "Désactivé", onClick = {}, enabled = false)
        }
    }
}
```

### Mapping couleurs Figma → MD3 colorScheme

```
Figma Variable              MD3 colorScheme Role
──────────────────────────────────────────────────
color.action.primary        primary
color.text.on-primary       onPrimary
color.action.primary.bg     primaryContainer
color.action.secondary      secondary
color.feedback.error        error
color.surface.default       surface
color.surface.variant       surfaceVariant
color.text.default          onSurface
color.border.default        outline
color.border.subtle         outlineVariant
```

---

## Gestion des assets

### Images depuis Figma MCP

```
Comportement MCP desktop :
- Les images sont servies en localhost : http://127.0.0.1:3845/assets/[hash].png
- TOUJOURS utiliser cette URL directement dans le code généré
- Ne JAMAIS créer de placeholders si une URL localhost est disponible

React :
  <img src="http://127.0.0.1:3845/assets/abc123.png" alt="Description" />

Compose :
  AsyncImage(model = "http://127.0.0.1:3845/assets/abc123.png", contentDescription = "Description")
```

### SVG / Icônes

```
- Les SVG retournés par MCP sont inline ou en URL localhost
- Ne pas importer de lib d'icônes externe si l'icône est dans le payload Figma
- React : utiliser directement le SVG inline ou <img src={localhostUrl} />
- Compose : utiliser painterResource ou AsyncImage selon la source
```

---

## Validation pixel-perfect

### Processus de validation

```
1. Générer le composant depuis Figma MCP
2. Lancer le dev server local
3. Comparer côte à côte : Figma screenshot vs rendu browser/device
4. Checklist :
   □ Spacing et padding corrects (vérifier avec l'inspecteur)
   □ Couleurs matchent les tokens (pas de dérive visuelle)
   □ Typographie : taille, poids, line-height, letter-spacing
   □ Border-radius conformes
   □ Ombres (box-shadow / elevation)
   □ États interactifs (hover, focus, active, disabled)
   □ Responsive : mobile, tablet, desktop
```

### Prompts de validation

```
"Compare ce screenshot Figma avec mon implémentation et liste les écarts"
"Vérifie que tous les tokens utilisés dans ce composant correspondent aux variables Figma"
"Génère les états manquants (hover, focus, disabled) pour ce composant"
```

---

## Responsive & breakpoints

### Breakpoints Bridge

```
mobile:   < 600px
tablet:   600px – 1024px
desktop:  > 1024px
wide:     > 1440px
```

### Prompt responsive

```
"Ce composant Figma a 3 versions (mobile/tablet/desktop).
Génère le code React responsive avec les breakpoints Bridge.
Utilise CSS custom properties pour les tokens de spacing responsive."
```

---

## Commandes de référence rapide

```bash
# Démarrer Claude Code dans le projet
cd mon-projet && claude

# Workflow type design-to-code
# 1. Sélectionner la frame dans Figma (Dev Mode)
# 2. Dans Claude Code :
"Implémente ma sélection Figma en React TypeScript avec les tokens Bridge"

# Pour Compose :
"Implémente ma sélection Figma en Jetpack Compose Material Design 3"

# Validation :
"Prends un screenshot de ma sélection Figma et compare avec src/components/Button/Button.tsx"
```
