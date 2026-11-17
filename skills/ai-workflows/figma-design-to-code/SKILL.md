---
name: figma-design-to-code
description: >-
  Turns a Figma frame or component into production code that follows the target
  project's stack, components and design tokens, using whichever Figma MCP tools are
  actually available and a documented fallback when they are not. Use when the user
  shares a Figma link or selection and asks to implement, build, port or update UI
  from it (web, SwiftUI or Jetpack Compose), or to map Figma variables to code tokens.
compatibility: Works best with the Figma MCP server (remote https://mcp.figma.com/mcp or desktop http://127.0.0.1:3845/mcp). Degrades to screenshot and manual-spec input without it.
metadata:
  domain: ai-workflows
  version: "2.0.0"
  status: beta
  scope: universal
  trust: authored
  last-reviewed: "2026-11-17"
---

# Figma design to code

Figma MCP output is a *representation* of the design (React + Tailwind by default), never the final code. The job is to translate it into the project's conventions, reuse what exists, and prove the result matches.

## When to use

* "Implement this Figma frame", "build this screen from Figma", "update the component to match the design".
* Mapping Figma variables or styles to the project's tokens before writing UI.
* Not for: writing a handoff document only (use `figma-spec-handoff`), comparing an existing build with Figma (use `figma-design-code-drift`), editing the Figma canvas.

## Inputs

* Required: a Figma URL with `node-id`, or a live selection (desktop server only).
* Required: the target repository, so its stack, components and tokens can be read.
* Optional: platform target (web, iOS, Android), Code Connect mappings, acceptance criteria.

## Procedure

1. **Discover tools, do not assume them.** List the Figma MCP tools the client exposes. Record which of these exist: `get_metadata`, `get_design_context`, `get_screenshot`, `get_variable_defs`, `get_code_connect_map`, `search_design_system`. Server type matters: selection-based prompting works only on the desktop server; the remote server needs a link. If none exist, go to the fallback (step 9).
2. **Read the project first.** Identify framework, styling approach, token source (CSS variables, Style Dictionary output, theme objects), component library and file conventions. Search for an existing component before creating one.
3. **Size the frame.** Call `get_metadata` first on large or unknown frames (rule of thumb: taller than about 800 px or many children). Split into sections by node ID.
4. **Get context per section.** Call `get_design_context` on each section rather than on the whole frame. Expect a "large response" notice on big frames; it is not an error.
5. **Get the visual reference.** Call `get_screenshot` for every node implemented. Never implement from structure alone.
6. **Get tokens and mappings.** Call `get_variable_defs` to obtain variable names and resolved values; call `get_code_connect_map` when available. A "missing Code Connect mappings" notice only means no mapping exists.
7. **Translate.**
   * Replace every literal (hex, px, font) with the project token that has the same *meaning*, not just the same value. If none exists, list it under "Token gaps" instead of inventing a name.
   * Reuse mapped or existing components; extend through their public API.
   * Use assets returned by the server (localhost or hosted URLs) as given; do not add icon libraries or placeholders when an asset was returned.
   * Check nested layers: the visible radius, padding or border may belong to an inner layer.
   * Add the states the design implies but may not show: hover, focus-visible, pressed, disabled, loading, error, empty, long content, RTL, text scaling.
   * Platform targets: for SwiftUI follow `swiftui-implementation`; for Compose follow `material3-compose`.
8. **Validate.** Render the result and compare with the screenshot at the same viewport. Check spacing, type, color, radius, elevation, states and responsive behavior. Run the project's lint, type check and tests.
9. **Fallback without MCP.** Ask for a screenshot plus the variable list or a spec. State in the output which values could not be verified. Never fabricate values from a file you cannot read.

## Output

1. Code changes in the project's structure.
2. A short implementation note containing: nodes implemented, tools used (and missing), token mapping table (Figma variable, project token, value), token gaps, components reused or created, deviations from the design with reasons, open questions.

## Edge cases

* Figma value matches no token: report it, propose the nearest semantic token, let the user decide.
* Variables unbound in Figma (hard-coded values): flag them as design debt in the note.
* Mixed responsibility frames (marketing page plus app chrome): implement only the requested scope.
* Rate limits or partial responses: reduce node scope, never fill gaps by guessing.
* Design contradicts platform guidance or accessibility (for example a 32 px touch target on mobile): implement the compliant version and report the conflict, following the precedence in `skill-router`.

## Acceptance criteria

* No literal color, spacing or typography value remains where a token exists.
* Every implemented node was compared with its screenshot; differences are listed.
* Tools actually used are listed; nothing is claimed from tools that were unavailable.
* Interactive states and keyboard focus are implemented and visible.
* Project checks (lint, types, tests) pass or failures are reported.

## Sources

* Figma MCP server tools: https://developers.figma.com/docs/figma-mcp-server/tools-and-prompts
* Figma official agent skills and setup: https://github.com/figma/mcp-server-guide
* Field notes from the March 2026 Input component test (archived): [references/legacy-guide.md](references/legacy-guide.md)
