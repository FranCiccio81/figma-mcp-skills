# Composant Input — Documentation Handoff
**Design System :** Foundations – Laboratoire Innotech International
**Dernière mise à jour :** 2026-03-28
**Fichier Figma :** `YMXQcB0QWivNJGwH3jJUI7` · Frame `Input` (node `729:14488`)

---

## 1. Vue d'ensemble du composant Input

### Rôle et usage
Le composant `Input` est le champ de saisie de texte de base du design system. Il structure la collecte de données utilisateur (formulaires, recherches, filtres). Il se décompose en trois sous-composants imbriqués :

| Couche | Nom Figma | Rôle |
|--------|-----------|------|
| 1 — Contenu | `base.input-content` | Zone interne : icônes + texte (placeholder / valeur) |
| 2 — Style | `base.input-style` | Enveloppe visuelle : fond, bordure, ombre d'état |
| 3 — Complet | `Input` | Assemblage final avec label et caption |

### Variantes présentes
Le composant utilise un style unique (outlined) — pas de variante `filled-background` ou `underline` distincte. La section `base.input-style` documente les **états** comme des variantes, pas des styles distincts.

### Tailles disponibles

| Taille | Hauteur du champ | Padding horizontal | Taille icône |
|--------|------------------|--------------------|--------------|
| **Micro** | ~28 px | 8 px | 16 px |
| **Small** | 32 px | 12 px | 20 px |
| **Default** | 40 px | 12 px | 24 px |
| **Large** | 56 px | 16 px | 24 px |

---

## 2. Anatomie du composant

### Éléments constitutifs

| Élément | Description | Token associé |
|---------|-------------|---------------|
| **Label** | Texte au-dessus du champ, semi-bold | `Paragraph 01–03/Semi Bold` selon la taille · couleur `Grey/900` |
| **Icône gauche (leading)** | SVG optionnel aligné à gauche de la zone de saisie | Couleur héritée du contexte ; taille selon la taille du composant |
| **Placeholder** | Texte indicatif affiché quand le champ est vide | Couleur `Grey/500` (Default/Small/Micro) ; `Grey/400` (Disabled) |
| **Valeur saisie (content)** | Texte entré par l'utilisateur | Couleur `Grey/900` (actif) ; `Grey/700` (Disabled Default) ; `Grey/600` (Disabled Large) |
| **Icône droite (trailing)** | SVG optionnel aligné à droite | Même règle que l'icône gauche |
| **Bordure** | Contour de l'input | Couleur variable selon l'état (voir §3) ; épaisseur `1 px` |
| **Fond** | Background du champ | `Shades/White` (défaut) ; `Grey/100` (Disabled) ; `Danger/50` (Error) |
| **Caption / Helper text** | Texte d'aide sous le champ | `Caption/Regular` (12 px) · couleur `Grey/400` |
| **Message d'erreur** | Remplace la caption en état Error | `Caption/Regular` (12 px) · couleur `Danger/500` |
| **Ombre d'interaction** | Box-shadow sur Hover et Focus | Token `Input/Hover` ou `Input/Focus` |

### Configurations d'icônes (showcase)
- Default (sans icône)
- Single Icon Trailing (icône droite uniquement)
- Single Icon Leading (icône gauche uniquement)
- Both Icons (icône gauche + droite)

---

## 3. États documentés

| État | Description visuelle | Tokens spécifiques |
|------|---------------------|-------------------|
| **Default** | Fond blanc, bordure grise | bg: `Shades/White` · border: `Grey/300` |
| **Hover** | Fond blanc, bordure gris moyen, halo gris clair | border: `Grey/400` · shadow: `Input/Hover` (`#E5E5E5` à 60%, spread 4 px) |
| **Focus / Pressed** | Fond blanc, bordure bleue, halo bleu translucide | border: `Primary/500` (#3B82F6) · shadow: `Input/Focus` (`#3B82F6` à 10%, spread 4 px) |
| **Filled** | Fond blanc, bordure grise — identique à Default | bg: `Shades/White` · border: `Grey/300` · text: `Grey/900` |
| **Error** | Fond rouge très clair, bordure rouge | bg: `Danger/50` · border: `Danger/500` · caption: `Danger/500` |
| **Disabled** | Fond gris clair, bordure gris très clair, texte atténué | bg: `Grey/100` · border: `Grey/200` · placeholder: `Grey/400` · content: `Grey/700`/`Grey/600` |
| **Read-only** | ⚠️ Non documenté dans la frame — à confirmer | — |

> **Note :** L'état `Focus` est nommé `Pressed` dans Figma. Il correspond visuellement à l'état `:focus` / `:focus-visible` en CSS.

---

## 4. Tokens utilisés

### Couleurs

| Usage | Token | Valeur hex |
|-------|-------|-----------|
| Border — Default / Filled | `Grey/300` | `#D1D5DB` |
| Border — Hover | `Grey/400` | `#9CA3AF` |
| Border — Focus | `Primary/500` | `#3B82F6` |
| Border — Error | `Danger/500` | `#EF4444` |
| Border — Disabled | `Grey/200` | `#E5E7EB` |
| Background — Default | `Shades/White` | `#FFFFFF` |
| Background — Error | `Danger/50` | `#FEF2F2` |
| Background — Disabled | `Grey/100` | `#F3F4F6` |
| Placeholder — actif | `Grey/500` | `#6B7280` |
| Placeholder — disabled | `Grey/400` | `#9CA3AF` |
| Valeur saisie — actif | `Grey/900` | `#111827` |
| Valeur saisie — disabled (Default) | `Grey/700` | `#374151` |
| Valeur saisie — disabled (Large) | `Grey/600` | `#4B5563` |
| Label | `Grey/900` | `#111827` |
| Caption — neutre | `Grey/400` | `#9CA3AF` |
| Caption — erreur | `Danger/500` | `#EF4444` |

### Effets (ombres d'interaction)

| Token | Type | Couleur | Offset | Radius | Spread |
|-------|------|---------|--------|--------|--------|
| `Input/Hover` | Drop Shadow | `#E5E5E5` à 60% | 0, 0 | 0 | 4 px |
| `Input/Focus` | Drop Shadow | `#3B82F6` à 10% | 0, 0 | 0 | 4 px |

### Espacement et dimensions

| Usage | Valeur | Statut token |
|-------|--------|-------------|
| Padding horizontal — Micro | 8 px | ⚠️ Hardcodé |
| Padding horizontal — Default / Small | 12 px | ⚠️ Hardcodé |
| Padding horizontal — Large | 16 px | ⚠️ Hardcodé |
| Padding vertical texte — Default / Small | 9 px (top + bottom) | ⚠️ Hardcodé |
| Padding vertical texte — Micro | 6 px | ⚠️ Hardcodé |
| Padding vertical texte — Large | 21 px | ⚠️ Hardcodé |
| Gap label → champ → caption | 8 px | ⚠️ Hardcodé |
| Border width | 1 px | ⚠️ Hardcodé |

### Typographie

| Élément | Token | Taille / Graisse / Line-height |
|---------|-------|-------------------------------|
| Label — Default | `Paragraph 02/Semi Bold` | 16 px / 600 / 24 px |
| Label — Large | `Paragraph 03/Semi Bold` | 18 px / 600 / 22 px |
| Label — Small / Micro | `Paragraph 01/Semi Bold` | 14 px / 600 / 16 px |
| Placeholder / Valeur — Default | `Paragraph 02/Regular` | 16 px / 400 / 24 px |
| Placeholder / Valeur — Large | `Paragraph 03/Regular` | 18 px / 400 / 24 px |
| Placeholder / Valeur — Small / Micro | `Paragraph 01/Regular` | 14 px / 400 / 16 px |
| Caption / Message d'erreur | `Caption/Regular` | 12 px / 400 / 18 px |

### Border radius

| Élément | Valeur | Statut token |
|---------|--------|-------------|
| Wrapper externe (`base.input-style`) | 2 px | ⚠️ Hardcodé |
| Container interne (`base.input-content`) | 4 px | ⚠️ Hardcodé |

> **⚠️ Valeurs hardcodées à tokeniser :** border-radius, paddings, gaps, border-width. Aucun token d'espacement ou de radius n'est présent dans les variables Figma actuelles.

---

## 5. Comportements interactifs

| Comportement | Détail | À confirmer |
|---|---|---|
| **Transition focus** | Aucune durée définie dans les frames statiques | ✅ À définir (recommandé : `150–200 ms ease-in-out`) |
| **Apparition du halo** | `box-shadow` spread sur Hover et Focus — pas d'animation définie | ✅ À confirmer |
| **Label** | **Statique** — le label reste au-dessus du champ en permanence, pas de floating label | Confirmé |
| **Placeholder vs valeur** | Le placeholder disparaît dès que l'utilisateur saisit. L'état `Filled` montre le contenu avec une bordure identique à Default | Confirmé |
| **Affichage des erreurs** | Déclenché côté produit. La caption se colore en `Danger/500` et le fond/bordure passent en rouge | ✅ Timing à définir (onBlur / onChange / onSubmit) |
| **Icônes interactives** | Les icônes trailing semblent fonctionnelles (ex. : croix pour effacer, œil pour mot de passe) — non documentées dans cette frame | ✅ À spécifier |

---

## 6. Accessibilité

### Checklist ARIA / sémantique

| Point | Recommandation |
|-------|---------------|
| Association label ↔ input | `<label htmlFor="inputId">` ou `aria-labelledby="labelId"` — **obligatoire** |
| Helper text | `aria-describedby="captionId"` sur l'`<input>` |
| Message d'erreur | `aria-describedby="errorId"` (peut cumuler caption + erreur avec deux IDs) |
| État erreur | `aria-invalid="true"` quand l'état Error est actif |
| Champ obligatoire | `aria-required="true"` ou attribut `required` |
| Champ désactivé | `disabled` HTML (pas seulement `aria-disabled`) |
| Champ lecture seule | `readonly` + `aria-readonly="true"` |

### Contraste — analyse

| Élément | Couleur texte | Fond | Ratio estimé | WCAG AA (4.5:1) |
|---------|--------------|------|--------------|-----------------|
| Valeur saisie (actif) | `Grey/900` #111827 | White #FFFFFF | ~18.1:1 | ✅ Conforme |
| Label | `Grey/900` #111827 | Fond page | ~18.1:1 | ✅ Conforme |
| Caption | `Grey/400` #9CA3AF | White #FFFFFF | ~2.85:1 | ❌ **Non conforme** |
| Placeholder | `Grey/500` #6B7280 | White #FFFFFF | ~4.48:1 | ⚠️ Limite — à vérifier |
| Placeholder disabled | `Grey/400` #9CA3AF | `Grey/100` #F3F4F6 | ~2.43:1 | ❌ Acceptable pour disabled |

> **⚠️ Action requise :** La `caption` (Grey/400 sur blanc) passe sous le seuil WCAG AA. Envisager `Grey/500` (#6B7280) minimum.

### Touch target

| Taille | Hauteur champ | Touch target minimum (44 px) |
|--------|--------------|------------------------------|
| Micro | ~28 px | ❌ Insuffisant |
| Small | 32 px | ❌ Insuffisant |
| Default | 40 px | ⚠️ Limite |
| Large | 56 px | ✅ Conforme |

---

## 7. Checklist handoff developer

- [ ] Tous les états présents — Default, Hover, Focus, Filled, Error, Disabled ✅ · Read-only ❌ manquant
- [ ] Tokens mappés — Couleurs ✅ · Effets ✅ · Typographie ✅ · Espacement/radius ❌ hardcodés
- [ ] Message d'erreur — contenu ✅ · positionnement sous le champ ✅
- [ ] Configurations d'icônes — 4 variantes documentées ✅
- [ ] Styles d'étiquetage — 4 combinaisons documentées ✅
- [ ] Comportement responsive — non documenté ❌ à définir
- [ ] Cas edge :
  - [ ] Texte très long dans label / valeur (overflow / ellipsis ?)
  - [ ] Copier-coller et autofill navigateur (`:autofill` / `:-webkit-autofill`)
  - [ ] Input `password`, `email`, `number` — comportements navigateur spécifiques
- [ ] Contraste caption (Grey/400) à corriger
- [ ] Touch targets Micro et Small à régler pour mobile

---

## 8. Questions ouvertes

| # | Question | Criticité |
|---|----------|-----------|
| 1 | L'état **Read-only** existe-t-il ? Différence visuelle avec Disabled ? | Haute |
| 2 | Les icônes trailing sont-elles interactives (effacer, toggle password) ? | Haute |
| 3 | Quel est le **timing de validation** (onBlur / onChange / onSubmit) ? | Haute |
| 4 | La **largeur** est-elle fixe ou fluide (100% du conteneur parent) ? | Haute |
| 5 | Quelle est la **durée et l'easing** des transitions entre états ? | Moyenne |
| 6 | Le double border-radius (2 px outer / 4 px inner) est-il intentionnel ? | Moyenne |
| 7 | Faut-il un **compteur de caractères** (ex. : `12/100`) ? | Moyenne |
| 8 | La caption en `Grey/400` ne passe pas WCAG AA — décision assumée ou à corriger ? | Haute |
| 9 | Tailles Micro/Small < 44 px — usage desktop uniquement ou zone tactile à étendre ? | Haute |
| 10 | Le style `:autofill` navigateur (fond jaune Chrome) est-il géré ? | Basse |
