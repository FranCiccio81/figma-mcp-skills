---
name: prioritization
description: >-
  Prioritizes a backlog, roadmap or set of opportunities with an explicit, explainable
  method (RICE, cost of delay, Kano, opportunity scoring, MoSCoW for scoping), exposes
  the assumptions behind each score, and produces a ranked list with trade-offs. Use
  when the user must decide what to build first, compare initiatives, cut scope, or
  justify a priority order to stakeholders.
metadata:
  domain: product
  version: "1.0.0"
  status: beta
  scope: universal
  trust: authored
  last-reviewed: "2026-11-17"
---

# Prioritization

## When to use

* Ranking initiatives, features or opportunities; scoping a release; defending a roadmap.

## Inputs

* Candidate items with a short description each.
* Strategy or outcome they serve (`product-strategy`), constraints (capacity, deadlines, dependencies, compliance dates).
* Any data for reach, impact or effort. Missing data becomes a labeled estimate, never a silent guess.

## Procedure

1. **Filter before scoring.** Remove items that serve no current outcome; separate mandatory items (legal, security, contractual) which are not ranked against optional ones.
2. **Choose the method for the question.**
   * Comparing many similar items: RICE (Reach × Impact × Confidence ÷ Effort).
   * Time-sensitive value: cost of delay, or cost of delay divided by duration.
   * Understanding satisfaction drivers: Kano survey.
   * Scoping a fixed release: MoSCoW, with "Must" limited to what makes the release viable.
3. **Score transparently.** One row per item with every input, its source and confidence. Use consistent scales across items.
4. **Sanity check.** Does the top of the list match the strategy? Do dependencies force a different order? Is one team overloaded?
5. **Sensitivity.** Show which ranks change if the least certain inputs are off by a reasonable margin.
6. **Decide and communicate:** ranked list, what is explicitly *not* being done now, and when it will be revisited.

## Output

Scoring table, ranked list, sensitivity notes, trade-offs, explicit "not now" list, review date.

## Edge cases

* Highest-paid-person's opinion overrides scores: record the decision and its rationale; scores are inputs, not verdicts.
* Effort unknown: ask engineering for ranges; use the upper bound in scoring.
* Accessibility and security fixes: treat as mandatory or score with legal and user harm included, never as "nice to have".

## Acceptance criteria

* Every score shows its inputs, sources and confidence.
* Mandatory items are separated from ranked ones.
* A "not now" list exists.

## Sources

* Nielsen Norman Group, prioritization methods: https://www.nngroup.com/
* Strategyzer: https://www.strategyzer.com/
