---
name: design-implementation-qa
description: >-
  Compares a design source (Figma frame, screenshot or spec) with its implementation (running UI,
  screenshots, code) and produces a visual QA report of deviations in layout, spacing, typography,
  color and tokens, states, responsive behaviour, content and accessibility, each with evidence,
  severity and fix. Use when asked to check design fidelity, run visual QA, compare Figma with a
  build, detect design drift or prepare visual regression baselines. Do not use to review a design
  on its own merits (use ux-heuristic-evaluation).
license: MIT
compatibility: "Figma MCP server optional; without it the skill needs exported screenshots or a written spec."
metadata:
  version: "1.0.0"
  domain: quality
  status: beta
  trust: internal
  sources: "DOC-FIGMA-MCP,W3C-WCAG22,STORYBOOK,PLAYWRIGHT"
  platforms: "any"
  last-reviewed: "2026-11-17"
---

# Design and implementation QA

Parity is claimed only when both sides were actually inspected. Everything else is "not verified".

## When to use

- Before merging UI work or before release.
- When designers report "it does not look like Figma".
- When setting up visual regression baselines.

## Inputs

- Design source: Figma link (preferred, via `figma-design-context`), exported screenshots or a spec.
- Implementation: URL or build, screenshots at the same viewport, or code.
- Project tokens and tolerance rules (for example: spacing must match a token exactly; anti-aliasing differences ignored).

## Workflow

1. **Collect both sides at matching conditions:** same viewport or window size class, theme,
   language, content and state. Use `get_screenshot` for Figma and a browser or simulator
   screenshot for the build. If one side is missing, stop and report what is missing.
2. **Compare structure:** element presence and order, hierarchy, alignment, grid.
3. **Compare tokens, not pixels:** for each element, the Figma variable (via `get_variable_defs`)
   against the token used in code. A matching hex value with a different token is still a deviation.
4. **Compare typography:** style token, size, weight, line height, truncation and wrapping.
5. **Compare spacing and sizing:** paddings and gaps against spacing tokens; touch target sizes.
6. **Compare states:** hover, focus, pressed, disabled, loading, error, empty, selected.
7. **Compare responsive behaviour** at each breakpoint or window class defined in the design.
8. **Check accessibility side effects:** contrast of the implemented colors, focus visibility,
   labels; route deep findings to `accessibility-audit`.
9. **Classify** each deviation: severity (blocker: wrong information or broken interaction;
   major: visible inconsistency with the design system; minor: small visual offset; nit), side
   at fault (design, code, both, spec gap) and fix.

## Outputs

A QA report: conditions compared, side-by-side evidence references, deviations table (ID,
element, property, design value and token, implemented value and token, severity, side at fault,
fix), items not verified, and recommended visual regression baselines.

## Edge cases

- **Design uses raw values without variables:** report as a design-side token gap, not a code bug.
- **Dynamic content differs:** use the design content in the build or compare layout only.
- **Platform conventions override the design** (Dynamic Type, system fonts): mark as intended deviation.
- **Figma MCP unavailable:** use exported images and say that token-level comparison was not possible.

## Acceptance criteria

- [ ] Both sides were inspected under stated matching conditions, or the gap is reported.
- [ ] Deviations compare tokens, not only rendered values.
- [ ] Every deviation has evidence, severity and the side at fault.
- [ ] Unverified items are listed.

## Sources

- Figma MCP server tools (get_screenshot, get_variable_defs): https://developers.figma.com/docs/figma-mcp-server/
- W3C WCAG 2.2: https://www.w3.org/WAI/standards-guidelines/wcag/
- Storybook visual testing: https://storybook.js.org/
- Playwright screenshots and visual comparisons: https://playwright.dev/
