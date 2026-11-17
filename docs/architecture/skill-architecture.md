# Architecture de la bibliothèque de skills

## 1. Principes

1. **Spécification ouverte d'abord** : chaque skill respecte la spécification Agent Skills (https://github.com/agentskills/agentskills, `docs/specification.mdx`). Aucune extension propriétaire dans le frontmatter : les informations propres à ce dépôt vont dans `metadata`, qui est une table de chaînes.
2. **Divulgation progressive** : le `SKILL.md` reste court (cible ≤ 250 lignes, plafond dur 500). Le détail va dans `references/`, chargé à la demande, à un seul niveau de profondeur.
3. **Un skill, une responsabilité, une seule copie.** Le validateur refuse les noms en double.
4. **Le format est universel, le contenu projet est isolé** : les skills marqués `scope: project` (Bridge) ne sont jamais activés hors du projet concerné.
5. **Pas d'invention** : un skill n'affirme une valeur (API, seuil, nom d'outil) que si une source primaire du registre la porte.

## 2. Arborescence

```
skills/
  product/           découverte, JTBD, stratégie, PRD, expérimentation, priorisation, mesure
  ux/                recherche, tests, heuristiques, parcours, IA, interaction, rédaction, critique
  design-systems/    tokens, API de composants, gouvernance, Bridge (projet)
  apple/             HIG, SwiftUI, accessibilité Apple
  android/           Material 3 + Compose, mise en page adaptative, accessibilité Android
  engineering/       React/TS, HTML/CSS, tests, performance, sécurité, revue, spec technique
  quality/           audit d'accessibilité, QA visuelle et régression
  ai-workflows/      Figma MCP (design-to-code, handoff, dérive design/code), routeur de skills
.claude/skills/component/   skill historique conservé à son emplacement
tools/               validateur, générateur de registre, installation, tests
docs/                audit, registre des sources, architecture, registre des skills
```

Les dossiers de domaine ne font pas partie du nom : un skill s'installe à plat (`.claude/skills/<name>/`) grâce à `tools/install.sh`, ce qui est le format attendu par Claude Code et les autres clients. Les noms sont donc uniques dans tout le dépôt.

## 3. Anatomie d'un skill

```
<name>/
  SKILL.md            obligatoire
  references/         optionnel, détail chargé à la demande
  scripts/            optionnel, code exécutable relu et testé
  evals/evals.json    obligatoire dans ce dépôt (schéma de anthropics/skills skill-creator)
```

### Frontmatter

```yaml
---
name: design-token-architecture          # = nom du dossier, [a-z0-9-], ≤ 64
description: >-                           # ≤ 1024, dit QUOI et QUAND ("Use when ...")
  ...
compatibility: ...                        # seulement si contrainte réelle d'environnement
metadata:
  domain: design-systems                  # = dossier parent
  version: "1.0.0"                        # SemVer
  status: stable                          # stable | beta | deprecated
  scope: universal                        # universal | project
  trust: authored                         # authored | official-derived | project-specific
  last-reviewed: "2026-11-17"
---
```

Le champ `license` est laissé vide tant que le propriétaire du dépôt n'a pas choisi de licence (voir l'audit).

### Corps : sections obligatoires

`## When to use`, `## Inputs`, `## Procedure`, `## Output`, `## Edge cases`, `## Acceptance criteria`, `## Sources`.

Les skills qui produisent un jugement (audit, critique, recherche, produit) séparent explicitement **observations**, **hypothèses**, **constats validés** et **recommandations**.

## 4. Contrôles qualité (tools/validate_skills.py)

| # | Contrôle | Bloquant |
|---|---|---|
| 1 | Conformité à la spécification (frontmatter, nom, longueurs, champs autorisés) | Oui |
| 2 | Métadonnées du dépôt (domaine, SemVer, statut, portée, confiance, date) | Oui |
| 3 | Liens relatifs résolus ; liens externes vérifiables avec `--external` | Oui (relatifs) |
| 4 | Provenance : chaque URL de la section Sources appartient à un domaine du registre des sources | Oui |
| 5 | Doublons : noms identiques (bloquant), descriptions trop proches (avertissement) | Oui / Non |
| 6 | Sécurité : `curl … \| sh`, injections d'instructions, motifs de secrets, scripts non déclarés | Oui |
| 7 | Licence : avertissement si aucune licence n'est déclarée | Non |
| 8 | Évaluation réaliste présente (`evals/evals.json`, au moins un cas) | Oui |
| 9 | Résultat attendu décrit, au moins deux attentes vérifiables par cas | Oui |
| 10 | Complétude documentaire : sections obligatoires, longueur ≤ 500 lignes | Oui |

En complément, la CI exécute `skills-ref validate` (validateur de référence, épinglé sur un commit relu) sur chaque skill.

## 5. Orchestration

Voir `skills/ai-workflows/skill-router/`. Ordre de précédence en cas de conflit :

1. Sécurité et exigences légales applicables
2. Contraintes projet et exigences validées
3. Guides officiels de plateforme
4. Design system établi du projet
5. Skills réutilisables pertinents
6. Bonnes pratiques communautaires

## 6. Cycle de vie

* Nouveau skill : `status: beta`, passe en `stable` après une évaluation exécutée et relue.
* Modification de comportement : incrément mineur ; changement d'interface (entrées, sorties) : majeur.
* Retrait : `status: deprecated` pendant une version avant suppression, avec le remplaçant indiqué.
