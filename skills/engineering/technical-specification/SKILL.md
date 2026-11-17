---
name: technical-specification
description: >-
  Writes or reviews a technical specification or design document: context and
  requirements, proposed architecture, data and API contracts, alternatives considered,
  security, privacy, accessibility, performance and observability, rollout and
  migration, risks and open questions, plus architecture decision records. Use when
  the user asks for a tech spec, RFC, design doc, ADR or implementation plan, or a
  review of one.
metadata:
  domain: engineering
  version: "1.0.0"
  status: beta
  scope: universal
  trust: authored
  last-reviewed: "2026-11-17"
---

# Technical specification

## When to use

* Before building something with non-trivial design choices, cross-team impact or migration.
* Recording a significant decision (ADR).

## Inputs

* Product requirements (`product-requirements`), current architecture, constraints (stack, compliance, deadlines), stakeholders.

## Procedure

1. **Context and goals.** Problem, requirements in scope, non-goals, success criteria (functional and non-functional).
2. **Current state** with diagrams of the relevant parts.
3. **Proposal.** Components and responsibilities, data model, API contracts (request, response, errors, versioning), sequence of key flows (Mermaid diagrams).
4. **Alternatives considered** with trade-offs and why they were rejected.
5. **Cross-cutting concerns:** security and privacy (threats, data classification), accessibility for UI work, performance budgets, reliability and failure modes, observability (logs, metrics, alerts), internationalization.
6. **Delivery.** Milestones, feature flags, migration and backfill, rollback plan, testing strategy (`frontend-testing`).
7. **Risks and open questions** with owners and dates.
8. **ADR** for each significant decision: context, decision, status, consequences.
9. **Review mode:** check each section for completeness and testability; list blocking gaps.

## Output

Markdown design document with the sections above and ADRs in the project's ADR folder if one exists.

## Edge cases

* Small changes: a short ADR or PR description is enough; do not force a full document.
* Unknown performance or scale numbers: state assumptions and plan a measurement.
* Decisions already made: document them as ADRs with honest consequences.

## Acceptance criteria

* At least one alternative is documented with trade-offs.
* Every API contract includes error cases.
* Rollback and observability are defined.
* Assumptions are labeled; nothing presented as measured unless it was.

## Sources

* Google Engineering Practices: https://google.github.io/eng-practices/
* OWASP Cheat Sheet Series (threat modeling): https://cheatsheetseries.owasp.org/
