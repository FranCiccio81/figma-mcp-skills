---
name: technical-specification
description: >-
  Writes or reviews a technical specification (design doc or RFC) for a frontend or full-stack
  feature: context and goals, non-goals, proposed design, alternatives considered, API and data
  contracts, state and error handling, accessibility, security and privacy, performance, testing,
  rollout, observability and risks. Use when asked for a tech spec, design doc, RFC or
  architecture proposal for a feature, or to review one before implementation. Do not use for
  product requirements (use product-requirements).
license: MIT
metadata:
  version: "1.0.0"
  domain: engineering
  status: beta
  trust: internal
  sources: "OWASP,W3C-WCAG22,WEB-DEV"
  platforms: "any"
  last-reviewed: "2026-11-17"
---

# Technical specification

A tech spec is where expensive mistakes are cheap. It records the decision, the alternatives and
why they lost.

## When to use

- Before implementing a feature that spans several components, services or teams.
- When a change affects public APIs, data models, security or performance.
- Reviewing a design doc.

## Inputs

- PRD or problem statement, designs, existing architecture and constraints.
- Non-functional requirements (accessibility level, performance budgets, compliance).

## Workflow

1. **Context and goals:** link the PRD; list goals and explicit non-goals.
2. **Current state:** relevant architecture, with a diagram (Mermaid) if helpful.
3. **Proposed design:** components and responsibilities, data flow, state management, API
   contracts (request, response, errors), data model changes and migrations.
4. **Alternatives:** at least two, with trade-offs and the reason for rejection.
5. **Cross-cutting concerns:** accessibility (WCAG 2.2 AA by default), security and privacy
   (threats, data classification, OWASP references), performance (budgets), localization,
   offline and error handling, analytics.
6. **Testing strategy:** levels and critical scenarios (see `frontend-testing`).
7. **Rollout:** flags, migration steps, backward compatibility, rollback plan.
8. **Observability:** logs (without personal data), metrics, alerts.
9. **Risks and open questions** with owners and dates.

## Outputs

A Markdown design doc with the sections above, diagrams, a decision record, and a review status
table (reviewer, area, status).

## Edge cases

- **Small change:** use a one-page variant (context, decision, alternatives, risks).
- **Unknown feasibility:** propose a spike with a time box and the question it answers.
- **Cross-team dependencies:** list contracts and owners; do not assume another team's timeline.

## Acceptance criteria

- [ ] Goals and non-goals are explicit.
- [ ] At least two alternatives are compared.
- [ ] API contracts include error cases.
- [ ] Accessibility, security, performance and rollback are addressed.
- [ ] Open questions have owners.

## Sources

- OWASP Cheat Sheet Series (threat modelling, API security): https://cheatsheetseries.owasp.org/
- W3C WCAG 2.2: https://www.w3.org/WAI/standards-guidelines/wcag/
- web.dev performance budgets: https://web.dev/
