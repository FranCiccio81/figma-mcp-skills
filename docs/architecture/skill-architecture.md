# Architecture de la bibliothèque de skills

## 1. Principes

- **Spec ouverte.** Chaque skill respecte la spécification Agent Skills (`SPEC-AGENTSKILLS`) : un dossier, un `SKILL.md` avec frontmatter `name` et `description`, des ressources facultatives.
- **Divulgation progressive.** Le `SKILL.md` reste court (cible < 200 lignes, plafond dur 500). Le détail vit dans `references/`, chargé seulement quand une étape le demande, un seul niveau de profondeur.
- **Une seule copie par skill.** Le dossier canonique est sous `skills/<domaine>/<nom>/`. Tout autre emplacement (`.claude/skills/`, `~/.claude/skills/`) est un lien symbolique ou une copie générée par `scripts/install-skills.sh`.
- **Universel séparé du spécifique.** Les skills ne contiennent aucune règle propre à un produit ou à une entreprise. Les contraintes projet (Bridge, Swissquote) restent dans `rules/` et dans le `CLAUDE.md` du projet consommateur, qui ont priorité.
- **Orchestration plutôt que duplication.** Quand une skill officielle existe (Android, Figma), la nôtre décide quoi faire et délègue l'implémentation à la skill officielle au lieu de la recopier.

## 2. Arborescence

```
skills/
  product/          découverte, JTBD, stratégie, PRD, expérimentation, priorisation, métriques
  ux/               heuristiques, tests utilisateurs, recherche, parcours, IA, UX writing, interaction
  design-systems/   component (existante), tokens, gouvernance
  apple/            HIG, SwiftUI, accessibilité Apple
  android/          Material 3, Compose, accessibilité Android
  engineering/      React et TypeScript, HTML et CSS, tests, performance, sécurité, revue de code
  quality/          audit d'accessibilité, QA design et implémentation
  ai-workflows/     routeur de skills, contexte Figma, mapping de tokens Figma, spec d'implémentation
  registry.json     généré par scripts/build_registry.py, lu par le routeur
```

Claude Code découvre les skills de projet à plat dans `.claude/skills/<nom>/`. Le niveau domaine est donc un choix d'organisation du dépôt source ; l'installation aplatit l'arborescence et le validateur garantit l'unicité des noms sur tout `skills/`.

Structure d'une skill :

```
<nom>/
  SKILL.md              obligatoire
  references/           documentation chargée à la demande
  evals/evals.json      au moins un cas réaliste (format compatible skill-creator)
  assets/               gabarits éventuels
```

## 3. Frontmatter

```yaml
---
name: design-token-architecture          # = nom du dossier, minuscules, chiffres, tirets
description: <ce que fait la skill>. Use when <déclencheurs>. Do not use for <exclusions>.
license: MIT
compatibility: <seulement si un environnement particulier est requis>
metadata:
  version: "1.0.0"                        # SemVer, chaîne
  domain: design-systems                  # = dossier parent
  status: stable                          # stable | beta | experimental | legacy
  trust: internal                         # internal | official-derived | community-derived
  sources: "DTCG-2025-10,W3C-WCAG22"      # IDs de docs/sources/source-registry.md
  platforms: "any"                        # any | web | ios | ipados | macos | watchos | visionos | android
  last-reviewed: "2026-11-17"
---
```

La spec impose des valeurs de `metadata` de type chaîne ; les listes sont donc séparées par des virgules.

## 4. Corps du SKILL.md

Sections obligatoires, dans cet ordre, vérifiées par le validateur :

1. `## When to use` (et quand ne pas l'utiliser)
2. `## Inputs`
3. `## Workflow` (étapes numérotées, actionnables)
4. `## Outputs`
5. `## Edge cases`
6. `## Acceptance criteria` (liste à cocher vérifiable)
7. `## Sources`

## 5. Statut des preuves

Toute skill qui produit de l'analyse étiquette ses affirmations :

| Étiquette | Sens |
|---|---|
| `[Observed]` | Constaté directement dans un artefact fourni (fichier Figma, code, enregistrement, donnée) |
| `[Validated]` | Confirmé par une recherche ou une mesure dont la méthode est citée |
| `[Assumption]` | Hypothèse non vérifiée, à tester |
| `[Recommendation]` | Proposition de l'agent, avec sa justification |

Aucune skill n'invente de donnée utilisateur, de verbatim, de métrique ou de valeur de design. Une information absente est déclarée absente.

## 6. Ordre de priorité

Quand des exigences se contredisent, l'agent applique cet ordre et explique le conflit :

1. Sécurité et exigences légales applicables (accessibilité légale, protection des données, réglementation financière)
2. Contraintes propres au projet et exigences validées
3. Guidelines officielles de la plateforme
4. Design system établi du projet
5. Skills réutilisables pertinentes
6. Bonnes pratiques communautaires

## 7. Orchestration

`skills/ai-workflows/skill-router` lit `skills/registry.json` et sélectionne les skills selon l'intention (produit, UX, design system, implémentation, qualité) et le contexte de plateforme. Les skills d'une plateforme non visée ne sont jamais activées. Voir `skills/ai-workflows/skill-router/references/routing-rules.md`.

## 8. Cycle de vie

| Statut | Signification |
|---|---|
| `experimental` | Nouvelle, non évaluée sur un cas réel |
| `beta` | Validée structurellement, évaluations définies, pas encore exécutées sur un projet réel |
| `stable` | Utilisée et évaluée sur au moins un cas réel documenté |
| `legacy` | Conservée pour compatibilité, structure antérieure |

Toute modification de comportement incrémente la version mineure ; un changement de sortie attendue incrémente la majeure. `last-reviewed` est mis à jour à chaque revue des sources.
