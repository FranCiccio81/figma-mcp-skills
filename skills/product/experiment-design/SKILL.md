---
name: experiment-design
description: >-
  Designs product experiments before they run: hypothesis, primary and guardrail metrics, minimum
  detectable effect, sample size and duration estimate, randomisation unit, risks and a decision
  rule fixed in advance; also chooses a non-A/B method when traffic is too low. Use when asked to
  plan an A/B test, fake door, pilot or any experiment, to size a test, or to review an experiment
  plan or read-out. Do not use to analyse qualitative research (use usability-testing or
  research-planning).
license: MIT
metadata:
  version: "1.0.0"
  domain: product
  status: beta
  trust: internal
  sources: "STRATEGYZER,NNG"
  platforms: "any"
  last-reviewed: "2026-11-17"
---

# Experiment design

The decision rule is written before the data exists. Otherwise the experiment only decorates an
opinion.

## When to use

- Planning an A/B or multivariate test.
- Choosing between an A/B test, a fake door, a concierge test or a usability test.
- Reviewing an experiment read-out for validity.

## Inputs

- The decision the experiment informs and the person who will make it.
- Hypothesis or assumption (from `product-discovery`).
- Baseline rate of the primary metric and available traffic per week.
- Constraints: legal, brand, fairness between users, minimum runtime.

## Workflow

1. **Write the hypothesis:** "Because <evidence>, we believe <change> for <segment> will cause
   <effect on metric>. We will know when <metric> moves by at least <MDE> within <duration>."
2. **Pick metrics:** one primary metric tied to the decision, two or three guardrails (errors,
   complaints, revenue, accessibility regressions), plus a sample ratio check.
3. **Choose the unit of randomisation** (user, account, session, household) and keep it consistent
   with the metric to avoid contamination.
4. **Estimate sample size.** For a conversion metric with baseline `p` and absolute effect `d`,
   at 80 % power and 5 % two-sided significance, a quick estimate per variant is
   `n ≈ 16 × p × (1 − p) / d²`. Use a proper calculator for the final plan and state the
   assumptions.
5. **Estimate duration** = total sample / eligible traffic per day, rounded up to full weeks to
   cover weekly cycles. If longer than the decision allows, change method (step 6).
6. **Choose an alternative when traffic is too low:** fake door with a pre-set click threshold,
   painted door, concierge or Wizard-of-Oz pilot, staged rollout with before/after and a control
   region, or qualitative usability testing.
7. **Pre-register the decision rule:** ship, iterate or stop, for each outcome including
   "inconclusive".
8. **List validity threats:** peeking, multiple comparisons, novelty effect, seasonality,
   sample ratio mismatch, interaction with other experiments, bots.
9. **Plan ethics and compliance:** consent where needed, no dark patterns, equal treatment for
   regulated disclosures, data retention.

## Outputs

An experiment plan: decision, hypothesis, variants, unit, metrics table (definition, source,
baseline, MDE), sample and duration estimate with formula and assumptions, decision rule,
validity threats and mitigations, ethics notes, read-out date. For a read-out review: a validity
checklist with pass or fail and the conclusion the data actually supports.

## Edge cases

- **Baseline unknown:** run an A/A or measure for one cycle first.
- **Several primary metrics requested:** keep one; others become secondary with corrected thresholds.
- **Result "trending" but not significant:** report as inconclusive, do not extend runtime without a pre-set rule.
- **Regulated content (prices, risk disclosures):** never vary legally required information.

## Acceptance criteria

- [ ] Exactly one primary metric, with guardrails.
- [ ] Sample size and duration are computed and their assumptions stated.
- [ ] The decision rule covers the inconclusive case and is fixed before launch.
- [ ] Validity threats and mitigations are listed.
- [ ] A low-traffic alternative is proposed when duration exceeds the decision window.

## Sources

- Strategyzer, *Testing Business Ideas* experiment library: https://www.strategyzer.com/
- Nielsen Norman Group on A/B testing and its limits: https://www.nngroup.com/
- Sample size rule of thumb (n ≈ 16σ²/δ²): R. Lehr (1992), cited by name only.
