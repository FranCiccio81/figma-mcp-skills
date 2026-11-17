---
name: opportunity-solution-tree
description: >-
  Builds an opportunity solution tree that links one measurable outcome to customer
  opportunities (needs, pains, desires) found in research, then to candidate
  solutions and the assumption tests that de-risk them. Use when a team needs to
  choose what to work on toward an outcome, map research findings into opportunities,
  or avoid jumping from a goal straight to a feature.
metadata:
  domain: product
  version: "1.0.0"
  status: beta
  scope: universal
  trust: authored
  last-reviewed: "2026-11-17"
---

# Opportunity solution tree

## When to use

* A team has an outcome (for example "increase second-week retention") and many feature ideas.
* After interviews, to turn findings into a structured choice.

## Inputs

* One outcome metric with baseline and target (see `product-metrics`).
* Research findings with sources. Without research, opportunities are hypotheses and must be labeled as such.

## Procedure

1. **Root: the outcome.** One product outcome the team can influence (a behavior change), not a business output it cannot directly move (revenue) and not a feature.
2. **Opportunities.** Write each from the customer's perspective ("I don't know if I'm saving enough"), sourced from research. Cluster them; parent opportunities are broad, children are specific enough to solve.
3. **Assess opportunities** on: size (how many, how often), severity, alignment with strategy, evidence strength. Pick one target opportunity; record why the others were not picked.
4. **Solutions.** Generate at least three distinct solutions for the target opportunity, to avoid anchoring on the first.
5. **Assumption tests.** For each solution, list its riskiest assumptions and a small test. Compare solutions on test results, not on opinions.
6. **Keep it alive.** Update the tree when new research arrives; date each node's evidence.

## Output

Tree as an indented Markdown list or a Mermaid diagram, plus tables: opportunities (statement, source, size, severity, evidence strength), selection rationale, solutions with assumptions and tests.

## Edge cases

* Outcome is actually an output ("ship feature X"): rewrite it with the team as a behavior change.
* Opportunity phrased as a solution ("needs dark mode"): ask what the person is trying to achieve and reframe.
* Too many opportunities: cluster before scoring; a flat list of fifty is not a tree.

## Acceptance criteria

* Exactly one outcome at the root.
* Every opportunity cites a source or is labeled *Hypothesis*.
* At least three solutions for the chosen opportunity, each with at least one assumption test.

## Sources

* Product Talk, Teresa Torres (originator of the method): https://www.producttalk.org/opportunity-solution-trees/
* Nielsen Norman Group: https://www.nngroup.com/
