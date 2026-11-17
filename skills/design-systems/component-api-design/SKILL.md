---
name: component-api-design
description: >-
  Designs the public API of a design system component across Figma and code: anatomy,
  props and variants, states, slots and composition, naming, defaults, accessibility
  contract, responsive behavior and platform mapping (React, SwiftUI, Compose). Use
  when the user creates a new component, adds variants or props, reviews a component's
  API, aligns Figma component properties with code props, or prepares Code Connect.
metadata:
  domain: design-systems
  version: "1.0.0"
  status: beta
  scope: universal
  trust: authored
  last-reviewed: "2026-11-17"
---

# Component API design

## When to use

* New component or significant change to an existing one.
* Figma properties and code props disagree.
* For the full spec, review and implementation lifecycle of a DS component, the repository's `component` skill orchestrates; this skill covers the API decisions.

## Inputs

* Use cases (real screens where the component is needed), existing components that overlap, design system principles and tokens, platforms.

## Procedure

1. **Justify the component.** Gather at least a few real use cases; check whether an existing component or composition covers them. Avoid near-duplicates.
2. **Anatomy.** Named parts (container, label, icon, supporting text), which are required, which are slots.
3. **Props and variants.**
   * Variants for mutually exclusive visual choices (`variant: primary | secondary | tertiary`), booleans only for true on/off features (`disabled`, `loading`), never boolean combinations that create impossible states.
   * Name props by intent, consistently across components (`size` everywhere, not `size` here and `scale` there).
   * Sensible defaults; required props only where meaning would otherwise be missing (accessible name).
   * Prefer composition (slots, children) over long lists of configuration props.
4. **States.** Default, hover, focus-visible, pressed, disabled, loading, error, selected, read-only, as relevant. Define which combinations are valid.
5. **Accessibility contract.** Role, accessible name source, keyboard interaction (from WAI-ARIA Authoring Practices for web patterns), focus management, target size, announcements. Platform equivalents for VoiceOver and TalkBack.
6. **Content rules.** Min and max text, truncation or wrapping, icon-only usage (requires an accessible label), localization and RTL.
7. **Responsive and adaptive behavior,** density, text scaling.
8. **Tokens.** Which semantic or component tokens each part uses (`design-token-architecture`).
9. **Platform mapping.** Figma component properties ↔ React props ↔ SwiftUI initializer and modifiers ↔ Compose parameters. Native platform components first where the system provides them; do not rebuild a native control without reason.
10. **Code Connect** mapping once names align.

## Output

Component API spec: purpose and use cases, anatomy, props table (name, type, default, description), variant and state matrix with invalid combinations, accessibility contract, content rules, tokens, platform mapping table, open questions.

## Edge cases

* Request for a one-off component: propose a local pattern instead of adding to the system.
* Figma limitations (for example nested instance swaps) force a different structure in design than in code: document the mapping instead of distorting the code API.
* Breaking API change: follow `design-system-governance` (deprecation, migration guide, major version).

## Acceptance criteria

* No impossible state is expressible through the props.
* Accessible name is guaranteed by the API (required prop or enforced fallback).
* Props are named consistently with existing components.
* Figma and code mapping table is complete.

## Sources

* WAI-ARIA Authoring Practices: https://www.w3.org/WAI/ARIA/apg/
* Carbon Design System (comparative reference): https://carbondesignsystem.com/
* Atlassian Design System (comparative reference): https://atlassian.design/
* Figma Code Connect guidance: https://github.com/figma/mcp-server-guide
