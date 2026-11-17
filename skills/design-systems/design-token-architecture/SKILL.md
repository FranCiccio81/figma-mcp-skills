---
name: design-token-architecture
description: >-
  Designs, audits or migrates a design token system: tiers (primitive, semantic,
  component), naming, theming and modes, the DTCG 2025.10 JSON format, Figma variables
  mapping, and the build pipeline to platforms (CSS, iOS, Android). Use when the user
  creates or restructures tokens, defines semantic or component tokens, maps Figma
  variables to code, adds dark mode or brands, or migrates tokens to the DTCG format.
metadata:
  domain: design-systems
  version: "1.0.0"
  status: beta
  scope: universal
  trust: official-derived
  last-reviewed: "2026-11-17"
---

# Design token architecture

## When to use

* Creating or restructuring tokens; adding themes, brands, modes or density.
* Mapping Figma variables and collections to code tokens.
* Migrating to the DTCG format or auditing token usage.
* For a specific project system (for example Bridge) also load its project skill; the project's files are the source of truth.

## Inputs

* Existing token files, Figma variable collections and modes, platforms to serve, build tooling.
* Product constraints: themes, brands, accessibility modes (high contrast), density.

## Procedure

1. **Inventory before designing.** Export current tokens and Figma variables; list duplicates, unused tokens, hard-coded values in code. Never replace existing product tokens without evidence and a migration plan.
2. **Tiers.**
   * *Primitive* (palette, raw scales): never used directly by components.
   * *Semantic* (meaning: `color.text.primary`, `color.action.primary.background`, `space.inset.md`): what most components consume; this is where themes and modes switch.
   * *Component* (only when a component needs to vary independently): `button.primary.background` aliases a semantic token.
3. **Naming.** Pattern such as `category.concept.variant.state` with a closed vocabulary. Names describe intent, never value (`blue-500` is a primitive name, not a semantic one). DTCG forbids `{`, `}`, `.` inside a single name segment and names starting with `$`.
4. **DTCG format.** `$value`, `$type` (inheritable from groups), `$description`, `$deprecated`, `$extensions` (reverse-domain keys); aliases with `{group.token}`; dimensions and durations as `{ "value": 16, "unit": "px" }`; colors as color-space objects. Details: [references/dtcg-format-notes.md](references/dtcg-format-notes.md).
5. **Themes and modes.** Model contexts (light, dark, high contrast, brand) on the semantic tier; use the DTCG Resolver module or the tool's equivalent (Figma variable modes, Style Dictionary or Tokens Studio themes). Each semantic token must resolve in every mode.
6. **Accessibility by construction.** Validate contrast for every text and UI pairing in every mode (4.5:1 text, 3:1 non-text). Store pairings to test, not only colors.
7. **Figma mapping.** Collections mirror tiers; primitives hidden from publishing; semantic variables scoped (for example fill vs stroke vs text) so designers pick the right ones; variable names match token paths.
8. **Pipeline.** One source of truth; transform to platform outputs (CSS custom properties, Swift, Kotlin or Compose theme); version and changelog through `design-system-governance`.
9. **Migration.** Map old to new, ship aliases with `$deprecated` explanations, lint for deprecated usage, remove after a stated period.

## Output

Token architecture document (tiers, naming grammar, modes), example DTCG JSON, Figma collection plan, mapping table old to new, contrast matrix per mode, pipeline description, migration plan.

## Edge cases

* Figma variables cannot express a composite token (typography, shadow): keep composites in code tokens and document the split.
* Values that differ per platform (dp vs pt vs px): keep the semantic name, transform units per platform.
* Teams consuming primitives directly: lint, then migrate component by component.

## Acceptance criteria

* Valid DTCG 2025.10 JSON (types resolvable, no circular aliases).
* Components reference no primitive tokens.
* Every semantic color pairing meets AA contrast in every mode, or is listed as a known exception.
* Migration keeps old names working until the announced removal.

## Sources

* Design Tokens Format Module 2025.10: https://www.designtokens.org/tr/2025.10/format/
* Design Tokens Resolver Module 2025.10: https://www.designtokens.org/tr/2025.10/resolver/
* WCAG 2.2 contrast criteria: https://www.w3.org/TR/WCAG22/
* Figma MCP variables tool: https://developers.figma.com/docs/figma-mcp-server/tools-and-prompts
