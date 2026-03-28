# SKILL : UX Research & Specs

> Skill pour générer, structurer et maintenir les specs fonctionnelles,  
> les annotations de design, les user flows et la documentation UX.

---

## ✅ Validé en conditions réelles — Learnings du test (2026-03-28)

> Test effectué sur la frame `Input` du fichier **Foundations – Laboratoire Innotech International**  
> Frame : 1697 × 4407 px · 4 sections · ~14k tokens MCP

### Ce qui fonctionne parfaitement

**Stratégie automatique sur grande frame :**  
Claude Code a spontanément découpé la frame en sections et lancé les appels en parallèle sans instruction explicite :
```
get_metadata          → structure globale (lecture rapide)
get_design_context ×4 → une par section
get_screenshot        → référence visuelle
get_variable_defs     → tokens Figma
```
Durée totale : **2 min 17 sec** pour un handoff complet.

**Détection automatique de problèmes non évidents :**
- Ratios de contraste calculés et classés (WCAG AA pass/fail)
- Touch targets mesurés par taille de composant
- Valeurs hardcodées identifiées (border-radius, paddings, gaps)
- État manquant détecté (Read-only absent de la frame)
- Ambiguïté de nommage signalée (`Pressed` Figma = `:focus-visible` CSS)

### Points d'attention MCP à connaître

| Situation | Ce qui se passe | Solution |
|-----------|-----------------|----------|
| Frame > ~5k tokens | Warning `Large MCP response` | Normal — Claude Code gère automatiquement |
| Pas de Code Connect | Message d'avertissement dans la réponse | Ignorer si l'objectif est specs/handoff, pas du code |
| Sections sans variables liées | Les valeurs hardcodées apparaissent en commentaires | Les noter dans la checklist tokens |
| `get_design_context` seul sur grande frame | Réponse tronquée ou incomplète | Toujours commencer par `get_metadata` sur les frames > 800px de haut |

### Prompt optimisé validé (composant de design system)

```
Tu es un expert UX spécialisé en design systems.

J'ai une frame sélectionnée dans Figma Desktop : [DESCRIPTION DE LA FRAME].

## Flux obligatoire — dans cet ordre
1. get_metadata        → évaluer la taille et structure
2. get_design_context  → par section si frame > 800px de haut
3. get_screenshot      → référence visuelle
4. get_variable_defs   → tokens utilisés

## Output attendu
[SECTIONS DU DOCUMENT SOUHAITÉES]

Langue : Français
Format : Markdown prêt à coller dans Notion
```

---

## Contexte & périmètre

Ce skill couvre :
- L'extraction automatique de specs depuis Figma
- La rédaction de specs fonctionnelles structurées
- La génération d'annotations d'accessibilité et d'interaction
- La documentation des user flows et états
- La préparation des dossiers de handoff developer
- La rédaction de cas d'usage et critères d'acceptance

---

## Extraction de specs depuis Figma MCP

### Prompt — Specs complètes d'un composant

```
"Depuis ma sélection Figma, génère les specs complètes :
  1. Description fonctionnelle
  2. Propriétés visuelles (tailles, espacements, couleurs, typo)
  3. États (default, hover, focus, active, disabled, error, loading)
  4. Comportements interactifs
  5. Contenu et contraintes (longueur max, truncation, etc.)
  6. Accessibilité (rôle ARIA, navigation clavier, lecteur d'écran)
  7. Responsive (mobile, tablet, desktop)"
```

### Prompt — Specs d'une page entière

```
"Depuis ma sélection Figma (cette page), génère :
  1. L'inventaire de tous les composants présents
  2. La hiérarchie de l'information
  3. Les zones de contenu dynamique vs statique
  4. Les interactions et transitions entre états
  5. Les dépendances entre composants"
```

### Prompt — Annotations pour developers

```
"Annote cette frame Figma pour le handoff développeur.
Pour chaque élément, spécifie :
  - Token de design utilisé (pas les valeurs brutes)
  - Comportement attendu
  - Contraintes de contenu
  - Exigences d'accessibilité"
```

---

## Format de specs fonctionnelles

### Template — Spec de composant

```markdown
# [Nom du composant] — Spec fonctionnelle

**Version :** 1.0  
**Figma :** [lien vers le composant]  
**Statut :** Draft / En review / Approuvé  
**Date :** [date]

---

## 1. Description

[Ce que fait le composant, son rôle dans l'interface, quand l'utiliser]

## 2. Variantes

| Variante | Quand l'utiliser |
|----------|-----------------|
| Primary | Action principale de la page |
| Secondary | Actions secondaires |
| Ghost | Actions tertiaires, contextes chargés |

## 3. États

| État | Description | Déclencheur |
|------|-------------|-------------|
| Default | État normal au repos | — |
| Hover | Survol souris | mouseenter |
| Focus | Sélection clavier | Tab / focus() |
| Active | Clic en cours | mousedown |
| Disabled | Non interactif | prop disabled=true |
| Loading | Action en cours | prop isLoading=true |
| Error | Erreur de validation | état error |

## 4. Propriétés visuelles

### Spacing
- Padding horizontal : `spacing.component.button.padding-x` (24px sur md)
- Padding vertical : `spacing.component.button.padding-y` (12px sur md)
- Gap icône/texte : `spacing.xs` (8px)
- Hauteur min : 48px (touch target)

### Typographie
- Label : `typography.label.large` (14sp, weight 500)

### Couleurs
- Fond primary : `color.action.primary.default`
- Texte : `color.text.on-primary`
- Focus ring : `color.focus.ring` (offset 2px)

## 5. Contenu & contraintes

- Label : 1 ligne maximum, pas de retour à la ligne
- Longueur recommandée : 1-3 mots
- Icône optionnelle : 20×20px, gauche ou droite
- Truncation : ellipsis si espace insuffisant

## 6. Comportements interactifs

- Click → déclenche l'action, passe en état loading si async
- Hover → transition couleur 150ms ease
- Focus visible → focus ring 2px avec offset
- Keyboard → Enter ou Space pour activer
- Disabled → bloque tous les événements, curseur not-allowed

## 7. Responsive

| Breakpoint | Comportement |
|------------|-------------|
| Mobile (<600px) | Full width par défaut |
| Tablet (600-1024px) | Auto width |
| Desktop (>1024px) | Auto width, min-width 120px |

## 8. Accessibilité

- Rôle : `button` natif (pas de div cliquable)
- Label : texte visible ou `aria-label` si icône seule
- État disabled : `aria-disabled="true"` + `disabled`
- État loading : `aria-busy="true"` + message pour SR
- Focus : visible, jamais supprimé

## 9. Critères d'acceptance

- [ ] Tous les états visuels sont implémentés
- [ ] Navigation clavier fonctionne
- [ ] Lecteur d'écran annonce l'état loading
- [ ] Touch target ≥ 44×44px sur mobile
- [ ] Pas de valeurs hardcodées (100% tokens)
- [ ] Tests unitaires couvrent les variantes et états
```

---

## User Flows

### Prompt — Documenter un flow depuis Figma

```
"Depuis ces frames Figma (sélectionnées), génère le user flow complet :
  1. Point d'entrée et déclencheur
  2. Étapes séquentielles avec les décisions
  3. États alternatifs (erreur, vide, succès)
  4. Points de sortie
  5. Format : liste numérotée + description des transitions"
```

### Template — User Flow

```markdown
# Flow : [Nom du flow]

**Déclencheur :** [Action qui lance le flow]  
**Acteur :** [Utilisateur / Système]  
**Précondition :** [Ce qui doit être vrai avant]  
**Postcondition :** [Ce qui est vrai après]

## Chemin principal (happy path)

1. L'utilisateur [action]
2. Le système [réaction]
3. L'utilisateur voit [écran/état]
4. [etc.]

## Chemins alternatifs

### Erreur de validation
- Si [condition] → afficher [message d'erreur]
- L'utilisateur peut [corriger] ou [annuler]

### État vide
- Si [aucun contenu] → afficher [empty state]
- Proposer [action principale]

### Timeout / Erreur réseau
- Après Xs sans réponse → afficher [indicateur de chargement]
- En cas d'erreur → afficher [message] + [action de retry]

## Edge cases

- [Cas limite 1] : comportement attendu
- [Cas limite 2] : comportement attendu
```

---

## Handoff developer

### Prompt — Préparer le handoff

```
"Depuis ma sélection Figma, génère le document de handoff complet pour les developers :
  1. Inventaire des assets (icônes, images, illustrations)
  2. Tokens utilisés avec leurs valeurs résolues
  3. Grille et système de layout
  4. Animations et transitions (durée, easing, déclencheur)
  5. Comportements non visibles dans les maquettes statiques
  6. Questions à clarifier avant implémentation"
```

### Checklist handoff

```markdown
## Checklist avant handoff

### Design
- [ ] Tous les états sont designés (default, hover, focus, error, empty, loading)
- [ ] Version mobile ET desktop présentes
- [ ] Composants liés à la librairie Bridge (pas de composants locaux)
- [ ] Toutes les couleurs et espaces sont en tokens
- [ ] Nommage des layers cohérent et lisible
- [ ] Annotations d'interaction ajoutées

### Contenu
- [ ] Textes finaux validés (pas de lorem ipsum)
- [ ] Cas de texte long gérés (truncation, wrap)
- [ ] Labels des boutons/actions validés UX Writing

### Assets
- [ ] Icônes exportées en SVG
- [ ] Images en résolution 2x minimum
- [ ] Assets nommés selon la convention Bridge

### Accessibilité
- [ ] Ratios de contraste vérifiés
- [ ] Ordre de focus documenté
- [ ] Textes alternatifs définis pour les images
- [ ] Annotations ARIA pour les composants complexes

### Developer Ready
- [ ] Code Connect configuré pour les composants principaux
- [ ] Tokens exportés depuis Tokens Studio
- [ ] README de la feature mis à jour
```

---

## Research & Tests utilisateurs

### Prompt — Rédiger un script de test utilisateur depuis Figma

```
"Depuis ce prototype Figma (lien), génère un script de test utilisateur modéré :
  1. Contexte et scénario à présenter au participant
  2. Tâches à accomplir (sans biais directifs)
  3. Questions de suivi pour chaque tâche
  4. Métriques à observer (succès, temps, erreurs, verbalisations)
  5. Questions de debriefing"
```

### Template — Résumé d'insight UX

```markdown
# Insights — [Nom de la fonctionnalité]

**Source :** Tests utilisateurs / Analytics / Heatmap / [autre]  
**Date :** [date]  
**Participants :** [n=X]

## Problèmes identifiés (priorité décroissante)

### 🔴 Critique
- **Problème :** [description]
- **Fréquence :** X/X participants touchés
- **Impact :** [bloquant / frustrant / confus]
- **Recommandation :** [solution proposée]

### 🟡 Majeur
- **Problème :** [description]
- **Recommandation :** [solution]

### 🟢 Mineur
- **Problème :** [description]
- **Recommandation :** [solution]

## Prochaines étapes

- [ ] [Action 1] — Responsable — Date
- [ ] [Action 2] — Responsable — Date
```

---

## Commandes de référence rapide

```
# Prompts essentiels UX/Specs

"Generate complete functional specs from my Figma selection"
"Document all interaction states for this component"
"Create the developer handoff checklist for this frame"
"Extract the user flow from these connected frames"
"Generate acceptance criteria for this feature"
"List all edge cases for this form flow"
"Write the UX writing guidelines for this component labels"
```
