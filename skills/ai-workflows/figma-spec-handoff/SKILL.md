---
name: figma-spec-handoff
description: >-
  Produces an implementation-ready handoff specification (anatomy, variants, states,
  tokens, behavior, accessibility, content rules, open questions) from a Figma frame
  or component, without writing code. Use when a designer or developer asks to
  document, annotate or hand off a Figma design, write a component or screen spec,
  or prepare a Notion-ready handoff page.
compatibility: Uses the Figma MCP server when available; otherwise works from screenshots and designer notes.
metadata:
  domain: ai-workflows
  version: "2.0.0"
  status: beta
  scope: universal
  trust: authored
  last-reviewed: "2026-11-17"
---

# Figma spec handoff

## When to use

* "Document this component", "write the handoff for this screen", "annotate this flow".
* Before implementation, to make design intent explicit and testable.
* Not for: writing code (use `figma-design-to-code`), auditing an existing build (use `figma-design-code-drift`), DS component lifecycle (the `component` skill covers spec, review and audit for design system components).

## Inputs

* Figma URL with `node-id` or a desktop selection; or screenshots plus designer notes.
* Output language and format (default: Markdown, the user's language, Notion-compatible).
* Optional: the project's token source and component library to name real tokens.

## Procedure

1. Discover available Figma MCP tools (see `figma-design-to-code` step 1). Note missing ones.
2. Structure: `get_metadata` for large frames, then `get_design_context` per section, `get_screenshot` per section, `get_variable_defs` once.
3. Build the anatomy: list layers that matter to implementation (container, slots, text, icons), including nested base layers.
4. Inventory variants and states shown. Then list states that are **not shown but required** (focus-visible, disabled, loading, error, empty, read-only, overflow, long text, RTL, text scaling). Mark each as *Shown* or *Missing in design*.
5. Tokens: table of Figma variable, resolved value, role. Hard-coded values go in a separate "unbound values" table.
6. Behavior: interactions, transitions, validation rules, responsive rules. Anything inferred is labeled *Assumption*.
7. Accessibility: role, accessible name, keyboard model, focus order, contrast results for each text and non-text pair (WCAG 2.2 AA), target size. Use `accessibility-audit` for the method.
8. Content: character limits, truncation, localization concerns, tone (see `ux-writing`).
9. Open questions: every ambiguity, owner, and what is blocked until answered.

## Output

A single Markdown document with sections: Overview, Anatomy, Variants and states (with Shown / Missing column), Tokens, Unbound values, Behavior, Responsive rules, Accessibility, Content, Assumptions, Open questions, Figma references (node IDs).

## Edge cases

* Frame mixes documentation artboards and the real component: spec only the component; cite the documentation as context.
* Figma naming that misleads code (for example a state named "Pressed" that is actually keyboard focus): document the intended behavior and flag the naming.
* No variables bound: still produce the spec; mark every value as unbound.
* Very large frames: process by section and state which sections were covered.

## Acceptance criteria

* Every statement is either observed in the file or labeled *Assumption*.
* Missing required states are listed explicitly.
* Every color pair has a computed contrast ratio and pass or fail at AA.
* Open questions have an owner or are marked unassigned.
* A developer can implement without opening Figma for anything except visual comparison.

## Sources

* Figma MCP server tools: https://developers.figma.com/docs/figma-mcp-server/tools-and-prompts
* WCAG 2.2: https://www.w3.org/TR/WCAG22/
* Archived prompt and field notes: [references/legacy-guide.md](references/legacy-guide.md)
