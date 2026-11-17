---
name: product-metrics
description: >-
  Defines how a product or feature is measured: outcome and North Star metric, input metrics,
  HEART goals-signals-metrics, precise metric definitions, guardrails, instrumentation plan with
  event names and properties, and privacy constraints. Use when asked to choose KPIs, define success
  metrics, build a measurement or tracking plan, review a dashboard's metrics or prepare analytics
  for a launch. Do not use to size an experiment (use experiment-design).
license: MIT
metadata:
  version: "1.0.0"
  domain: product
  status: beta
  trust: internal
  sources: "NNG,STRATEGYZER"
  platforms: "any"
  last-reviewed: "2026-11-17"
---

# Product metrics and measurement

A metric that nobody would act on is noise. Each metric has a decision attached to it.

## When to use

- Launching a product or feature and defining success.
- Writing the analytics section of a PRD.
- Auditing a dashboard full of vanity metrics.

## Inputs

- The outcome or goal, and the decisions the team expects to take.
- The product flows concerned.
- Existing analytics schema, tools and naming conventions.
- Privacy and consent constraints (GDPR, Swiss nLPD, internal policies).

## Workflow

1. **Start from decisions.** For each decision, ask which signal would change it.
2. **Apply HEART** (Happiness, Engagement, Adoption, Retention, Task success) with
   Goals → Signals → Metrics, keeping only the categories that matter for this product.
3. **Choose one outcome metric** for the feature (or a North Star for a product) and two to four
   input metrics the team can influence directly.
4. **Add guardrails** that must not degrade (error rate, support contacts, opt-outs, latency,
   accessibility complaints).
5. **Define each metric precisely:** name, question it answers, formula (numerator, denominator,
   time window), segment, data source, owner, refresh rate, known biases.
6. **Write the tracking plan:** event name in the project convention (for example
   `object_action` in snake_case), trigger, properties with types and allowed values, platform,
   consent category. Reuse existing events before adding new ones.
7. **Check privacy:** no personal data in event properties, minimisation, consent gating,
   retention period.
8. **Plan the read-out:** baseline, target, date, and what happens at each result.

## Outputs

A measurement plan: decisions, HEART table, metric definitions table, guardrails, tracking plan
table, privacy notes, read-out plan. For a dashboard audit: each metric with keep, change or
remove and the reason.

## Edge cases

- **Rates without denominators** ("10,000 clicks"): replace with a rate and its base.
- **Averages on skewed data:** prefer medians or percentiles.
- **Task success on mobile without events:** add explicit completion events, not inferred ones.
- **Small segments:** suppress or aggregate to avoid re-identification.

## Acceptance criteria

- [ ] Every metric maps to a decision.
- [ ] Exactly one outcome metric per feature, with guardrails.
- [ ] Each metric has a full definition (formula, window, source, owner).
- [ ] Tracking events contain no personal data and follow the project naming convention.
- [ ] Baseline, target and read-out date are set or marked as to be measured.

## Sources

- Nielsen Norman Group on UX metrics: https://www.nngroup.com/
- Strategyzer on evidence and metrics for business ideas: https://www.strategyzer.com/
- HEART framework: K. Rodden, H. Hutchinson, X. Fu, Google (2010), cited by name only.
