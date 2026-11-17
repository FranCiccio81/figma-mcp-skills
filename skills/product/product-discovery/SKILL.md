---
name: product-discovery
description: >-
  Structures product discovery for a problem space: frames the problem, maps
  assumptions by risk, chooses the cheapest evidence-gathering activities, and
  synthesizes what was learned into a decision (pursue, pivot, park). Use when the
  user explores a new product idea or problem area, asks whether a problem is worth
  solving, or needs a discovery plan before committing to a solution.
metadata:
  domain: product
  version: "1.0.0"
  status: beta
  scope: universal
  trust: authored
  last-reviewed: "2026-11-17"
---

# Product discovery

## When to use

* "Is this worth building?", "help me explore this problem", "plan discovery for X".
* Before a PRD exists, or when a PRD rests on untested assumptions.
* Not for: writing the PRD (use `product-requirements`), running a specific study (use `ux-research-planning`).

## Inputs

* Problem statement or idea, target users, business context and constraints.
* Existing evidence: research, analytics, support tickets, sales notes. Ask for it; do not assume it exists.

## Procedure

1. **Frame the problem** in one sentence: who struggles, with what, in which situation, and what it costs them. Reject solution-shaped framings ("users need a dashboard") and rewrite them as problems.
2. **Separate the knowledge base** into four lists: *Observations* (directly seen, with source), *Validated findings* (supported by sufficient evidence), *Assumptions* (believed, not tested), *Unknowns*.
3. **Map assumptions** by type (desirability, viability, feasibility, usability, ethical or legal) and by risk = impact if wrong × lack of evidence. The top-right ones are the "leap of faith" assumptions.
4. **Pick the cheapest credible test** for each risky assumption: existing data analysis, interviews (`ux-research-planning`), prototype tests (`usability-testing`), fake door or concierge tests (`experiment-design`). State the decision each test informs and the result that would change your mind.
5. **Time-box** discovery and define the decision meeting: what will be decided, by whom, on what evidence.
6. **Synthesize** results back into the four lists and recommend: pursue (with the opportunity to address), pivot (which assumption broke), or park.

## Output

Discovery brief: problem statement, user and business impact, evidence table (claim, type, source, strength), assumption map, test plan (assumption, method, success signal, cost, owner), decision criteria, recommendation with confidence.

## Edge cases

* No users accessible: use proxy evidence (support logs, reviews, sales calls), label confidence Low, plan access as the first task.
* Stakeholder has already decided the solution: still map its assumptions; present the risk of skipping tests.
* Regulated domains: add legal and compliance assumptions explicitly; never treat them as tested without expert input.

## Acceptance criteria

* No user need is stated as validated without cited evidence.
* Each risky assumption has a test with a falsifiable success signal.
* The recommendation states confidence and what would change it.
* User problem, why it matters, business impact, evidence and uncertainties, proposed next step and success indicators are all present.

## Sources

* Double Diamond (Design Council): https://www.designcouncil.org.uk/
* Nielsen Norman Group, discovery and research methods: https://www.nngroup.com/
* Strategyzer, testing business ideas: https://www.strategyzer.com/
