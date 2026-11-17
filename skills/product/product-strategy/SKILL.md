---
name: product-strategy
description: >-
  Drafts or reviews a product strategy: diagnosis of the situation, target segments,
  where to play and how to win, strategic bets with explicit assumptions, guardrails
  and the measures that show progress. Use when the user writes a product vision or
  strategy, defines annual bets or roadmap themes, evaluates a strategic option, or
  asks whether a plan is actually a strategy.
metadata:
  domain: product
  version: "1.0.0"
  status: beta
  scope: universal
  trust: authored
  last-reviewed: "2026-11-17"
---

# Product strategy

## When to use

* Writing or reviewing a vision, strategy or set of strategic bets.
* Turning a list of initiatives into a coherent strategy, or showing that it is not one.

## Inputs

* Company goals, market context, competitive alternatives, capabilities, constraints (budget, regulation, technology).
* Evidence about customers and the market. Missing evidence becomes explicit assumptions.

## Procedure

1. **Diagnosis.** What is going on and what is the crux challenge? Use evidence; separate facts from interpretation.
2. **Guiding policy.** Target segments and jobs (`jobs-to-be-done`), where to play and where *not* to play, how to win (differentiation that customers value and competitors cannot easily copy).
3. **Strategic bets.** Two to five bets, each with: the opportunity, why now, the key assumption, the leading indicator, the kill or pivot criterion, and the investment level.
4. **Coherent actions.** Initiatives that implement the bets; anything that serves no bet is either a guardrail (compliance, reliability) or a candidate to stop.
5. **Measures.** One outcome per bet plus guardrail metrics (`product-metrics`).
6. **Stress test.** Pre-mortem ("it is a year from now and this failed; why?"), dependency check, and capacity check against the team.

## Output

Strategy document: diagnosis, guiding policy, bets table, initiative mapping, measures, risks and pre-mortem findings, open assumptions and when they will be tested.

## Edge cases

* "Strategy" is a list of goals or features: show the gap and ask for the diagnosis first.
* Too many bets for the capacity: force-rank and state what is deferred.
* Regulated markets: regulatory change is part of the diagnosis; confirm with domain experts.

## Acceptance criteria

* The document states what the product will *not* do.
* Every bet has an assumption, a leading indicator and a stop criterion.
* Facts cite sources; everything else is labeled as assumption or interpretation.

## Sources

* Strategyzer, business model and strategy tools: https://www.strategyzer.com/
* Nielsen Norman Group, UX strategy: https://www.nngroup.com/
