# Workflow — Figma MCP + Claude Code

Guide pratique pour documenter un composant de design system directement depuis Figma Desktop via le MCP Server.

---

## Prérequis

- Claude Code installé (`npm i -g @anthropic-ai/claude-code`)
- Figma Desktop avec le MCP Server activé
- Un fichier Figma ouvert, frame sélectionnée

---

## Étape 1 — Évaluer la taille de la frame

```
get_metadata (sans nodeId = nœud sélectionné)
```

Retourne la structure XML avec les IDs, noms, positions et dimensions.

**Règle :** si la frame fait > ~2000 px de hauteur, découper en sections et appeler
`get_design_context` sur chaque sous-frame séparément.

---

## Étape 2 — Extraire le design en parallèle

Lancer simultanément :

```
get_design_context (section 1)
get_design_context (section 2)
get_design_context (section N)
get_screenshot
get_variable_defs
```

`get_design_context` retourne du code React+Tailwind de référence enrichi de métadonnées.
`get_variable_defs` retourne tous les tokens (couleurs, typo, effets) liés au nœud.
`get_screenshot` donne la référence visuelle.

---

## Étape 3 — Générer la documentation

Demander à Claude de produire un document Markdown structuré couvrant :

| Section | Contenu |
|---------|---------|
| Vue d'ensemble | Rôle, variantes, tailles |
| Anatomie | Éléments constitutifs + tokens |
| États | Tableau comparatif par état |
| Tokens | Couleurs, spacing, typo, radius, ombres |
| Comportements | Transitions, validation, label floating |
| Accessibilité | ARIA, contraste, touch targets |
| Checklist handoff | Points de vérification avant dev |
| Questions ouvertes | Décisions à confirmer |

---

## Astuce — Nœuds sans Code Connect

Si `get_design_context` retourne un message Code Connect, répondre **non**
puis rappeler l'outil avec `forceCode: true`. Le code de référence sera généré
sans mapping codebase.

---

## Tokens fréquents à surveiller

- Valeurs hardcodées non liées à un token → signaler dans le doc
- `border-radius` souvent absent des variables Figma
- `padding` / `gap` rarement tokenisés → créer des tokens d'espacement
- Contrastes `placeholder` et `caption` souvent sous le seuil WCAG AA

---

## Commande de prompt type

```
Tu es un expert UX spécialisé en design systems.
J'ai une frame sélectionnée dans Figma Desktop : [NOM DU COMPOSANT].

## Flux obligatoire — dans cet ordre
1. get_metadata       → évaluer la taille
2. get_design_context → structure (par section si besoin)
3. get_screenshot     → référence visuelle
4. get_variable_defs  → tokens

Génère un document Markdown complet avec :
anatomie, états, tokens, accessibilité, checklist handoff, questions ouvertes.
Langue : Français. Format : prêt à coller dans Notion.
```
