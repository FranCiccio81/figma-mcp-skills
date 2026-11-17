---
name: product-requirements
description: >-
  Writes or reviews a product requirements document (PRD) or a feature specification:
  problem, evidence, goals and non-goals, users and scenarios, functional and
  non-functional requirements, acceptance criteria, success metrics, risks and open
  questions. Use when the user asks for a PRD, feature spec, user stories with
  acceptance criteria, or a review of an existing requirements document.
metadata:
  domain: product
  version: "1.0.0"
  status: beta
  scope: universal
  trust: authored
  last-reviewed: "2026-11-17"
---

# Product requirements

Two modes: **PRD** (why and what, for a product area or initiative) and **Feature spec** (precise behavior for one feature, ready for design and engineering). Pick the mode from the request; ask if unclear.

## When to use

* "Write a PRD", "spec this feature", "turn this idea into requirements", "review my PRD".
* Not for: technical design (use `technical-specification`), UI handoff (use `figma-spec-handoff`).

## Inputs

* Problem or idea, target users, business goal, constraints, deadline drivers.
* Evidence: research, data, support tickets. Ask for it. Do not invent quotes, numbers or user insights.

## Procedure

1. **Problem and evidence.** Who has the problem, what it costs them, why it matters now. Evidence table with four labeled kinds: *Observation*, *Validated finding*, *Assumption*, *Recommendation*.
2. **Goals and non-goals.** Outcome goals with metrics (`product-metrics`); non-goals to prevent scope creep.
3. **Users and scenarios.** Primary and secondary users; key scenarios or job stories (`jobs-to-be-done`).
4. **Requirements.** Numbered, testable, prioritized (Must, Should, Could). Functional requirements describe behavior, not UI layout.
5. **Non-functional requirements.** Accessibility (WCAG 2.2 AA minimum), performance, security and privacy, localization, platform coverage, legal and regulatory requirements with owner.
6. **Acceptance criteria** per requirement, in Given / When / Then form, including error, empty and edge states.
7. **Release and measurement.** Rollout plan, instrumentation, success and guardrail metrics, decision date.
8. **Risks, dependencies, open questions** with owners.
9. **Review mode:** score each section as Complete, Weak or Missing, and list the top issues that would block design or engineering.

## Output

Markdown document with the sections above, in the user's language. Feature specs add a states table (state, trigger, behavior, copy reference) and a requirements traceability list.

## Edge cases

* No evidence available: write the PRD with assumptions clearly labeled and a discovery step first.
* Solution dictated by a stakeholder: document it, and list the assumptions it depends on.
* Regulated domain (finance, health): list applicable regulations as requirements to be confirmed by compliance; do not assert legal interpretations.

## Acceptance criteria

* States the user problem, why it matters, business impact, evidence and uncertainties, proposed solution and success indicators.
* Every requirement is testable and has acceptance criteria.
* Non-goals and open questions are present.
* No fabricated research, metrics or quotes.

## Sources

* Nielsen Norman Group: https://www.nngroup.com/
* WCAG 2.2 (non-functional accessibility baseline): https://www.w3.org/TR/WCAG22/
