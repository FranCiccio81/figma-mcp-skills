# SKILL : Accessibilité — WCAG 2.1 AA

> Skill pour auditer, corriger et documenter l'accessibilité des designs et du code,  
> en conformité WCAG 2.1 niveau AA — obligatoire pour les produits financiers (FINMA, EN 301 549).

---

## ✅ Validé en conditions réelles — Learnings du test (2026-03-28)

> Audit automatique détecté sur le composant `Input` — Laboratoire Innotech International

### Problèmes détectés automatiquement par Claude Code via MCP

| Critère WCAG | Élément | Problème détecté | Sévérité |
|---|---|---|---|
| 1.4.3 Contraste | Caption `Grey/400` sur blanc | Ratio 2.85:1 — seuil AA = 4.5:1 | ❌ Fail |
| 1.4.3 Contraste | Placeholder `Grey/500` sur blanc | Ratio 4.48:1 — limite | ⚠️ Borderline |
| 2.5.5 Touch Target | Taille Micro (28px) | Sous les 44px requis mobile | ❌ Fail |
| 2.5.5 Touch Target | Taille Small (32px) | Sous les 44px requis mobile | ❌ Fail |
| 2.5.5 Touch Target | Taille Default (40px) | Limite — acceptable desktop only | ⚠️ |
| 2.5.5 Touch Target | Taille Large (56px) | Conforme | ✅ |

### Correction immédiate — Caption

```
Problème : Grey/400 (#9CA3AF) sur White (#FFFFFF) = 2.85:1
Solution : Passer à Grey/500 (#6B7280) = 4.48:1 (borderline)
Mieux    : Passer à Grey/600 (#4B5563) = 7.0:1 ✅ AAA
```

### Ce que MCP ne peut pas détecter automatiquement

- Navigation clavier (ordre de focus, focus trap) → test manuel requis
- Comportement lecteur d'écran (annonces dynamiques) → test NVDA/VoiceOver requis
- Autofill navigateur (`:-webkit-autofill`) → test navigateur requis
- Gestion de l'état Read-only si absent de la frame

---

## Contexte & périmètre

Ce skill couvre :
- L'audit d'accessibilité depuis Figma MCP
- Les ratios de contraste et tokens conformes
- Les patterns ARIA pour les composants complexes
- La navigation clavier et focus management
- Les tests avec lecteurs d'écran
- La génération de rapports d'audit
- La conformité réglementaire (EN 301 549 / FINMA)

---

## Les 4 principes WCAG (POUR)

```
P — Perceptible
  L'information doit être présentable de façon perceptible par tous.
  → Texte alternatif, contraste, pas de contenu uniquement visuel

O — Opérable
  L'interface doit être utilisable par tous.
  → Navigation clavier, pas de délai critique, pas de flash

U — Compréhensible
  L'information et l'interface doivent être compréhensibles.
  → Langue définie, comportements prévisibles, aide à la saisie

R — Robuste
  Le contenu doit être robuste pour être interprété par les AT.
  → HTML valide, ARIA correct, compatibilité lecteurs d'écran
```

---

## Audit Figma — Contraste & couleurs

### Prompt — Audit de contraste depuis Figma

```
"Audite cette frame Figma pour la conformité WCAG 2.1 AA :
  1. Vérifie le ratio de contraste de chaque combinaison texte/fond
  2. Identifie les éléments qui échouent le critère 1.4.3 (4.5:1 pour le texte)
  3. Identifie les éléments UI non-texte qui échouent 1.4.11 (3:1)
  4. Propose les tokens Bridge alternatifs conformes
  5. Génère un rapport avec les violations et les corrections"
```

### Ratios de contraste requis

```
Texte normal (< 18pt / < 14pt gras)  → 4.5 : 1  (AA)
Texte large (≥ 18pt / ≥ 14pt gras)  → 3.0 : 1  (AA)
Composants UI et états               → 3.0 : 1  (AA)
Texte décoratif / logos              → Aucune exigence
Texte sur image de fond              → 4.5 : 1  (meilleure pratique)

AAA (optionnel mais recommandé fintech) :
Texte normal                         → 7.0 : 1
Texte large                          → 4.5 : 1
```

### Tokens Bridge — Combinaisons conformes

```
Fond blanc (surface.default)           + text.primary        = ≥ 7:1  ✅
Fond blanc (surface.default)           + text.secondary      = ≥ 4.5:1 ✅
Fond blanc (surface.default)           + text.disabled       = < 4.5:1 ⚠️ (intentionnel)
Fond primary (action.primary.default)  + text.on-primary     = ≥ 4.5:1 ✅
Fond error (feedback.error.background) + text.on-error       = ≥ 4.5:1 ✅
Fond surface.variant                   + text.primary        = Vérifier cas par cas
```

### Checklist couleurs

```markdown
□ Ratio texte/fond ≥ 4.5:1 pour tout texte standard
□ Ratio texte/fond ≥ 3:1 pour le texte large (≥18px ou ≥14px bold)
□ Ratio icônes/fond ≥ 3:1
□ Ratio bordures/fond ≥ 3:1 pour les champs de formulaire
□ Focus ring visible avec ratio ≥ 3:1 vs arrière-plan adjacent
□ L'information n'est pas transmise uniquement par la couleur
□ Les états d'erreur ont un indicateur autre que la couleur seule
□ Mode sombre : tous les ratios re-vérifiés
```

---

## Navigation clavier

### Ordre de focus — principes

```
1. Logique : suit le flux de lecture naturel (gauche→droite, haut→bas)
2. Visible : l'indicateur de focus est toujours visible
3. Complet : tous les éléments interactifs sont atteignables
4. Efficace : pas de pièges au focus (focus trap uniquement dans les modals)
```

### Prompt — Audit navigation clavier

```
"Pour ce composant Figma, génère :
  1. L'ordre de tabulation attendu (liste numérotée)
  2. Les interactions clavier pour chaque élément
  3. Les cas de focus trap (modals, drawers)
  4. Les raccourcis clavier si applicable"
```

### Mapping clavier par type de composant

```
BOUTON
  Enter / Space → activer
  Tab → focus suivant

LIEN
  Enter → naviguer
  Tab → focus suivant

INPUT TEXT
  Typing → saisie
  Tab → focus suivant
  Shift+Tab → focus précédent

CHECKBOX
  Space → toggle
  Tab → focus suivant

RADIO GROUP
  Arrow Up/Down → naviguer entre les options
  Space → sélectionner
  Tab → sortir du groupe

SELECT / COMBOBOX
  Enter / Space → ouvrir
  Arrow Up/Down → naviguer les options
  Enter → sélectionner
  Escape → fermer

MODAL / DIALOG
  Escape → fermer
  Tab → cycle dans la modal (focus trap)
  Shift+Tab → cycle inverse

TABS
  Arrow Left/Right → changer d'onglet
  Home → premier onglet
  End → dernier onglet
  Tab → dans le contenu de l'onglet actif

ACCORDION
  Enter / Space → ouvrir/fermer
  Tab → focus suivant

DATA TABLE
  Arrow keys → naviguer les cellules
  Enter → activer la cellule
  Space → sélectionner la ligne

TOOLTIP / POPOVER
  Escape → fermer
  (s'ouvre au focus, pas seulement au hover)
```

---

## Patterns ARIA

### Prompt — Générer le code ARIA

```
"Génère le code React/Compose pour ce composant [type]
avec tous les attributs ARIA requis selon WAI-ARIA 1.2.
Inclure : role, aria-label, aria-describedby, aria-expanded, aria-selected, etc."
```

### ARIA par type de composant

```tsx
// MODAL
<div
  role="dialog"
  aria-modal="true"
  aria-labelledby="modal-title"
  aria-describedby="modal-description"
>
  <h2 id="modal-title">Titre de la modal</h2>
  <p id="modal-description">Description</p>
</div>

// ALERT / TOAST
<div role="alert" aria-live="polite">
  Message de succès
</div>

// FORMULAIRE
<div role="group" aria-labelledby="group-label">
  <span id="group-label">Informations personnelles</span>
  <label htmlFor="firstname">Prénom *</label>
  <input
    id="firstname"
    type="text"
    aria-required="true"
    aria-invalid={hasError}
    aria-describedby="firstname-error"
  />
  {hasError && (
    <span id="firstname-error" role="alert">
      Le prénom est obligatoire
    </span>
  )}
</div>

// BOUTON AVEC ÉTAT LOADING
<button
  aria-busy={isLoading}
  aria-label={isLoading ? "Chargement en cours" : "Confirmer"}
  disabled={isLoading}
>
  {isLoading ? <Spinner /> : "Confirmer"}
</button>

// TOGGLE / SWITCH
<button
  role="switch"
  aria-checked={isOn}
  aria-label="Activer les notifications"
>
  {isOn ? "Activé" : "Désactivé"}
</button>

// NAVIGATION
<nav aria-label="Navigation principale">
  <ul>
    <li><a href="/" aria-current="page">Accueil</a></li>
    <li><a href="/portfolio">Portfolio</a></li>
  </ul>
</nav>

// TABS
<div role="tablist" aria-label="Options de compte">
  <button
    role="tab"
    aria-selected={activeTab === 'trading'}
    aria-controls="panel-trading"
    id="tab-trading"
  >
    Trading
  </button>
  <div
    role="tabpanel"
    id="panel-trading"
    aria-labelledby="tab-trading"
    hidden={activeTab !== 'trading'}
  >
    Contenu trading
  </div>
</div>

// EXPANDABLE / ACCORDION
<button
  aria-expanded={isOpen}
  aria-controls="accordion-content"
>
  Section titre
</button>
<div id="accordion-content" hidden={!isOpen}>
  Contenu
</div>

// STEP INDICATOR (onboarding, auth)
<ol aria-label="Étapes du processus">
  <li aria-current="step">Identification</li>
  <li>Vérification</li>
  <li>Confirmation</li>
</ol>
```

---

## Focus management

### Prompt — Focus management pour les interactions dynamiques

```
"Ce composant [modal/drawer/toast] apparaît dynamiquement.
Génère le code de focus management complet :
  1. Focus initial au moment de l'ouverture
  2. Focus trap pendant l'ouverture
  3. Retour du focus à l'élément déclencheur à la fermeture"
```

### Template — Focus trap React

```tsx
import { useEffect, useRef } from 'react'

const FOCUSABLE_SELECTORS = [
  'a[href]',
  'button:not([disabled])',
  'input:not([disabled])',
  'select:not([disabled])',
  'textarea:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
].join(', ')

export function useFocusTrap(isActive: boolean) {
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!isActive || !containerRef.current) return

    const container = containerRef.current
    const focusableElements = container.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTORS)
    const firstElement = focusableElements[0]
    const lastElement = focusableElements[focusableElements.length - 1]

    // Focus initial
    firstElement?.focus()

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key !== 'Tab') return

      if (e.shiftKey) {
        if (document.activeElement === firstElement) {
          e.preventDefault()
          lastElement?.focus()
        }
      } else {
        if (document.activeElement === lastElement) {
          e.preventDefault()
          firstElement?.focus()
        }
      }
    }

    container.addEventListener('keydown', handleKeyDown)
    return () => container.removeEventListener('keydown', handleKeyDown)
  }, [isActive])

  return containerRef
}
```

---

## Tests avec lecteurs d'écran

### Matrice de test

```
NVDA + Firefox       → Windows, le plus utilisé
JAWS + Chrome        → Windows, enterprise
VoiceOver + Safari   → macOS / iOS
TalkBack + Chrome    → Android
```

### Checklist lecteur d'écran

```markdown
□ Le titre de la page est annoncé à la navigation
□ L'ordre de lecture est logique
□ Tous les éléments interactifs ont un nom accessible
□ Les états sont annoncés (sélectionné, étendu, en cours, erreur)
□ Les changements dynamiques sont annoncés (live regions)
□ Les images ont des alt pertinents (ou alt="" si décoratif)
□ Les formulaires : label + message d'erreur associés
□ Les modals : focus trap + annonce du titre
□ Les tableaux : en-têtes associés aux cellules
```

### Live regions — annonces dynamiques

```tsx
// ARIA live pour les mises à jour importantes
<div aria-live="polite" aria-atomic="true" className="sr-only">
  {statusMessage}
</div>

// Erreurs : assertive (interrompt le lecteur)
<div aria-live="assertive" role="alert">
  {errorMessage}
</div>

// Classe utilitaire "screen-reader only"
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}
```

---

## Rapport d'audit

### Prompt — Générer un rapport complet

```
"Audite ce fichier/composant Figma pour la conformité WCAG 2.1 AA.
Génère un rapport structuré avec :
  1. Score global (% de critères conformes)
  2. Violations critiques (bloquantes)
  3. Violations majeures
  4. Recommandations
  5. Plan de remédiation priorisé"
```

### Template — Rapport d'audit

```markdown
# Rapport d'accessibilité — [Nom du composant/Feature]

**Date :** [date]  
**Standard :** WCAG 2.1 Niveau AA  
**Référentiel :** EN 301 549 v3.2.1  
**Auditeur :** Claude Code + revue manuelle

## Résumé exécutif

| Catégorie | Conformes | Non conformes | N/A |
|-----------|-----------|---------------|-----|
| Perceptible | X | X | X |
| Opérable | X | X | X |
| Compréhensible | X | X | X |
| Robuste | X | X | X |
| **Total** | **X** | **X** | **X** |

## Violations critiques 🔴

### 1.4.3 — Contraste du texte
- **Élément :** [description]
- **Ratio actuel :** X.X:1
- **Ratio requis :** 4.5:1
- **Correction :** Utiliser `color.text.primary` au lieu de `color.text.tertiary`

## Violations majeures 🟡

### 2.4.3 — Ordre du focus
- **Problème :** L'ordre de tabulation ne suit pas le flux visuel
- **Correction :** Réorganiser les éléments dans le DOM

## Recommandations 🟢

- Ajouter `aria-describedby` sur les champs avec des instructions
- Améliorer les messages d'erreur (plus descriptifs)

## Plan de remédiation

| Priorité | Critère | Action | Effort | Responsable |
|----------|---------|--------|--------|-------------|
| P1 | 1.4.3 | Corriger les tokens couleur | XS | Dev |
| P2 | 2.4.3 | Reorder DOM elements | S | Dev |
| P3 | 2.5.3 | Ajouter aria-label | XS | Dev |
```

---

## Commandes de référence rapide

```
# Prompts essentiels accessibilité

"Audit this Figma frame for WCAG 2.1 AA compliance"
"Check all color contrast ratios in my selection against WCAG standards"
"Generate the complete ARIA markup for this [modal/form/tabs] component"
"What keyboard interactions are required for this component?"
"Generate the focus trap implementation for this modal"
"Create an accessibility report for this feature"
"List all elements that need alternative text in this frame"
"Generate screen reader announcements for the dynamic states of this component"
"Check if the tab order in this frame follows a logical reading order"
```
