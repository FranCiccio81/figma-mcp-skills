---
name: figma-design-code-drift
description: >-
  Compares an implemented screen or component with its Figma source and produces a
  visual QA report of deviations (layout, spacing, typography, color, tokens, states,
  content, responsive behavior), each with evidence, severity and suggested fix. Use
  when the user asks whether the build matches the design, wants a design QA pass
  before release, or suspects design and code have drifted apart.
compatibility: Needs a way to render the implementation (browser, simulator or emulator screenshots). Figma MCP recommended; otherwise exported Figma frames.
metadata:
  domain: ai-workflows
  version: "1.0.0"
  status: beta
  scope: universal
  trust: authored
  last-reviewed: "2026-11-17"
---

# Figma design and code drift

## When to use

* "Does this match the Figma?", "design QA before release", "find what drifted".
* After a design system update, to find consumers still on old values.
* Not for: building the UI (use `figma-design-to-code`), automated screenshot regression between two code versions (use `visual-regression-qa`).

## Inputs

* Figma URL with `node-id` (or exported frames), and the implementation location (URL, route, story, simulator screen).
* Viewports and themes to compare (default: the frames that exist in Figma).
* The project's token source.

## Procedure

1. Discover available Figma MCP tools. Pull `get_screenshot` and `get_design_context` for each frame, `get_variable_defs` for tokens. Without MCP, ask for exported frames and the variable list; mark token checks as Not verified.
2. Render the implementation at the same viewport, theme, locale and data. Mismatched data is the first source of false positives: align content before comparing.
3. Compare in this order, one category at a time:
   1. Structure: missing or extra elements, order.
   2. Layout: alignment, spacing, sizes (measure with devtools or layout inspectors, not by eye).
   3. Typography: family, size, weight, line height, letter spacing, truncation.
   4. Color and tokens: is the *token* the same, not just the color value? A correct value bound to the wrong token is drift.
   5. Shape and elevation: radius (check nested layers), borders, shadows.
   6. States: hover, focus-visible, pressed, disabled, loading, error, empty.
   7. Responsive and text scaling behavior.
   8. Content: copy differences.
4. Decide direction for each deviation: *Code drift* (implementation wrong), *Design drift* (Figma outdated or detached from the library), *Intentional* (documented decision), or *Unknown*.
5. Rate severity: Blocker (broken task or accessibility failure), Major (visible brand or hierarchy issue), Minor (sub-pixel or cosmetic).

## Output

Report with: scope (frames, viewports, tools available), summary counts by severity and direction, deviations table (ID, element, category, expected with Figma reference, actual with evidence, direction, severity, suggested fix), not-verified list.

## Edge cases

* Detached Figma instances or local overrides: report as design drift, not a code bug.
* Font rendering differences between Figma and browsers or OS: ignore sub-pixel antialiasing; report metric differences only.
* Dynamic data: compare structure and tokens; exclude live values.
* The design itself fails accessibility: report it as a design issue and point to `accessibility-audit`.

## Acceptance criteria

* Every deviation has evidence from both sides (Figma reference and implementation measurement or screenshot).
* Token mismatches are reported by token name, not by hex value only.
* Direction and severity are set for every deviation.
* Anything not verifiable is listed rather than assumed equal.

## Sources

* Figma MCP server tools: https://developers.figma.com/docs/figma-mcp-server/tools-and-prompts
* Design Tokens Format Module 2025.10: https://www.designtokens.org/tr/2025.10/
