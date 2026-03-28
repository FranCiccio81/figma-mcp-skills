# Figma MCP Rules — Universelles

> Rules à copier dans `.cursor/rules`, `CLAUDE.md`, ou l'équivalent de ton éditeur.
> Enrichies avec les learnings du test réel (2026-03-28).

---

## Rules core — À toujours appliquer

```
## Figma MCP Integration Rules

### Flux obligatoire (ne pas sauter)
1. Sur les frames > 800px de haut : appeler get_metadata en premier
2. Appeler get_design_context — par section si frame large
3. Appeler get_screenshot systématiquement pour la référence visuelle
4. Appeler get_variable_defs pour les tokens utilisés
5. Traduire l'output (React + Tailwind) dans les conventions du projet
6. Valider contre Figma pour une correspondance 1:1 avant de marquer comme terminé

### Rules d'implémentation
- Traiter l'output MCP comme une représentation du design, pas comme du code final
- Remplacer les classes Tailwind par les tokens/utilities du design system
- Réutiliser les composants existants plutôt que de dupliquer
- Utiliser les tokens couleur, typographie et spacing du système
- Respecter les patterns existants de routing, state et data fetching
- Valider le rendu final contre le screenshot Figma

### Assets
- Si le MCP retourne une URL localhost pour une image ou SVG → utiliser directement
- Ne PAS importer de librairies d'icônes externes — assets dans le payload Figma
- Ne PAS créer de placeholders si une source localhost est disponible
```

---

## Warnings MCP — Guide de décodage

Appris en conditions réelles sur une frame de 1697×4407px :

| Warning | Cause | À faire |
|---------|-------|---------|
| `Components missing code connect mappings` | Pas de Code Connect | Ignorer pour specs/handoff. Pertinent pour génération de code |
| `Large MCP response (~14.0k tokens)` | Frame volumineuse | Normal. Claude Code continue correctement |
| `MUST call get_screenshot` | Rappel automatique | Toujours appeler |
| `MUST call get_design_context` après `get_metadata` | Rappel automatique | Toujours appeler |
| `SUPER CRITICAL: generated code MUST be converted` | Rappel output MCP | L'output React+Tailwind est un point de départ, pas du code final |

---

## Stratégie par taille de frame

| Taille de frame | Stratégie | Temps estimé |
|----------------|-----------|--------------|
| < 400px haut | `get_design_context` direct | ~20-30 sec |
| 400–800px | `get_design_context` + `get_screenshot` | ~30-60 sec |
| > 800px | `get_metadata` → sections → `get_design_context` × N en parallèle | ~1-3 min |
| > 2000px (page entière) | `get_metadata` → cibler les nodes clés | ~3-5 min |

---

## Rules Claude Code

```markdown
# MCP Servers

## Figma MCP server rules

- Assets locaux : utiliser les URLs localhost directement (http://localhost:3845/assets/...)
- IMPORTANT : Ne PAS importer de librairies d'icônes externes
- IMPORTANT : Ne PAS créer de placeholders si source localhost disponible
- IMPORTANT : Appeler get_screenshot systématiquement
- IMPORTANT : Sur frames > 800px → get_metadata d'abord, puis get_design_context par section
- IMPORTANT : L'output React+Tailwind du MCP est un point de départ, toujours convertir
```

---

## Rules Cursor

```
---
description: Figma MCP server rules
globs:
alwaysApply: true
---
- Assets locaux : utiliser les URLs localhost directement
- IMPORTANT : Ne PAS importer de librairies d'icônes externes
- IMPORTANT : Ne PAS créer de placeholders si source localhost disponible
- IMPORTANT : get_metadata en premier sur les grandes frames (> 800px)
- IMPORTANT : get_screenshot toujours après get_design_context
- IMPORTANT : convertir l'output React+Tailwind vers les conventions du projet
```

---

## Rules de qualité générales

```
- Réutiliser les composants existants de /src/components
- Priorité à la fidélité Figma
- Utiliser les tokens, jamais de valeurs hardcodées
- WCAG 2.1 AA sur tous les composants
- Documenter les composants générés
- Vérifier les composants imbriqués pour les border-radius
- L'état "Pressed" dans Figma = :focus-visible CSS (pas :active)
```
