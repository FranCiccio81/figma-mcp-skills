---
name: ux-heuristic-evaluation
description: >-
  Evaluates an interface (screens, prototype, Figma frame, live product) against usability
  heuristics and produces a design critique where every finding carries severity, confidence,
  evidence, effort and impact. Use when asked for a UX audit, heuristic evaluation, expert review,
  design critique or "what is wrong with this screen". Do not use for WCAG conformance (use
  accessibility-audit) or for platform convention checks (use apple-hig-review or
  material3-design-review), although findings can reference them.
license: MIT
metadata:
  version: "1.0.0"
  domain: ux
  status: beta
  trust: internal
  sources: "NNG,W3C-WCAG22"
  platforms: "any"
  last-reviewed: "2026-11-17"
---

# UX heuristic evaluation and design critique

An expert review finds likely problems quickly. It does not prove that users have them: findings
are `[Observed]` in the interface and `[Assumption]` about user impact until tested.

## When to use

- Reviewing a design before usability testing, to fix obvious issues first.
- Auditing an existing product area to build a backlog.
- Giving structured critique on a design in progress.

## Inputs

- The artifact: screenshots, Figma link (use `figma-design-context`), prototype or URL.
- Context: target users, primary tasks, platform, constraints, stage (concept or production).
- Optional: analytics or research that already points to problems.

## Workflow

1. **Frame the review:** list the two to five primary tasks and the users. Without tasks, ask for
   them or state the tasks assumed.
2. **Walk each task** step by step on the actual artifact, noting what the user must see, decide
   and do at each step.
3. **Check the heuristics** in [references/heuristics.md](references/heuristics.md) at each step.
   Also note platform convention breaks and obvious accessibility barriers, then route them to the
   specialised skills.
4. **Record each finding** with: location, heuristic, description, evidence (screenshot region,
   node ID, URL), severity 0 to 4, confidence (high, medium, low), user impact, effort (S, M, L),
   recommendation.
5. **Rate severity** on frequency, impact and persistence using the scale in the reference.
   Confidence is low when the finding depends on unknown context or content.
6. **Deduplicate and cluster** findings that share a root cause.
7. **Prioritise** by severity × impact / effort, and list quick wins separately.
8. **Note strengths** worth keeping, so fixes do not regress them.

## Outputs

A report with: scope and tasks, method and limits (number of evaluators, artifact fidelity),
summary of top five issues, findings table, quick wins, strengths, recommended validation
(which findings to test with users).

| ID | Location | Heuristic | Finding | Evidence | Severity | Confidence | Impact | Effort | Recommendation |
|---|---|---|---|---|---|---|---|---|---|

## Edge cases

- **Single evaluator:** state it; one evaluator typically finds a minority of issues, so recommend
  a second reviewer for high-stakes flows.
- **Low-fidelity wireframes:** skip visual findings, focus on flow and content.
- **Missing states** (errors, empty, loading): report as findings, they are often the most severe.
- **Stakeholder taste disguised as critique:** tie every comment to a heuristic, task or principle.

## Acceptance criteria

- [ ] Primary tasks are stated before findings.
- [ ] Every finding has location, evidence, severity, confidence, impact and effort.
- [ ] Severity follows the documented 0 to 4 scale.
- [ ] User impact is not presented as validated without research.
- [ ] Findings that need user testing are identified.

## Sources

- Nielsen Norman Group, 10 usability heuristics and severity ratings: https://www.nngroup.com/
- W3C WCAG 2.2 for accessibility barriers spotted during review: https://www.w3.org/WAI/standards-guidelines/wcag/
