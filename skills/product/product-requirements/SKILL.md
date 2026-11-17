---
name: product-requirements
description: >-
  Writes or reviews a product requirements document (PRD) or feature specification that makes the
  user problem, its importance, business impact, evidence, uncertainties, proposed solution, scope,
  requirements and success indicators explicit. Use when asked for a PRD, feature spec, one-pager,
  epic description or when a spec must be checked before delivery. Do not use for component-level
  design system specs (use component) or for engineering design docs (use technical-specification).
license: MIT
metadata:
  version: "1.0.0"
  domain: product
  status: beta
  trust: internal
  sources: "NNG,W3C-WCAG22,STRATEGYZER"
  platforms: "any"
  last-reviewed: "2026-11-17"
---

# Product requirements

A good PRD lets a designer, an engineer and a compliance reviewer reach the same understanding
without a meeting. It separates what is known from what is assumed.

## When to use

- A feature moves from discovery to delivery.
- A stakeholder sends a one-line request that needs scoping.
- Reviewing an existing PRD for gaps before sprint planning.

## Inputs

- Problem statement or request, and who asked.
- Evidence: research, analytics, tickets, discovery brief.
- Constraints: platforms, deadlines, regulation, dependencies, design system.
- Optional: designs (Figma links), existing PRD to review.

## Workflow

1. **State the problem** from the user's point of view, with the affected segment and frequency.
2. **Explain why it matters**: user impact and business impact (revenue, cost, risk, retention),
   each with an evidence label. If impact is unknown, say so and propose how to estimate it.
3. **List evidence and uncertainties** in two separate tables. Uncertainties get an owner and a
   way to resolve them.
4. **Describe the proposed solution** at the level of behaviour, not pixels. Link designs.
5. **Set scope**: in scope, out of scope, and later. Name the smallest valuable release.
6. **Write requirements** as numbered, testable statements: functional, content, accessibility
   (WCAG 2.2 AA by default), privacy and security, performance, analytics, localization,
   platform specifics. Mark each Must, Should or Could.
7. **Define success indicators**: one primary outcome metric with baseline and target, two or
   three guardrails, and the date of the read-out.
8. **Add acceptance criteria** in Given / When / Then form for each Must requirement.
9. **Plan rollout**: feature flag, staged release, support readiness, rollback condition.
10. **Review pass**: run the checklist in [the PRD template](references/prd-template.md) and list gaps.

## Outputs

A Markdown PRD following [references/prd-template.md](references/prd-template.md). When reviewing,
a gap report: section, problem, risk, suggested fix.

## Edge cases

- **Solution dictated by a stakeholder:** keep it, but record the problem it is supposed to
  solve and the assumption that it will.
- **No baseline metric:** make "instrument and measure baseline" a Must requirement.
- **Regulated features:** add a compliance section with the applicable rule and the approver.
- **Multi-platform:** write shared behaviour once, then platform deltas (iOS, Android, web).

## Acceptance criteria

- [ ] Problem, why it matters, business impact, evidence and uncertainties, proposed solution and success indicators are all present.
- [ ] Evidence and assumptions are in separate tables with labels.
- [ ] Every Must requirement has Given / When / Then acceptance criteria.
- [ ] Accessibility requirements cite WCAG 2.2 success criteria or the project rule.
- [ ] Out-of-scope items are listed.
- [ ] No metric, quote or date is invented.

## Sources

- Nielsen Norman Group on requirements and UX in agile: https://www.nngroup.com/
- W3C WCAG 2.2: https://www.w3.org/WAI/standards-guidelines/wcag/
- Strategyzer on testing assumptions: https://www.strategyzer.com/
