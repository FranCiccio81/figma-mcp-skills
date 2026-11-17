---
name: bridge-designer-workflow
description: >-
  Guides product designers working with Bridge 2.0 in Figma: library setup, frames and
  variable modes (themes, typography size), instances and property conventions,
  binding every fill, stroke, radius and spacing to variables, states, copy, accessibility
  annotations, self-check and handoff to developers. Use when a Swissquote or
  PostFinance designer creates or updates mockups, prepares a handoff, asks how to use
  a Bridge library or variable, or wants a pre-handoff check of a Figma file.
compatibility: Figma with access to the Bridge 2.0 libraries. The Figma MCP helps with self-checks but is not required.
metadata:
  domain: bridge
  version: "1.0.0"
  status: beta
  scope: project
  trust: project-specific
  last-reviewed: "2026-11-17"
---

# Bridge for designers (Figma workflow)

Platform rules (structure, components, sizes per platform) live in `bridge-ios`, `bridge-android`, `bridge-tablet`, `bridge-foldables` and `bridge-web`. Tokens and formats live in `references/bridge-foundations.md`. This skill covers how to work in Figma so that the file is correct, reviewable and implementable.

## When to use

* Starting, updating or reviewing a Bridge mockup in Figma.
* Preparing a handoff for developers.
* Questions such as "which variable do I use", "why does my instance look wrong in dark", "how do I mark a missing component".

## Inputs

* The brief or PRD (`bridge-product-manager`), the platforms, the product (Swissquote, PostFinance), the Figma file.

## Procedure

1. **Libraries.** Enable only the Bridge 2.0 libraries: Foundations (variables, text, effect and grid styles), Components Library (web), Mobile library 2.0 (iOS and Android). The old "SQ Component" kit and libraries marked "Don't use - Old DS" are not sources.
2. **Frames.**
   * iPhone 402 pt wide; Android phone per `bridge-android`; web 1440 (Large), 768 (Medium), 390 (Small), plus 320 for reflow checks on critical flows; tablets and foldables per their skills.
   * Apply the Bridge layout grid styles. Auto layout everywhere. Nudge 1, big nudge 8, snap to the 4 px grid.
   * Set the variable modes on the frame: theme (SQ Light, SQ Dark, PF Light, PF Dark, Default) and typography (Medium, or Small on compact web viewports).
3. **Components.**
   * Instances only, never detached. If an instance cannot do what you need, it is a gap or a misuse: ask, do not detach.
   * Property conventions: variant values lowercase, booleans start with `show`, text properties with `edit`, instance swaps with `pick`. Fill containers through slots.
   * Mobile origin: `[Native]` instances get `platform=ios` or the Android value; `[Mobile]` are custom Bridge; native-as-is elements come from the platform kits.
   * Read the component description (Purpose, Use when, Do not use, Accessibility, Tokens) before using a component in a new way.
4. **Variables, never values.** Bind every fill, stroke, radius, padding and gap to Foundations variables; text uses Foundations text styles. Pick the size scale by intent: `spacing` between siblings, `padding` inside a container, `margin` around a block. No opacity to fake a tint: use the solid tint token.
5. **Colour roles.** Product actions `action/product/*`; brand orange only in brand moments; Buy blue and Sell red only for orders; up and down with a sign or arrow in addition to colour. One primary action per view.
6. **States.** For every interactive element and data screen: default, hover (web only), pressed, focus, disabled, loading or submitting, error, empty, offline. Mobile has no hover.
7. **Themes.** Check every screen in light and dark (dark is its own set of values), and in PF modes when it ships in PostFinance.
8. **Copy and data.** English first, sentence case, second person; amounts `CHF 1,234.50`; formats per `bridge-content-and-formats`. Leave room for 30 to 40 percent text expansion.
9. **Accessibility annotations.** Reading or focus order, headings, accessible names for icon-only controls, VoiceOver or TalkBack grouping of rows, touch targets, behaviour at large text sizes (`bridge-accessibility`).
10. **Gaps.** Missing component or token: compose from documented parts, name the frame `[gap]`, report it with the template in `bridge-design-system`.
11. **Self-check and handoff.** Run `bridge-compliance-review` on the frame (with the Figma MCP when available). Group finished work in a Section marked Ready for dev; developers set Completed; later edits show as Changed. Write the handoff with the platform skill's spec format, listing states, tokens, accessibility notes and open questions.

## Output

A Figma file that passes the compliance review, plus a handoff note: screens and states, components with origin and key properties, tokens used, accessibility annotations, gaps and open questions.

## Edge cases

* Variable missing for a value you need: do not hard-code; use the closest semantic family and record the gap.
* Exploration or concept work: variables and instances still apply; mark the page as exploration so nobody implements it.
* A component works in light but fails contrast in dark: report it; do not override the token locally.

## Acceptance criteria

* No detached instance, no unbound fill, stroke, radius or spacing, no raw text style.
* Light and dark (and PF where relevant) checked.
* Every interactive element has its states; every data screen has loading, empty, error.
* Gaps are named `[gap]` and reported.
* Handoff note complete and the Section marked Ready for dev.

## Sources

* Figma MCP server tools (self-checks, variables): https://developers.figma.com/docs/figma-mcp-server/tools-and-prompts
* Apple Human Interface Guidelines: https://developer.apple.com/design/human-interface-guidelines/
* Material Design 3: https://m3.material.io/
* WCAG 2.2: https://www.w3.org/TR/WCAG22/
