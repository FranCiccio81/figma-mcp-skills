---
name: heuristic-evaluation
description: >-
  Runs an expert heuristic evaluation (UX audit) of a screen, flow or product using
  Nielsen's ten usability heuristics plus platform conventions, and reports each issue
  with evidence, severity, confidence, impact and effort. Use when the user asks for a
  UX audit, expert review, usability review of screens, or a prioritized list of UX
  problems without running a user test.
metadata:
  domain: ux
  version: "1.0.0"
  status: beta
  scope: universal
  trust: authored
  last-reviewed: "2026-11-17"
---

# Heuristic evaluation

## When to use

* Fast expert review before or between user tests.
* Auditing an existing product to build a UX backlog.
* Not a substitute for usability testing: findings are expert predictions.

## Inputs

* Screens, flows, prototype or live product, and the primary user tasks.
* Platform (to apply its conventions) and target users.

## Procedure

1. **Define scope and tasks.** Evaluate along the tasks users actually perform, not screen by screen in isolation.
2. **Two passes.** First pass for flow and overall understanding; second pass element by element.
3. **Apply the heuristics:** visibility of system status; match with the real world; user control and freedom; consistency and standards (including platform conventions: Apple HIG, Material, web); error prevention; recognition rather than recall; flexibility and efficiency; aesthetic and minimalist design; help users recognize, diagnose and recover from errors; help and documentation.
4. **Record each issue:** location, heuristic, description, evidence (screenshot reference, step), affected task.
5. **Rate:**
   * Severity 0 to 4 (not a problem, cosmetic, minor, major, catastrophe) based on frequency, impact and persistence.
   * Confidence: High (clear violation, reproducible), Medium, Low (depends on users we have not observed).
   * Impact on business or user outcome, and Effort (S, M, L) to fix.
6. **Consolidate** when several evaluators participate: merge duplicates, average or discuss severities.
7. **Recommend** fixes; mark the ones that need validation by testing.

## Output

Summary, findings table (ID, location, heuristic, issue, evidence, severity, confidence, impact, effort, recommendation), quick wins (high severity, low effort), items to validate with users, strengths worth keeping.

## Edge cases

* Domain-specific flows (trading, pension, medical): mark findings that depend on domain knowledge as Low confidence unless a domain expert reviewed them.
* Accessibility issues found along the way: log them and route to `accessibility-audit` for proper criteria.
* Single evaluator: say so; single evaluators miss a significant share of issues.

## Acceptance criteria

* Every finding has evidence, heuristic, severity, confidence, impact and effort.
* No finding is presented as a validated user need.
* Strengths are reported, not only problems.

## Sources

* Nielsen Norman Group, ten usability heuristics and severity ratings: https://www.nngroup.com/
* Apple Human Interface Guidelines: https://developer.apple.com/design/human-interface-guidelines/
* Material Design 3: https://m3.material.io/
