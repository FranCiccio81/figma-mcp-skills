---
name: product-metrics
description: >-
  Defines how product success is measured: outcome and guardrail metrics, metric
  definitions with formulas, a tracking plan (events, properties, ownership), privacy
  constraints, and a review routine. Use when the user asks which metrics or KPIs to
  track, needs a tracking or instrumentation plan, defines success metrics for a
  feature, or wants to analyze product analytics without misleading conclusions.
metadata:
  domain: product
  version: "1.0.0"
  status: beta
  scope: universal
  trust: authored
  last-reviewed: "2026-11-17"
---

# Product metrics

## When to use

* Defining success metrics for a PRD, an experiment or a strategy bet.
* Writing an analytics tracking plan.
* Reviewing a dashboard or a metric movement.

## Inputs

* The outcome the product should drive and the user behavior that indicates it.
* Existing analytics tools, data model and privacy policy.
* Current baselines if they exist. Never fabricate baselines or benchmarks.

## Procedure

1. **Metric hierarchy.** One outcome metric per goal (behavior change), leading indicators that move earlier, guardrails that must not degrade (errors, latency, complaints, accessibility, unsubscribe or opt-out rates).
2. **Define each metric precisely:** name, question it answers, formula, population, time window, unit, data source, owner, known biases.
3. **Tracking plan.** Event names in a consistent convention (object + action, past tense), required properties, when each fires, which screens. Avoid personal data in properties; confirm consent requirements with privacy owners.
4. **Quality checks.** Test events in a staging environment; compare counts with backend truth; monitor for silent breaks after releases.
5. **Interpretation rules.** Look at distributions and segments, not only averages; check seasonality; correlation is not causation, use experiments (`experiment-design`) for causal claims.
6. **Review routine.** Cadence, audience, and the decisions each metric review can trigger.

## Output

Metric definitions table, metric hierarchy, tracking plan table (event, trigger, properties, platform, owner), data-quality checklist, privacy notes, review routine.

## Edge cases

* Vanity metrics (page views, downloads) proposed as goals: replace with behavior-based outcomes, keep them as diagnostics.
* Small samples: report ranges and avoid percentage changes on tiny bases.
* Regulated data (financial, health): minimize collection; involve privacy or compliance owners before instrumenting.

## Acceptance criteria

* Every metric has a formula, population, window and owner.
* At least one guardrail per outcome metric.
* Tracking plan contains no personal data unless explicitly approved.
* No baseline or target appears without a source or an "assumption" label.

## Sources

* Nielsen Norman Group, analytics and UX metrics: https://www.nngroup.com/
* Strategyzer: https://www.strategyzer.com/
