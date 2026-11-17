---
name: figma-token-mapping
description: >-
  Maps Figma variables and styles used in a frame to the project's design tokens: exact matches,
  alias matches, nearest candidates flagged for approval, hardcoded values, mode coverage, and a
  proposed DTCG or code patch that never creates tokens without approval. Use when asked to map
  Figma variables to tokens, find which tokens a design uses, detect hardcoded values, sync Figma
  variables with code tokens or prepare Code Connect token usage. Do not use to design a new token
  architecture (use design-token-architecture).
license: MIT
compatibility: "Needs Figma MCP get_variable_defs for live data; otherwise works from an exported variables JSON."
metadata:
  version: "1.0.0"
  domain: ai-workflows
  status: beta
  trust: official-derived
  sources: "DOC-FIGMA-MCP,DTCG-2025-10,FIGMA-HELP,W3C-WCAG22"
  platforms: "any"
  last-reviewed: "2026-11-17"
---

# Figma token mapping

A mapping is a table of evidence: Figma variable, resolved value, project token, match type. A
value without a token is a decision for the design system owner, not for the agent.

## When to use

- Before implementing a frame, to know which tokens to use.
- Auditing a design for unbound values.
- Keeping Figma variables and code tokens in sync.

## Inputs

- Figma node (via `figma-design-context`) or an exported variables file.
- Project token sources: token JSON, CSS custom properties, theme files, Tailwind config.
- Project mapping rules (for example a Figma name to CSS token table in `CLAUDE.md`), which take precedence.

## Workflow

1. **Collect Figma data:** `get_variable_defs` for variables and styles with resolved values;
   design context for raw (unbound) values.
2. **Index project tokens:** name, tier, resolved value per mode, file location.
3. **Match in order:**
   - **Mapped:** a rule in the project mapping table.
   - **Exact name:** same token path after normalisation (`Grey/900` to `grey.900`).
   - **Value match:** same resolved value; prefer the semantic token whose intent fits the usage
     (text, border, surface), and flag ambiguous candidates.
   - **Nearest:** closest value within a stated tolerance (color distance, spacing step) marked
     `needs approval`.
   - **None:** no token; candidate for a new token, requires approval.
4. **Check usage intent:** a primitive used directly in a component is a finding; propose the semantic token.
5. **Check modes:** for each mapped token, confirm values exist for every mode used by the
   product (light, dark, high contrast).
6. **Check accessibility of pairs** found in the frame (text on surface) with computed contrast.
7. **Produce the patch proposal:** code changes replacing values with tokens; DTCG additions only
   as a proposal block marked "pending approval".

## Outputs

Mapping table (Figma variable or raw value, resolved value, layer or node, project token, match
type, confidence, notes), hardcoded values list, mode coverage table, contrast notes, patch
proposal, decisions needed.

## Edge cases

- **Two tokens with the same value** (`color.text.subtle` and `color.icon.subtle`): choose by
  usage; never pick alphabetically.
- **Figma variable renamed in code:** keep a persistent mapping file; do not rename either side silently.
- **Values with opacity or blend modes:** report the composited value and the original token plus opacity.
- **Library variables not published:** list them as unresolved.

## Acceptance criteria

- [ ] Every value in the frame appears in the mapping table or the hardcoded list.
- [ ] Each mapping states its match type and confidence.
- [ ] No new token is created; additions are proposals pending approval.
- [ ] Mode coverage is checked.
- [ ] Project mapping rules were applied first.

## Sources

- Figma MCP server, get_variable_defs: https://developers.figma.com/docs/figma-mcp-server/
- Design Tokens Format Module 2025.10: https://www.designtokens.org/TR/2025.10/
- Figma variables and modes: https://help.figma.com/
- W3C WCAG 2.2 contrast: https://www.w3.org/WAI/standards-guidelines/wcag/
