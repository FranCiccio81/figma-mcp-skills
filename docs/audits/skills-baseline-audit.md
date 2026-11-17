# Audit de référence de la bibliothèque de skills

| Champ | Valeur |
|---|---|
| Dépôt | `FranCiccio81/figma-mcp-skills` (public, aucune licence déclarée au niveau du dépôt) |
| Commit de référence | `4c3de4479dd5d0bc4b40ef934e4e0f2b697f78dc` (`main`, 81 commits) |
| Date de l'audit | 2026-11-17 |
| Branche de travail | `claude/skills-library-modernization` |
| État Git au départ | arbre propre, aucune modification non commitée |
| Méthode | lecture intégrale des skills, rules, docs, specs et du workflow CI ; vérification des affirmations factuelles contre les sources officielles (voir `docs/sources/source-registry.md`) ; calcul des contrastes avec la formule WCAG |

## 1. Inventaire

Le dépôt contient trois natures de contenu très différentes, qu'il faut traiter séparément.

| Zone | Contenu | Nature |
|---|---|---|
| `.claude/skills/component/` | Skill `component` (6 actions, 24 fichiers, frontmatter valide) | Skill réutilisable, fonctionnelle |
| `skills/01..04-*/SKILL.md` | 4 fichiers Markdown de 370 à 520 lignes | Guides, pas des skills au sens de la spec (aucun frontmatter) |
| `rules/` | Rules Figma MCP universelles et rules Bridge | Mélange universel et spécifique Swissquote |
| `.claude/CLAUDE.md` | Rules globales Claude Code | Mélange universel et spécifique Bridge |
| `docs/workflow-figma-mcp.md` | Workflow MCP en 3 étapes | Doublon partiel des rules |
| `components/input-documentation.md`, `ds/specs/active/button-spec.md` | Livrables produits avec les skills | Exemples de sorties, spécifiques au fichier Figma de test |
| `skills-lock.json`, `SETUP.md` | Registre de 59 skills tiers installés hors dépôt (`.agents/` ignoré) | Inventaire local, non reproductible tel quel |
| `.mcp.json` | Serveur Figma desktop en HTTP | Configuration valide |
| `.github/workflows/boussole-ci.yml` | CI de l'application Boussole | Aucun contrôle des skills |
| `boussole/`, `cv-job-matching/`, `pension-partner-app/` | Trois projets applicatifs (≈ 440 fichiers) | Hors périmètre skills, à ne pas toucher |

## 2. Constats majeurs

1. **Les quatre skills historiques ne sont pas chargeables.** `skills/01-design-system` à `skills/04-accessibility` n'ont pas de frontmatter YAML (`name`, `description` requis par la spec Agent Skills). De plus, Claude Code découvre les skills de projet dans `.claude/skills/`, et `.gitignore` y exclut tout sauf `component`. Ces fichiers ne s'activent donc jamais automatiquement : ils servent de documentation.
2. **Une seule skill conforme.** `component` respecte la spec (nom, description, licence, `metadata.version` en chaîne). Sa provenance n'est pas documentée : elle déclare `license: MIT` sans auteur, n'apparaît pas dans `skills-lock.json` et `SETUP.md` la situe dans `~/.agents/skills/`. À clarifier avant toute redistribution.
3. **Erreurs factuelles.**
   - `CLAUDE.md` indique un contraste de 2,85:1 pour `Grey/400` (#9CA3AF) sur blanc. La valeur calculée est **2,54:1**. La conclusion (interdit pour du texte) reste juste.
   - `Primary/500` (#3B82F6) sur blanc donne **3,68:1** : insuffisant pour du texte normal, ce que les rules ne signalent pas alors que ce token sert de couleur d'action.
   - La skill accessibilité cite le critère 2.5.5 comme exigence de taille de cible à 44 px. 2.5.5 est de niveau **AAA** ; le critère AA de WCAG 2.2 est 2.5.8 (24 × 24 px CSS). Les 44 pt (Apple) et 48 dp (Android) sont des recommandations de plateforme, pas des critères WCAG AA.
   - Le référentiel ciblé est WCAG 2.1 alors que WCAG 2.2 est la Recommandation W3C en vigueur depuis le 5 octobre 2023.
   - "Pressed dans Figma = `:focus-visible`" est présenté comme une règle générale. C'est une observation propre au fichier de test ; en CSS, l'état pressé correspond à `:active`. Il faut vérifier variante par variante.
4. **Configurations MCP contradictoires.** `.mcp.json` et `README.md` utilisent `http://127.0.0.1:3845/mcp` en HTTP ; `SETUP.md` documente l'ancien transport SSE (`/sse`). Les URLs d'assets alternent entre `localhost:3845` et `127.0.0.1:3845`. Figma recommande désormais le serveur distant `https://mcp.figma.com/mcp`, le serveur desktop restant valable.
5. **Ordre du flux MCP divergent.** Cinq fichiers décrivent le flux Figma avec des ordres différents (`get_metadata` d'abord, ou `get_design_context` d'abord comme dans le guide officiel Figma). Aucun ne prévoit la vérification préalable des outils réellement exposés.
6. **Doublons.** Le flux MCP, les warnings et la table Figma vers CSS sont répétés dans `CLAUDE.md`, `rules/figma-mcp-rules.md`, `docs/workflow-figma-mcp.md` et les skills 02 et 03.
7. **Contenu propriétaire dans un dépôt public.** Le dépôt est public. Il contient des règles internes du design system Bridge de Swissquote, une clé de fichier Figma (`YMXQcB0QWivNJGwH3jJUI7`) dans `button-spec.md`, et des captures de valeurs de tokens. Rien de secret n'a été trouvé (aucun jeton ni identifiant), mais la publication relève d'une décision de l'entreprise.
8. **Absence de licence de dépôt.** Sans fichier `LICENSE`, le contenu est "tous droits réservés" par défaut, ce qui contredit le `license: MIT` de `component` et empêche toute réutilisation sereine.
9. **Inventaire tiers non vérifié.** `skills-lock.json` référence 59 skills (41 de `wondelai/skills`) par hash de contenu, sans commit ni licence. `SETUP.md` annonce 35 skills `wondelai` contre 41 dans le lock. Plusieurs skills tiers résument des ouvrages sous droits ; leur licence n'a pas été vérifiée.
10. **Aucun contrôle qualité automatisé** pour les skills : pas de validation de spec, de liens, de doublons ni d'évaluations.
11. **Polices embarquées.** `pension-partner-app/assets/fonts` contient Hanken Grotesk (SIL OFL) et Remix Icon (Apache 2.0) : licences compatibles, rien à corriger.

## 3. Tableau priorisé

Échelle de qualité : 1 (inutilisable) à 5 (référence). Priorité : P0 (bloquant), P1 (important), P2 (amélioration).

| Actif existant | Rôle actuel | Qualité | Problème identifié | Action recommandée | Risque | Priorité |
|---|---|---|---|---|---|---|
| `skills/01-design-system` | Guide tokens 4 tiers, Code Connect, Bridge | 2 | Pas de frontmatter, mélange Bridge et universel, format Style Dictionary présenté sans référence DTCG | Extraire l'universel dans `design-token-architecture` ; archiver l'original dans `docs/legacy-skills/` | Faible | P0 |
| `skills/02-design-to-code` | Figma vers React et Compose | 3 | Pas de frontmatter, flux MCP non vérifié, templates Bridge présentés comme génériques | Répartir dans `figma-design-context`, `react-component-engineering`, `compose-implementation` ; archiver | Faible | P0 |
| `skills/03-ux-research-specs` | Specs, flows, handoff | 3 | Pas de frontmatter, "recherche" sans méthode de recherche réelle | Répartir dans `figma-implementation-spec`, `research-planning`, `interaction-design-spec` ; archiver | Faible | P0 |
| `skills/04-accessibility` | Audit WCAG 2.1 | 3 | Pas de frontmatter, WCAG 2.1, confusion 2.5.5 et 2.5.8 | Remplacer par `accessibility-audit` (WCAG 2.2) et les skills plateforme ; archiver | Moyen (référentiel) | P0 |
| `.claude/skills/component` | Workflow composant DS complet | 4 | Provenance non documentée, description longue en liste de déclencheurs, WCAG 2.1 | Conserver le contenu, déplacer en `skills/design-systems/component` avec lien symbolique, enrichir la metadata | Faible | P1 |
| `.claude/CLAUDE.md` | Rules globales | 3 | Contraste erroné, règle "Pressed" généralisée | Corriger les faits, pointer vers les skills | Faible | P1 |
| `rules/figma-mcp-rules.md` | Rules MCP universelles | 3 | Doublon, ordre du flux différent du guide Figma | Aligner sur `figma-design-context`, ajouter la vérification des outils | Faible | P1 |
| `rules/bridge-design-system-rules.md` | Rules Bridge | 3 | Propriétaire, publié | Conserver en l'état ; décision de publication à prendre par le propriétaire | Moyen (confidentialité) | P1 |
| `docs/workflow-figma-mcp.md` | Workflow MCP | 3 | Doublon | Pointer vers la skill `figma-design-context` | Faible | P2 |
| `components/input-documentation.md` | Exemple de handoff | 4 | Lié à un fichier de test | Conserver comme exemple de sortie | Faible | P2 |
| `ds/specs/active/button-spec.md` | Spec produite par `component spec` | 4 | Clé de fichier Figma publique | Conserver ; signaler | Faible | P2 |
| `README.md` | Présentation | 2 | URL `TON_USERNAME`, catalogue obsolète, aucune mention des projets applicatifs | Réécrire | Faible | P0 |
| `SETUP.md` | Inventaire local de 63 skills | 2 | Transport SSE obsolète, comptages incohérents, non reproductible | Corriger le transport, renvoyer vers le registre | Faible | P1 |
| `skills-lock.json` | Lock du CLI `skills` | 3 | Pas de licence ni de commit par entrée | Conserver ; tracer les sources dans le registre des sources | Faible | P2 |
| `.mcp.json` | Serveur Figma desktop | 4 | Pas d'option distante documentée | Conserver ; documenter le serveur distant dans le README | Faible | P2 |
| Licence du dépôt | Absente | 1 | Contradiction avec `license: MIT` | Choisir une licence (décision du propriétaire) ; les nouvelles skills déclarent `MIT` en attente | Moyen | P1 |
| CI des skills | Absente | 1 | Aucun contrôle | Validateur, tests, registre généré, workflow GitHub | Faible | P0 |
| Projets `boussole/`, `cv-job-matching/`, `pension-partner-app/` | Applications | n/a | Hors périmètre, alourdissent le dépôt | Ne pas modifier ; envisager des dépôts séparés | Faible | P2 |

## 4. Ce qui fonctionne et doit être préservé

- Les apprentissages terrain du 2026-03-28 (stratégie par sections au-delà de 800 px, warning Code Connect à ignorer pour les specs, double border-radius des composants imbriqués, valeurs codées en dur détectées). Ils sont repris dans `figma-design-context` et `figma-implementation-spec`.
- La skill `component`, son principe "jamais de token créé sans approbation" et son repli quand le MCP est indisponible.
- La convention `ds/specs/active/` et `ds/audits/active/`.

## 5. Suites données dans cette branche

- Les quatre skills historiques sont déplacées, jamais supprimées, dans `docs/legacy-skills/` avec une table de correspondance.
- `component` est déplacée en `skills/design-systems/component/` (v1.2.0) ; `.claude/skills/component` devient un lien symbolique.
- 35 nouvelles skills, réparties en 8 domaines ; catalogue dans `docs/registry/skills-registry.md`.
- Faits corrigés dans `.claude/CLAUDE.md` et `rules/figma-mcp-rules.md` ; transport SSE corrigé dans `SETUP.md` ; README réécrit.
- Validateur, registre généré, installeur, vérification des liens, 44 tests et workflow `skills-ci`.
- Vérification en direct du serveur Figma MCP distant le 2026-11-17 : l'étape `create_session`, absente de toute la documentation du dépôt, est désormais exigée par le serveur ; la lecture du fichier de test est refusée faute de droits (voir `skills/ai-workflows/figma-design-context/evals/RESULTS.md`).

## 6. Décisions qui restent au propriétaire

1. Licence du dépôt (MIT, Apache-2.0 ou propriétaire).
2. Maintien public des règles Bridge, de la clé de fichier Figma et des captures de tokens.
3. Séparation des projets applicatifs dans des dépôts dédiés.
4. Revue de licence et de fidélité des 41 skills `wondelai/skills` du lock avant usage en entreprise.
5. Passage de la règle projet WCAG 2.1 AA à WCAG 2.2 AA.
