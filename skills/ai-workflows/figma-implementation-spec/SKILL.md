---
name: figma-implementation-spec
description: >-
  Turns a Figma frame or component into a developer handoff specification: anatomy, variants and
  states, tokens per element, spacing and sizing, typography, behaviour and interactions,
  responsive rules, content constraints, accessibility annotations, assets, acceptance criteria and
  open questions, in Notion-ready Markdown. Use when asked for a handoff, dev spec, redlines, specs
  from Figma, component documentation from a design, or annotations for developers. Do not use to
  write code (use react-component-engineering, swiftui-implementation or compose-implementation).
license: MIT
compatibility: "Figma MCP server recommended; falls back to screenshots and a written brief."
metadata:
  version: "1.0.0"
  domain: ai-workflows
  status: stable
  trust: internal
  sources: "DOC-FIGMA-MCP,W3C-WCAG22,W3C-APG,DTCG-2025-10"
  platforms: "any"
  last-reviewed: "2026-11-17"
---

# Figma implementation specification

A handoff spec answers every question a developer would otherwise ask in a meeting, and flags the
ones only the designer can answer.

## When to use

- Handoff of a component or screen to development.
- Documenting an existing design system component from Figma.
- Preparing a spec for review before implementation.

## Inputs

- Figma node(s), read through `figma-design-context` (metadata, design context per section,
  screenshot, variables, Code Connect).
- Token mapping from `figma-token-mapping` when tokens matter.
- Output language (default: the user's language) and target tool (Notion, Confluence, Markdown file).

## Workflow

1. **Gather context** with `figma-design-context`; stop and report if Figma cannot be read.
2. **Overview:** purpose, when to use, when not to use, related components.
3. **Anatomy:** numbered parts with their layer names and whether optional.
4. **Variants and sizes:** matrix from the Figma component properties.
5. **States:** inventory per `interaction-design-spec` (default, hover, focus, pressed,
   disabled, read-only, error, loading...), noting states missing from the file. Check what a
   variant called "Pressed" actually shows (press or focus ring).
6. **Tokens per element:** color, typography, spacing, radius, shadow, motion, from the token
   mapping; list hardcoded values separately.
7. **Layout and responsive rules:** auto layout, constraints, min and max sizes, behaviour at each breakpoint or window class.
8. **Content rules:** character limits, truncation, wrapping, localization expansion, empty values.
9. **Accessibility annotations:** semantic element or native control, accessible name source,
   keyboard behaviour (APG pattern), focus order, announcements, contrast results, target size
   (WCAG 2.5.8 and the project rule).
10. **Assets:** icons and images with export format and source.
11. **Acceptance criteria and open questions** with owners.

## Outputs

A Markdown document following [references/handoff-template.md](references/handoff-template.md),
with provenance (file key, node IDs, date) at the top. Default language is the user's language.

## Edge cases

- **Frame mixes documentation and component:** spec the component, not the documentation layout.
- **Missing states or variants:** list them as open questions, do not invent visuals.
- **Hardcoded values in the design:** report them as design debt with the nearest token.
- **Platform differences:** add per-platform rows (web, iOS, Android) instead of one compromise.

## Acceptance criteria

- [ ] Provenance is recorded.
- [ ] Every visual property references a token or is listed as hardcoded.
- [ ] All states are listed with missing ones flagged.
- [ ] Accessibility annotations include keyboard, name, role and contrast.
- [ ] Open questions have owners.

## Sources

- Figma MCP server documentation: https://developers.figma.com/docs/figma-mcp-server/
- W3C WCAG 2.2: https://www.w3.org/WAI/standards-guidelines/wcag/
- WAI-ARIA Authoring Practices Guide: https://www.w3.org/WAI/ARIA/apg/
- Design Tokens Format Module 2025.10: https://www.designtokens.org/TR/2025.10/
