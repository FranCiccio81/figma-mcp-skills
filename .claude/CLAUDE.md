# Claude Code — Rules globales

## MCP Servers

### Figma MCP server rules

- Le Figma MCP server fournit un endpoint d'assets local pour les images et SVG
- IMPORTANT : Si le MCP retourne une source `localhost` pour une image ou un SVG, utilise cette source directement sans la modifier
- IMPORTANT : Ne PAS importer de nouvelles librairies d'icônes — tous les assets doivent venir du payload Figma
- IMPORTANT : Ne PAS créer de placeholders si une source localhost est fournie
- IMPORTANT : Toujours appeler `get_screenshot` après `get_design_context`
- IMPORTANT : Vérifier la liste des outils exposés avant le premier appel (ils diffèrent entre serveur distant et desktop) ; le serveur distant demande `create_session` avant les outils de fichier
- IMPORTANT : Ne jamais inventer une valeur qu'un appel MCP n'a pas retournée ; en cas d'accès refusé, appeler `whoami` une fois, signaler et passer au repli documenté
- IMPORTANT : Sur les frames > 800px de haut, toujours commencer par `get_metadata`

### Warnings MCP à connaître

| Warning | Signification | Action |
|---------|---------------|--------|
| `Components missing code connect mappings` | Pas de Code Connect | Ignorer pour specs/handoff |
| `Large MCP response (~Xk tokens)` | Frame volumineuse | Normal — continuer |
| `MUST call get_screenshot` | Rappel automatique MCP | Toujours respecter |
| `MUST call get_design_context` après `get_metadata` | Rappel automatique | Toujours respecter |

## Flux obligatoire

### Specs / Handoff
1. `get_metadata` → taille et structure
2. `get_design_context` × N → par section si frame > 800px
3. `get_screenshot` → référence visuelle
4. `get_variable_defs` → tokens utilisés
5. Document Markdown en français, format Notion-ready

### Implémentation / Code
1. `get_metadata` → si frame large
2. `get_design_context` → structure React + Tailwind
3. `get_screenshot` → référence visuelle
4. `get_variable_defs` → tokens à mapper
5. `get_code_connect_map` → composants existants
6. Convertir vers les conventions du projet (jamais utiliser l'output MCP tel quel)
7. Valider visuellement contre le screenshot

> Validé (2026-03-28) : frame 1697×4407px / 4 sections → handoff complet en 2min17.

## Design System — Bridge

- Toujours utiliser les tokens Bridge (4 tiers : core → semantic → component → breakpoint)
- Ne JAMAIS hardcoder couleurs, spacing ou typographie
- Noms sémantiques : `color.action.primary` pas `#0057FF`
- Atomic Design : atoms → molecules → organisms → templates
- Nommage BEM pour les classes CSS

### Correspondances Figma → CSS fréquentes

| Nom Figma | Token CSS |
|-----------|-----------|
| `Grey/900` | `--color-text-primary` |
| `Grey/400` | `--color-text-disabled` |
| `Grey/300` | `--color-border-default` |
| `Primary/500` | `--color-action-primary` |
| `Danger/500` | `--color-feedback-error` |
| `Shades/White` | `--color-surface-default` |
| `Input/Focus` | `--shadow-input-focus` |

## Accessibilité

- WCAG 2.1 AA obligatoire sur tous les composants (cible recommandée : WCAG 2.2 AA, Recommandation W3C depuis octobre 2023, qui inclut 2.1 AA)
- Contraste : 4.5:1 texte / 3:1 éléments UI / 3:1 focus ring
- Touch target (règle projet) : 44px web / 44pt iOS / 48dp Android. Pour mémoire, le minimum WCAG 2.2 AA est 24 × 24 px CSS (2.5.8) ; 44 px correspond au niveau AAA (2.5.5)
- ARIA approprié pour tous les composants complexes
- ⚠️ `Grey/400` (#9CA3AF) sur blanc = ratio 2,54:1 (calculé) → JAMAIS utiliser pour du texte
- ⚠️ `Primary/500` (#3B82F6) sur blanc = 3,68:1 → valable pour un focus ring ou une bordure (3:1), insuffisant pour du texte normal (4,5:1)
- ⚠️ État "Pressed" dans Figma : vérifier variante par variante. Dans le fichier Foundations testé, il montre un focus ring (`:focus-visible`) ; ailleurs il peut désigner l'état pressé (`:active`)
- ⚠️ Tailles Micro (<30px) et Small (<36px) : touch target insuffisant sur mobile

## Code Quality

- Réutiliser les composants existants — ne pas dupliquer
- JSDoc / KDoc sur tous les composants générés
- Respecter la structure de fichiers du projet
- Pas de styles inline sauf cas justifiés
- Vérifier les composants imbriqués : le border-radius visible ≠ forcément le layer racine

## Skills

- Skills canoniques : `skills/<domaine>/<nom>/` ; catalogue généré : `docs/registry/skills-registry.md`
- Pour une demande en plusieurs étapes, commencer par `skill-router` (il charge d'abord ce fichier et `rules/`)
- Toute lecture Figma passe par `figma-design-context`
- Ordre de priorité en cas de conflit : sécurité et droit, contraintes projet validées, guidelines officielles de plateforme, design system du projet, skills réutilisables, pratiques communautaires
