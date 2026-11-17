---
name: design-critique
description: >-
  Gives structured, principle-based design critique on screens, flows or visual
  directions: restates the goal, evaluates hierarchy, layout, typography, color,
  consistency, usability and accessibility, and separates blocking issues from
  suggestions. Use when the user shares a design and asks for feedback, a critique, a
  review before a stakeholder presentation, or a comparison between design options.
metadata:
  domain: ux
  version: "1.0.0"
  status: beta
  scope: universal
  trust: authored
  last-reviewed: "2026-11-17"
---

# Design critique

## When to use

* "What do you think of this screen?", "critique these two options", "review before I present".
* For a systematic UX audit use `heuristic-evaluation`; for conformance use `accessibility-audit`.

## Inputs

* The design (image, Figma link, prototype), its goal, audience, stage (exploration or final), and the kind of feedback wanted.

## Procedure

1. **Restate the goal** and the user's primary task. If unknown, ask; critique without a goal is taste.
2. **First impression:** what draws attention first, second, third? Does that match the task's priority?
3. **Evaluate in order:** task clarity and flow; visual hierarchy; layout and alignment, spacing rhythm; typography (scale, readability, line length); color (meaning, contrast, consistency); components (consistent with the design system and platform); content (clarity, `ux-writing`); accessibility red flags (contrast, target sizes, color-only meaning).
4. **Ground every point** in a principle or guideline (heuristic, platform guideline, WCAG criterion, design system rule) and a concrete location.
5. **Classify:** Blocking (prevents the goal or fails accessibility), Important, Suggestion. Separate *observation* from *recommendation*.
6. **Comparisons:** compare options against the same criteria in a table; recommend with conditions ("Option B, if the primary task is X").
7. **End with what works**, so it is kept in the next iteration.

## Output

Critique with: goal restated, strengths, issues table (location, observation, principle, severity, recommendation), questions for the designer, and for comparisons a criteria table with a conditional recommendation.

## Edge cases

* Early exploration: focus on concept and flow, not pixel details.
* Brand or design-system constraints the reviewer cannot see: ask before recommending changes that contradict them.
* Personal preference: label it as such, or leave it out.

## Acceptance criteria

* Every issue cites a principle and a location.
* Severity distinguishes blocking issues from suggestions.
* Strengths are named.

## Sources

* Nielsen Norman Group, design critiques and heuristics: https://www.nngroup.com/
* Apple Human Interface Guidelines: https://developer.apple.com/design/human-interface-guidelines/
* Material Design 3: https://m3.material.io/
