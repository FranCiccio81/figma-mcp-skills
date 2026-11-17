---
name: design-token-architecture
description: >-
  Designs, audits and migrates design token systems: tiers (primitive, semantic, component),
  naming, theming and modes, DTCG 2025.10 file format, aliasing rules, platform outputs (CSS,
  Compose, SwiftUI) and a safe migration plan for existing product tokens. Use when asked to create
  or restructure tokens, define semantic tokens, convert tokens to the DTCG format, add dark mode or
  brand themes, audit hardcoded values or plan a token migration. Do not use to map a single Figma
  frame to existing tokens (use figma-token-mapping).
license: MIT
metadata:
  version: "1.0.0"
  domain: design-systems
  status: beta
  trust: official-derived
  sources: "DTCG-2025-10,W3C-WCAG22,M3,APPLE-HIG,DS-CARBON,DS-ATLASSIAN,FIGMA-HELP"
  platforms: "any"
  last-reviewed: "2026-11-17"
---

# Design token architecture

Tokens encode design decisions. Primitives say what values exist; semantic tokens say what they
are for; component tokens say where they are used. The project's existing tokens are the
starting point, never something to replace silently.

## When to use

- Setting up tokens for a new design system or product.
- Restructuring a flat palette into tiers, or adding modes (dark, high contrast, brand).
- Converting Tokens Studio, Style Dictionary or Figma variables to the DTCG format.
- Auditing code or Figma for hardcoded values.

## Inputs

- Existing token files, CSS custom properties, Figma variable collections and modes.
- Platforms to support (web, iOS, Android) and the build tool (for example Style Dictionary).
- Brand, theme and accessibility requirements (contrast targets).
- The project's naming convention and any token rules in its `CLAUDE.md` (they take precedence).

## Workflow

1. **Inventory** what exists: files, formats, counts per category, naming patterns, consumers.
   Record hardcoded values found in code and Figma separately.
2. **Decide the tiers** with the team. A common model is three tiers (primitive, semantic,
   component), optionally a responsive or breakpoint tier. Keep the project's tier model if one
   exists.
3. **Name tokens** consistently: category, concept or property, variant, state, scale
   (for example `color.action.primary.hover`, `space.inset.md`). Semantic names describe intent,
   never values (`color.text.subtle`, not `color.grey-500`).
4. **Alias, do not copy:** semantic tokens reference primitives; component tokens reference
   semantic tokens. Avoid skipping tiers except where documented.
5. **Model modes** (light, dark, high contrast, brands) at the semantic tier. In DTCG 2025.10 use
   separate token sets combined with the Resolver module; in Figma use variable collection modes.
6. **Write DTCG files** following [references/dtcg-quick-reference.md](references/dtcg-quick-reference.md):
   `$value`, `$type`, `$description`, `$deprecated`, aliases `{group.token}`, `$extensions` for
   tool-specific data. Validate against the published spec, not memory.
7. **Check accessibility of pairs:** every text and background semantic pair meets the contrast
   target (WCAG 2.2: 4.5:1 for normal text, 3:1 for large text and UI components). Compute, do not estimate.
8. **Plan platform output:** CSS custom properties, Compose `ColorScheme`/`Typography` or custom
   `CompositionLocal`, SwiftUI `Color` assets or extensions. Keep naming traceable across platforms.
9. **Plan migration** for existing products: mapping table old to new, deprecation aliases with a
   removal version, codemods or search patterns, visual regression checks, communication. Never
   remove or rename a token in use without this plan and evidence of the need.

## Outputs

- Token architecture document: tiers, naming grammar, modes, governance rules.
- DTCG JSON examples or files for the agreed scope.
- Contrast table for semantic pairs.
- Migration table (old, new, status, deprecation version) when changing an existing system.
- Audit report of hardcoded values (location, value, suggested token, confidence).

## Edge cases

- **Values without a matching token:** propose the closest token and flag the difference;
  creating a token requires owner approval.
- **Figma variable names differ from code names:** keep a mapping file, do not rename one side
  without the other.
- **Opacity-based states** (for example Material state layers): document the formula as a token
  or composite rather than precomputing dozens of colors.
- **Tooling lagging the spec:** note which features (Color module color spaces, Resolver) the
  current build tool supports and keep a fallback.

## Acceptance criteria

- [ ] No semantic token name contains a raw value or palette step.
- [ ] Every semantic token aliases a primitive; every component token aliases a semantic token, or the exception is documented.
- [ ] Modes are defined at the semantic tier.
- [ ] DTCG output uses `$value` and `$type` and valid alias syntax.
- [ ] Text and background pairs have computed contrast ratios.
- [ ] Any change to existing tokens comes with a migration and deprecation plan.

## Sources

- Design Tokens Community Group, Format, Color and Resolver modules 2025.10: https://www.designtokens.org/TR/2025.10/
- W3C WCAG 2.2 contrast criteria: https://www.w3.org/WAI/standards-guidelines/wcag/
- Material Design 3 color roles and tokens: https://m3.material.io/
- Apple Human Interface Guidelines, color and dark mode: https://developer.apple.com/design/human-interface-guidelines/
- Carbon and Atlassian token documentation (comparison only): https://carbondesignsystem.com/ and https://atlassian.design/
- Figma variables and modes: https://help.figma.com/
