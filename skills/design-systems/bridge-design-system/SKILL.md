---
name: bridge-design-system
description: >-
  Project-specific rules for the Bridge design system: four-tier token hierarchy
  (core, semantic, component, breakpoint), naming, Figma-to-token mappings and component
  conventions. Use when working inside a project that consumes Bridge: the user mentions
  Bridge, Bridge tokens or Bridge components, or when the repository contains Bridge
  token files. Do not use for other design systems.
metadata:
  domain: design-systems
  version: "2.0.0"
  status: beta
  scope: project
  trust: project-specific
  last-reviewed: "2026-11-17"
---

# Bridge design system (project-specific)

This skill carries project rules. It sits at level 4 of the precedence order (established project design system): it overrides generic reusable skills, but not safety, legal requirements, validated project constraints, or official platform guidance.

## When to use

* Implementing, reviewing or documenting UI in a Bridge-based codebase.
* Mapping Figma variables from Bridge files to code tokens.
* Not for: generic token architecture questions (use `design-token-architecture`).

## Inputs

* The Bridge token source in the repository (the token files are the source of truth, not this skill).
* Figma Bridge library link when mapping variables.

## Procedure

1. Locate the Bridge token files in the project. If none exist, stop and ask; do not reconstruct tokens from this skill or from the archived guide.
2. Respect the tier order: components consume component or semantic tokens; core tokens are never used directly in components; breakpoint tokens alias core or semantic tokens.
3. Name by meaning: `color.action.primary`, not a hex value or a palette step.
4. Map Figma variables through the project's mapping table (see [references/legacy-guide.md](references/legacy-guide.md) for the March 2026 examples, to be confirmed against the current token files).
5. Components follow the project's atomic structure and BEM class naming where the codebase already uses them.
6. Accessibility rules override visual specs: known example, `Grey/400` (#9CA3AF) on white is 2.54:1 (computed) and must never carry text.
7. Any new token goes through the Bridge contribution process (`design-system-governance`), never added silently.

## Output

Code or documentation that uses only existing Bridge tokens, plus a list of token gaps and proposed additions with their tier.

## Edge cases

* Figma value without a Bridge token: report as a gap.
* Old flat tokens (for example `primary-blue`): propose a migration to the tier hierarchy with an alias period; never rename in place.
* Bridge 2.0 migration in progress: confirm which version the project consumes before mapping.

## Acceptance criteria

* No hard-coded color, spacing or typography values.
* No core token referenced from a component.
* Every gap listed with a proposed tier and semantic name.

## Sources

* Repository rules: `rules/bridge-design-system-rules.md` at the root of this repository (project content, verify confidentiality before publishing)
* Token format reference: https://www.designtokens.org/tr/2025.10/
* Archived March 2026 guide: [references/legacy-guide.md](references/legacy-guide.md)
