# Registre des sources

Ce registre trace la provenance de chaque source utilisée par les skills. Chaque skill cite ses sources par identifiant dans `metadata.sources`, et le validateur (`scripts/validate_skills.py`) refuse un identifiant absent de ce fichier ou un domaine d'URL qui n'y figure pas.

## Règles d'usage

1. **Officiel d'abord.** En cas de divergence, la source officielle de la plateforme ou du standard l'emporte sur toute source communautaire.
2. **Paraphraser, citer, lier.** Aucune documentation n'est copiée en bloc. Les skills résument des règles et renvoient à l'URL canonique.
3. **Popularité n'est pas qualité.** Les étoiles GitHub ne sont jamais un critère d'adoption.
4. **Aucun script tiers exécuté** sans lecture préalable. Les dépôts examinés ici ont été clonés en lecture seule dans un répertoire isolé, sans exécution.
5. **Revalidation.** Toute source est revérifiée au moins tous les 6 mois ou à chaque version majeure de plateforme (WWDC, Google I/O, nouvelle version WCAG ou DTCG).

## Barème

- **Confiance** : A (officiel, mainteneur identifié, licence claire), B (officiel ou reconnu mais licence ou périmètre partiel), C (communautaire sérieux), D (communautaire non vérifié).
- **Pertinence** : 1 (marginale) à 5 (centrale pour ce dépôt).
- **Décision** : `adopté` (sert de fondement à des skills), `référencé` (lié comme lecture, sans contenu repris), `installation optionnelle` (à installer à côté, non copié), `rejeté`, `à évaluer`.

Dernière vérification globale : **2026-11-17**.

## 1. Spécification et dépôts officiels de skills

| ID | Source | Propriétaire | Statut | Licence | Maintenance constatée | Confiance | Pertinence | Décision |
|---|---|---|---|---|---|---|---|---|
| `SPEC-AGENTSKILLS` | https://agentskills.io/specification et https://github.com/agentskills/agentskills | Projet Agent Skills (initié par Anthropic) | Officiel | Apache-2.0 | Commit `83021e2` du 2026-11-04 | A | 5 | **Adopté.** Les règles de `skills-ref` (nom, description ≤ 1024, compatibilité ≤ 500, champs autorisés, nom = dossier) sont reproduites dans le validateur local |
| `REPO-ANTHROPIC-SKILLS` | https://github.com/anthropics/skills | Anthropic | Officiel | Apache-2.0 par skill (`LICENSE.txt`), certaines skills documentaires en source disponible | Commit `e4bb5d9` du 2026-11-16 | A | 3 | **Référencé.** Format `evals/evals.json` de `skill-creator` repris pour les évaluations. `frontend-design`, `webapp-testing` et `skill-creator` recommandés en installation optionnelle |
| `REPO-ANDROID-SKILLS` | https://github.com/android/skills | Google LLC (équipe Android) | Officiel | Apache-2.0 | Commit `c729425` du 2026-11-15, skills datées 2026-08 à 2026-11 | A | 5 | **Installation optionnelle et référencé.** `adaptive`, `edge-to-edge`, `navigation-3`, `testing-setup`, `migration/ios-to-android` couvrent l'implémentation ; nos skills Android délèguent vers elles au lieu de les recopier. Note : leur `metadata` contient des listes, ce qui s'écarte de la spec (valeurs chaîne) |
| `REPO-GOOGLE-SKILLS` | https://github.com/google/skills | Google LLC | Officiel | Apache-2.0 | Commit `5d8e9ea` du 2026-11-17 | A | 1 | **Référencé.** 211 skills essentiellement Cloud, Ads et Identity ; aucune n'est pertinente pour le design produit |
| `REPO-FIGMA-MCP-GUIDE` | https://github.com/figma/mcp-server-guide | Figma | Officiel | Aucune licence déclarée dans le dépôt | Commit `490a73c` du 2026-11-16, plugin `figma` v2.2.211 | B | 5 | **Installation optionnelle.** Plugin officiel (skills `figma-use`, `figma-design-to-code`, `figma-code-connect`, `figma-generate-library`, `figma-swiftui`...). Faute de licence, rien n'est copié ; nos skills Figma orchestrent et renvoient vers elles |
| `DOC-FIGMA-MCP` | https://developers.figma.com/docs/figma-mcp-server/ | Figma | Officiel | Documentation propriétaire | Page "Tools and prompts" consultée le 2026-11-17 | A | 5 | **Adopté.** Liste des outils, serveur distant `https://mcp.figma.com/mcp` recommandé, serveur desktop `http://127.0.0.1:3845/mcp` |

## 2. Apple

| ID | Source | Statut | Licence | Confiance | Pertinence | Décision |
|---|---|---|---|---|---|---|
| `APPLE-HIG` | https://developer.apple.com/design/human-interface-guidelines/ | Officiel | Documentation Apple, tous droits réservés | A | 5 | **Adopté** (paraphrase). Tailles de contrôle par plateforme (iOS et iPadOS 44 × 44 pt par défaut, 28 × 28 pt minimum ; macOS 28 et 20 ; watchOS 44 et 28 ; visionOS 60 et 28 ; tvOS 66 et 56), contrastes, matériaux, Liquid Glass |
| `APPLE-DESIGN` | https://developer.apple.com/design/ | Officiel | Idem | A | 3 | Référencé |
| `APPLE-DESIGN-RESOURCES` | https://developer.apple.com/design/resources/ | Officiel | Licence d'usage Apple, redistribution interdite | A | 3 | **Référencé uniquement.** Aucun kit ni gabarit n'est redistribué dans ce dépôt |
| `APPLE-SWIFTUI` | https://developer.apple.com/documentation/swiftui/ | Officiel | Idem | A | 5 | Adopté (noms d'API vérifiés uniquement sur cette documentation) |
| `APPLE-ACCESSIBILITY` | https://developer.apple.com/accessibility/ | Officiel | Idem | A | 5 | Adopté |
| `APPLE-LIQUID-GLASS` | https://developer.apple.com/documentation/technologyoverviews/liquid-glass | Officiel | Idem | A | 4 | Adopté. Liquid Glass introduit avec iOS 26, iPadOS 26, macOS Tahoe 26, watchOS 26, tvOS 26 et visionOS 26 ; variantes `regular` et `clear` |

Apple ne publie pas de dépôt officiel de skills à la date de vérification. Les dépôts communautaires SwiftUI identifiés (voir section 7) sont `à évaluer`.

## 3. Android et Material

| ID | Source | Statut | Licence | Confiance | Pertinence | Décision |
|---|---|---|---|---|---|---|
| `ANDROID-DESIGN` | https://developer.android.com/design/ et https://developer.android.com/design/ui/mobile | Officiel | Licences en pied de page du site (contenu Creative Commons Attribution, code Apache-2.0) | A | 5 | Adopté |
| `ANDROID-COMPOSE` | https://developer.android.com/develop/ui/compose | Officiel | Idem | A | 5 | Adopté |
| `ANDROID-ADAPTIVE` | https://developer.android.com/develop/adaptive-apps | Officiel | Idem | A | 5 | Adopté. Classes de taille de fenêtre en largeur : compact < 600 dp, medium 600 à 840, expanded 840 à 1200, large 1200 à 1600, extra-large ≥ 1600 (large et extra-large via `supportLargeAndXLargeWidth`) |
| `M3` | https://m3.material.io/ | Officiel (Google) | Documentation Google | A | 5 | Adopté (cible tactile 48 × 48 dp, rôles de couleur, typographie, couleur dynamique) |

## 4. Design systems de référence

Consultés comme points de comparaison, jamais comme modèles à imposer au design system du projet.

| ID | Source | Propriétaire | Licence | Confiance | Pertinence | Décision |
|---|---|---|---|---|---|---|
| `DS-CARBON` | https://carbondesignsystem.com/ | IBM | Apache-2.0 (code) | A | 3 | Référencé (gouvernance, tokens, accessibilité) |
| `DS-ATLASSIAN` | https://atlassian.design/ | Atlassian | Propriétaire | A | 3 | Référencé (tokens sémantiques, contenu) |
| `DS-FLUENT2` | https://fluent2.microsoft.design/ | Microsoft | Propriétaire, code MIT | A | 3 | Référencé |
| `DS-SPECTRUM` | https://spectrum.adobe.com/ | Adobe | Propriétaire, code Apache-2.0 | A | 3 | Référencé. Spectrum 2 est la version active (`s2.spectrum.adobe.com`) |
| `DS-POLARIS` | https://polaris.shopify.com/ | Shopify | Propriétaire, code MIT | B | 2 | Référencé avec réserve : Polaris React est déprécié au profit des Polaris Web Components documentés sur shopify.dev |
| `DS-USWDS` | https://designsystem.digital.gov/ | US GSA | Domaine public (CC0) | A | 3 | Référencé (accessibilité, contenu, gouvernance ouverte) |
| `DTCG-2025-10` | https://www.designtokens.org/TR/2025.10/ | W3C Design Tokens Community Group | Accord W3C Community Final Specification Agreement | A | 5 | **Adopté.** Première version stable publiée le 2025-10-28 : modules Format, Color et Resolver |

## 5. Accessibilité

| ID | Source | Statut | Licence | Confiance | Pertinence | Décision |
|---|---|---|---|---|---|---|
| `W3C-WAI` | https://www.w3.org/WAI/ | Officiel W3C | W3C Document License | A | 5 | Adopté |
| `W3C-WCAG22` | https://www.w3.org/WAI/standards-guidelines/wcag/ (WCAG 2.2, Recommandation du 2023-10-05) | Officiel W3C | Idem | A | 5 | **Adopté comme référentiel par défaut.** 2.5.8 Target Size (Minimum) AA = 24 × 24 px CSS ; 2.5.5 Target Size (Enhanced) AAA = 44 × 44 px CSS |
| `W3C-APG` | https://www.w3.org/WAI/ARIA/apg/ | Officiel W3C | Idem, exemples sous licence W3C Software | A | 5 | Adopté (patterns clavier et ARIA) |

## 6. Méthodes produit et UX

| ID | Source | Statut | Licence | Confiance | Pertinence | Décision |
|---|---|---|---|---|---|---|
| `NNG` | https://www.nngroup.com/ | Référence professionnelle (Nielsen Norman Group) | Tous droits réservés | A | 4 | Référencé et paraphrasé (10 heuristiques, échelle de sévérité 0 à 4, tests utilisateurs) |
| `DESIGN-COUNCIL` | https://www.designcouncil.org.uk/ | Organisme public britannique | Tous droits réservés | A | 3 | Référencé (Double Diamond, Systemic Design Framework) |
| `STRATEGYZER` | https://www.strategyzer.com/ | Strategyzer AG | Canvas sous CC BY-SA, ouvrages sous droits | A | 3 | Référencé (Value Proposition Canvas, Business Model Canvas, tests d'hypothèses) |
| `TISDD` | https://www.thisisservicedesigndoing.com/ | Auteurs de *This Is Service Design Doing* | Méthodes en CC BY-SA 4.0 | A | 3 | Référencé (journey maps, service blueprints) |

## 7. Sources communautaires examinées

Chaque dépôt a été cloné en lecture seule et inspecté (structure, licence, présence de scripts, hooks, téléchargements, instructions suspectes). Aucun n'a été exécuté.

| ID | Source | Licence | Dernier commit | Constat de sécurité | Confiance | Pertinence | Décision |
|---|---|---|---|---|---|---|---|
| `COMM-CUELLARFR` | https://github.com/cuellarfr/design-skills | MIT (Carlos C.) | `7e25e66`, 2026-09-30 | Markdown uniquement, aucun script, aucune instruction suspecte | C | 4 | **Installation optionnelle.** Dix skills UX riches (recherche, critique, accessibilité WCAG 2.2, journey mapping, UX writing). Non copiées : nos skills restent plus courtes et liées à nos sources ; la doublure fonctionnelle est signalée au routeur |
| `COMM-IMPECCABLE` | https://github.com/pbakaus/impeccable | Apache-2.0 | `d41d986`, 2026-11-16 | Lanceur shell qui télécharge un binaire au premier lancement (vérifié par somme de contrôle) et hooks Claude Code exécutés à chaque `Edit`, `Write` et `Stop` | C | 3 | **Installation optionnelle après revue du binaire.** Ne pas activer ses hooks dans un dépôt d'entreprise sans validation sécurité |
| `COMM-FLITZRRR` | https://github.com/flitzrrr/frontend-design-skills | MIT | `d607ba3`, 2026-04-06 | Contenu généré par scraping de galeries (Awwwards, Dribbble, Behance, Mobbin...) ; provenance du contenu dérivé incertaine ; installeur `npx` | D | 2 | **Rejeté.** Risque de licence sur le contenu distillé, orientation tendances visuelles, peu actif |
| `COMM-WONDELAI` | https://github.com/wondelai/skills | Non vérifiée | n/a | Non inspecté (accès non ouvert dans cette session) | D | 3 | **À évaluer.** 41 entrées dans `skills-lock.json`, résumés d'ouvrages sous droits : vérifier licence et fidélité avant tout usage en entreprise |
| `COMM-SWIFTUI` | https://github.com/AvdLee/SwiftUI-Agent-Skill, https://github.com/twostraws/swiftui-agent-skill | MIT annoncé | n/a | Non inspectés | D | 3 | **À évaluer.** Candidats pour compléter `swiftui-implementation` |

## 8. Domaines autorisés dans les skills

Le validateur accepte uniquement les URLs dont le domaine figure ci-dessous (ou un sous-domaine). Ajouter un domaine exige d'ajouter d'abord la source au registre.

<!-- allowed-domains:start -->
- agentskills.io
- github.com
- developers.figma.com
- figma.com
- help.figma.com
- developer.apple.com
- developer.android.com
- m3.material.io
- carbondesignsystem.com
- atlassian.design
- fluent2.microsoft.design
- spectrum.adobe.com
- polaris.shopify.com
- designsystem.digital.gov
- designtokens.org
- www.w3.org
- nngroup.com
- designcouncil.org.uk
- strategyzer.com
- thisisservicedesigndoing.com
- web.dev
- developer.mozilla.org
- owasp.org
- cheatsheetseries.owasp.org
- react.dev
- testing-library.com
- playwright.dev
- storybook.js.org
- typescriptlang.org
<!-- allowed-domains:end -->

Sources techniques complémentaires utilisées par les skills d'ingénierie (toutes officielles, documentation sous licence ouverte ou propriétaire selon l'éditeur, confiance A, décision `référencé`) :

| ID | Source |
|---|---|
| `WEB-MDN` | https://developer.mozilla.org/ (Mozilla, CC BY-SA 2.5) |
| `WEB-DEV` | https://web.dev/ (Google, CC BY 4.0), Core Web Vitals |
| `OWASP` | https://owasp.org/ et https://cheatsheetseries.owasp.org/ (CC BY-SA 4.0) |
| `REACT-DOCS` | https://react.dev/ (Meta, CC BY 4.0) |
| `TS-DOCS` | https://www.typescriptlang.org/ (Microsoft) |
| `TESTING-LIBRARY` | https://testing-library.com/ (MIT) |
| `PLAYWRIGHT` | https://playwright.dev/ (Microsoft, Apache-2.0) |
| `STORYBOOK` | https://storybook.js.org/ (MIT) |
| `FIGMA-HELP` | https://help.figma.com/ (Figma, variables et Code Connect) |
