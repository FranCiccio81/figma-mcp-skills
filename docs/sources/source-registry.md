# Registre des sources

Dernière vérification globale : 2026-11-17.

Barèmes :
* **Confiance** (1 à 5) : 5 = éditeur officiel de la norme ou de la plateforme ; 3 = auteur identifiable, contenu relu, maintenance active ; 1 = provenance incertaine.
* **Pertinence** (1 à 5) pour cette bibliothèque.
* **Niveau de vérification** : *Inspecté* (dépôt cloné et contenu lu), *Vérifié* (page ou recherche officielle consultée dans cette session), *Référencé* (URL canonique connue, contenu non relu dans cette session : à relire avant de s'appuyer sur un détail).

La popularité (étoiles GitHub) n'a été utilisée comme critère pour aucune décision.

## 1. Spécification Agent Skills et skills officiels

| Source | Propriétaire | Statut | Licence | Dernière activité | Vérification | Confiance | Pertinence | Décision |
|---|---|---|---|---|---|---|---|---|
| https://github.com/agentskills/agentskills (spécification `docs/specification.mdx`, validateur `skills-ref`) | Projet Agent Skills (initié par Anthropic) | Officiel | Apache-2.0 | 2026-11-04 | Inspecté | 5 | 5 | **Adopté** comme norme. Règles de frontmatter réimplémentées dans `tools/validate_skills.py`. `skills-ref` (déclaré outil de démonstration par ses auteurs) exécuté en CI en complément, épinglé sur un commit. |
| https://agentskills.io/specification | Projet Agent Skills | Officiel | Apache-2.0 | n/a | URL bloquée par le proxy de session ; contenu identique lu dans le dépôt source | 5 | 5 | Adopté (via le dépôt) |
| https://github.com/anthropics/skills | Anthropic | Officiel | Apache-2.0 par skill (`LICENSE.txt`) | 2026-11-16 | Inspecté (20 skills, aucune exécution) | 5 | 3 | **Référencé, non copié.** `skill-creator` fournit le schéma `evals/evals.json` repris ici. `frontend-design` et `webapp-testing` recommandés à l'installation. |
| https://github.com/android/skills | Google (Android) | Officiel | Apache-2.0 | 2026-11-15 | Inspecté (37 skills ; validés avec `skills-ref`) | 5 | 5 | **Adopté par référence.** Nos skills Android délèguent l'implémentation détaillée à `edge-to-edge`, `adaptive`, `navigation-3`, `testing-setup`, `migrate-xml-views-to-jetpack-compose`. Note de sécurité : `devtools/android-cli` contient `curl … \| bash` vers `dl.google.com` (domaine officiel) ; ne jamais l'exécuter automatiquement. |
| https://github.com/google/skills | Google | Officiel | Apache-2.0 | 2026-11-17 | Inspecté (211 skills) | 5 | 1 | **Non adopté** : quasi exclusivement Google Cloud, Ads, identité. Hors périmètre design. |
| https://github.com/figma/mcp-server-guide | Figma | Officiel (Beta) | Figma Developer Terms (pas une licence open source) | 2026-11-16 | Inspecté | 5 | 5 | **Adopté par référence**, non copié (conditions d'utilisation propriétaires). Recommandé à l'installation via le plugin Figma. |
| https://developers.figma.com/docs/figma-mcp-server/ | Figma | Officiel | Documentation | n/a | Vérifié (liste des outils, serveurs distant et desktop) | 5 | 5 | Adopté |

## 2. Apple

| Source | Statut | Vérification | Confiance | Décision |
|---|---|---|---|---|
| https://developer.apple.com/design/human-interface-guidelines/ | Officiel | Référencé | 5 | Source primaire des skills `apple-hig-review` et `apple-accessibility` |
| https://developer.apple.com/documentation/swiftui/ | Officiel | Vérifié pour `glassEffect(_:in:)`, `Glass`, `GlassEffectContainer` (disponibles à partir d'iOS 26, iPadOS 26, macOS 26, tvOS 26, watchOS 26) | 5 | Source primaire de `swiftui-implementation` |
| https://developer.apple.com/documentation/technologyoverviews/adopting-liquid-glass | Officiel | Vérifié | 5 | Utilisé pour la section Liquid Glass |
| https://developer.apple.com/design/resources/ | Officiel | Référencé | 5 | Kits UI cités, non redistribués |
| https://developer.apple.com/accessibility/ | Officiel | Référencé | 5 | Référence VoiceOver, Dynamic Type |

## 3. Android et Material

| Source | Statut | Vérification | Confiance | Décision |
|---|---|---|---|---|
| https://developer.android.com/develop/ui/compose/layouts/adaptive/use-window-size-classes | Officiel | Vérifié (largeur : compact < 600 dp, medium 600 à 840, expanded 840 à 1200, large 1200 à 1600, extra-large ≥ 1600 ; hauteur : 480 et 900 dp) | 5 | Adopté |
| https://developer.android.com/about/versions/16/behavior-changes-16 | Officiel | Vérifié (désactivation de `windowOptOutEdgeToEdgeEnforcement` pour targetSdk 36 ; predictive back par défaut ; contraintes d'orientation ignorées sur grands écrans) | 5 | Adopté |
| https://developer.android.com/design/ui/mobile | Officiel | Référencé | 5 | Adopté |
| https://developer.android.com/develop/ui/compose | Officiel | Référencé | 5 | Adopté |
| https://m3.material.io/ | Officiel (Google) | Référencé | 5 | Adopté pour rôles de couleur, typographie, cibles tactiles 48 × 48 dp |

## 4. Design systems publics

Utilisés comme références comparatives pour les skills `component-api-design`, `design-system-governance` et `design-token-architecture`. Aucun contenu copié. Contenu non relu dans cette session : statut *Référencé*.

| Source | Propriétaire | Licence de la documentation | Confiance |
|---|---|---|---|
| https://carbondesignsystem.com/ | IBM | Code Apache-2.0 | 4 |
| https://atlassian.design/ | Atlassian | Propriétaire | 4 |
| https://fluent2.microsoft.design/ | Microsoft | Code MIT | 4 |
| https://spectrum.adobe.com/ | Adobe | Propriétaire | 4 |
| https://polaris.shopify.com/ | Shopify | Code MIT | 4 |
| https://designsystem.digital.gov/ | GSA (gouvernement américain) | Domaine public | 5 |

## 5. Normes de tokens et d'accessibilité

| Source | Statut | Vérification | Confiance | Décision |
|---|---|---|---|---|
| https://www.designtokens.org/tr/2025.10/ (Format, Color, Resolver modules) | W3C Community Group, première version stable 2025.10 (28 octobre 2025) | Vérifié | 5 | **Format cible** de `design-token-architecture` |
| https://www.w3.org/TR/WCAG22/ | Recommandation W3C (octobre 2023) | Référencé | 5 | Norme cible des skills d'accessibilité (niveau AA) |
| https://www.w3.org/WAI/ARIA/apg/ | W3C WAI | Référencé | 5 | Patterns clavier et ARIA |
| https://www.w3.org/WAI/ | W3C WAI | Référencé | 5 | Adopté |

## 6. Méthodes produit et UX

Cadres utilisés de façon critique, sans reproduction de contenu protégé.

| Source | Usage | Confiance |
|---|---|---|
| https://www.nngroup.com/ | Heuristiques de Nielsen, échelle de sévérité, méthodes de test | 4 |
| https://www.designcouncil.org.uk/ | Double diamant | 4 |
| https://www.strategyzer.com/ | Value Proposition Canvas | 4 |
| https://www.thisisservicedesigndoing.com/ | Blueprint de service, méthodes | 4 |
| Teresa Torres, *Continuous Discovery Habits* (2021) | Opportunity Solution Tree (concept cité, non reproduit) | 4 |

## 7. Ingénierie frontend et qualité

Sources primaires des skills `engineering/*` et `quality/visual-regression-qa`. Statut *Référencé* : URL canoniques des éditeurs, contenu non relu en détail dans cette session.

| Source | Propriétaire | Statut | Confiance |
|---|---|---|---|
| https://react.dev/ | Meta (React) | Officiel | 5 |
| https://www.typescriptlang.org/docs/ | Microsoft | Officiel | 5 |
| https://developer.mozilla.org/ | Mozilla | Référence de facto | 5 |
| https://web.dev/ | Google Chrome | Officiel (Core Web Vitals : LCP ≤ 2,5 s, INP ≤ 200 ms, CLS ≤ 0,1 au 75e centile) | 5 |
| https://testing-library.com/docs/guiding-principles | Testing Library | Officiel du projet | 4 |
| https://playwright.dev/docs/intro | Microsoft (Playwright) | Officiel | 5 |
| https://owasp.org/ et https://cheatsheetseries.owasp.org/ | OWASP Foundation | Référence sécurité | 5 |
| https://google.github.io/eng-practices/ | Google | Guide public de revue de code | 4 |
| https://semver.org/ | Projet SemVer | Spécification | 5 |
| https://www.producttalk.org/opportunity-solution-trees/ | Teresa Torres (auteure de la méthode) | Source primaire de la méthode | 4 |
| https://developer.apple.com/documentation/xctest | Apple | Officiel | 5 |

## 8. Bridge 2.0 (sources internes Swissquote)

| Source | Propriétaire | Statut | Vérification | Confiance | Décision |
|---|---|---|---|---|---|
| Archive `bridge-platform-skills.zip` v0.2 (12 novembre 2026), fournie par le propriétaire du dépôt | Équipe design Swissquote | Interne | Inspectée (12 fichiers, aucun script, aucun secret ; `bridge-web` valide avec `skills-ref`) | 4 | **Adoptée** : 5 skills plateforme importés tels quels puis complétés (métadonnées, sections, evals) |
| Figma Bridge 2.0 : Foundations, Components Library, Mobile library 2.0 (clés citées dans les skills) | Swissquote | Interne, source de vérité | Non lue dans cette session (lecture par le Figma MCP au moment de l'usage) | 5 | Source de vérité ; l'instantané `skills/bridge/_shared/bridge-foundations.md` sert de repli |
| https://www.radix-ui.com/primitives | WorkOS (Radix UI) | Officiel du projet | Référencé | 4 | Primitives des composants React Bridge (comportement clavier et focus) |

Risque : ces sources décrivent un design system d'entreprise. Leur publication dans un dépôt public relève d'une décision du propriétaire (voir l'audit).

## 9. Candidats communautaires

| Source | Licence | Dernière activité | Vérification | Analyse | Confiance | Décision |
|---|---|---|---|---|---|---|
| https://github.com/cuellarfr/design-skills | MIT | 2026-09-30 | Inspecté (10 skills, valides, aucun script) | Contenu de qualité correcte, ancré dans des principes nommés ; un seul auteur | 3 | **Inspiration seulement.** Non vendorisé pour éviter les doublons avec nos skills UX. |
| https://github.com/pbakaus/impeccable | Apache-2.0 | 2026-11-16 | Inspecté | Le setup exécute un binaire téléchargé au premier lancement ; champs de frontmatter hors spécification (`version`, `user-invocable`, `argument-hint`) ; copies multiples par agent | 2 | **Rejeté pour intégration.** Installation individuelle possible après revue du binaire. |
| https://github.com/flitzrrr/frontend-design-skills | MIT | 2026-04-06 | Inspecté | Inactif depuis 7 mois ; scripts de scraping ; référence WCAG 2.1 | 2 | **Rejeté.** |
| https://github.com/wondelai/skills (41 entrées de `skills-lock.json`) | MIT (dépôt) | 2026-11-13 | Inspecté sommairement | Skills dérivés de livres sous droits ; la licence MIT du dépôt ne règle pas la question des œuvres sources | 2 | **Statu quo** : laissé dans le lockfile, revue de licence recommandée avant réutilisation dans des livrables. |

## 10. Règles de mise à jour

1. Toute nouvelle source passe par ce registre avant d'être citée dans un skill.
2. Un skill qui s'appuie sur une source *Référencée* pour un détail technique (nom d'API, seuil chiffré) doit la faire passer en *Vérifiée*.
3. Revue trimestrielle : dates de dernière activité, changements de licence, nouvelles versions (WCAG, DTCG, iOS, Android).
