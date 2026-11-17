---
name: experiment-design
description: >-
  Designs product experiments that can actually change a decision: hypothesis,
  method (A/B test, fake door, concierge, prototype test), primary and guardrail
  metrics, sample size and duration, decision rules set in advance, and analysis
  pitfalls. Use when the user wants to test an idea, run an A/B test, validate an
  assumption cheaply, or interpret experiment results.
metadata:
  domain: product
  version: "1.0.0"
  status: beta
  scope: universal
  trust: authored
  last-reviewed: "2026-11-17"
---

# Experiment design

## When to use

* Validating a risky assumption before building (`product-discovery`, `opportunity-solution-tree`).
* Planning or reviewing an A/B test.
* Interpreting results without fooling ourselves.

## Inputs

* The decision the experiment informs and the assumption behind it.
* Baseline metric values and traffic or participant volume. If unknown, the plan must start by measuring them; never invent baselines.

## Procedure

1. **Decision first.** "If the result is X we will do A, otherwise B." No decision, no experiment.
2. **Hypothesis.** We believe [change] for [segment] will cause [effect on metric] because [rationale from evidence].
3. **Choose the cheapest valid method.**
   * Behavioral, at scale: A/B test (needs enough traffic).
   * Demand: fake door or landing-page test (disclose honestly afterwards; avoid deceptive patterns).
   * Value delivery: concierge or Wizard of Oz.
   * Usability: prototype test (`usability-testing`), not an A/B test.
4. **Metrics.** One primary metric tied to the hypothesis, guardrails (errors, complaints, revenue, accessibility regressions), and diagnostic metrics.
5. **Power and duration.** Compute sample size from baseline, minimum detectable effect, significance level (commonly 5 %) and power (commonly 80 %). Run full weekly cycles. Fix the stopping rule in advance; do not stop when it "looks significant".
6. **Risks.** Novelty effects, sample ratio mismatch, interference between variants, multiple comparisons, segment cherry-picking, ethical and legal constraints (consent, financial or health impact).
7. **Analysis plan** written before launch: tests to run, segments pre-registered, how ties are decided.

## Output

Experiment brief: decision, hypothesis, method, variants, audience and allocation, metrics (primary, guardrails), sample size calculation with inputs, duration, stopping and decision rules, risks, analysis plan. For results: effect size with confidence interval, guardrail status, decision taken.

## Edge cases

* Low traffic: prefer qualitative or larger-effect tests; do not run underpowered A/B tests and report noise.
* Inconclusive result: that is a result; apply the pre-set rule for ties.
* Regulated contexts: experiments that change prices, risk disclosures or eligibility need compliance approval first.

## Acceptance criteria

* Decision rule and stopping rule are written before launch.
* Sample size shows its inputs.
* Results report effect size and uncertainty, not only a p-value.

## Sources

* Nielsen Norman Group, A/B testing and research methods: https://www.nngroup.com/
* Strategyzer, testing business ideas: https://www.strategyzer.com/
