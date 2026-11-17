---
name: value-proposition-design
description: >-
  Builds and stress-tests a value proposition by mapping customer jobs, pains and
  gains against products, pain relievers and gain creators, then defines the evidence
  needed to prove fit. Use when the user wants to articulate or sharpen a value
  proposition, check problem-solution fit, compare positioning options, or prepare
  messaging grounded in customer needs.
metadata:
  domain: product
  version: "1.0.0"
  status: beta
  scope: universal
  trust: authored
  last-reviewed: "2026-11-17"
---

# Value proposition design

## When to use

* Defining or refreshing what a product promises and to whom.
* Checking whether a feature set actually addresses the most important pains.
* Comparing alternative propositions before testing them.

## Inputs

* One customer segment at a time (a proposition for "everyone" is not testable).
* Known jobs, pains and gains with their evidence (see `jobs-to-be-done`).
* Competitive alternatives, including "do nothing".

## Procedure

1. **Customer profile.** List jobs, pains and gains for the segment. Rank by importance *to the customer*, with the evidence source for each rank.
2. **Value map.** List the products and services, then the specific pain relievers and gain creators. Each reliever must point to a named pain.
3. **Fit check.** Mark which top-ranked pains and gains are addressed. Unaddressed top pains are the biggest risk; relievers for unranked pains are likely waste.
4. **Differentiation.** Compare with the alternatives the customer would otherwise use. State what is meaningfully better, for whom, and at what cost to switch.
5. **Proposition statement.** For [segment] who [job or pain], [product] is a [category] that [key benefit]; unlike [alternative], it [differentiator]. Draft 2 or 3 options when uncertain.
6. **Evidence plan.** For each option, the assumption that must hold, the test (`experiment-design`), and the signal that proves fit.

## Output

Canvas in Markdown tables (profile, value map, fit matrix), proposition options, differentiation table, list of assumptions with test plan, recommendation and confidence.

## Edge cases

* Multi-sided products: one canvas per side, plus the dependency between them.
* Regulated financial products: promises must be accurate and not misleading; route claims through compliance review before external use.
* Features without a mapped pain: flag them as candidates for removal or for discovery.

## Acceptance criteria

* Every pain reliever and gain creator maps to a ranked customer pain or gain.
* Rankings cite evidence or are labeled *Assumption*.
* At least one falsifiable test per proposition option.

## Sources

* Strategyzer, Value Proposition Canvas: https://www.strategyzer.com/
* Nielsen Norman Group: https://www.nngroup.com/
