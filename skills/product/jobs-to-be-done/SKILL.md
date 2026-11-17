---
name: jobs-to-be-done
description: >-
  Applies Jobs-to-be-Done to understand why people adopt or switch products: plans
  switch interviews, extracts functional, emotional and social jobs, forces of
  progress, and writes job stories grounded in evidence. Use when the user mentions
  JTBD, job stories, why customers hire or fire a product, switching behavior, or
  wants needs framed independently of solutions.
metadata:
  domain: product
  version: "1.0.0"
  status: beta
  scope: universal
  trust: authored
  last-reviewed: "2026-11-17"
---

# Jobs to be Done

## When to use

* Understanding motivations behind adoption, churn or switching.
* Reframing feature requests as underlying jobs.
* Writing job stories for a PRD.

## Inputs

* Target segment and the behavior of interest (recent sign-up, switch from competitor, churn).
* Interview transcripts or notes if they exist. Without them, output a research plan and clearly marked hypotheses only.

## Procedure

1. **Recruit on behavior, not demographics:** people who recently made the switch (ideally within the last few months) so the decision is still remembered.
2. **Interview along the timeline:** first thought, passive looking, active looking, deciding, first use, ongoing use. Ask for concrete past events ("tell me about the day you…"), never hypotheticals ("would you…").
3. **Code the forces of progress:** push of the current situation, pull of the new solution, anxiety about the new, habit of the present. A switch happens when push + pull exceed anxiety + habit.
4. **Extract jobs** in solution-free language: functional ("get my tax documents ready"), emotional ("feel in control of retirement"), social ("look prepared to my partner"). Note the circumstance; the circumstance is what makes jobs actionable.
5. **Write job stories:** *When* [situation], *I want to* [motivation], *so I can* [expected outcome]. One story per distinct circumstance.
6. **Count support:** number of interviews in which each job and force appeared. Patterns from fewer than a handful of interviews are hypotheses.

## Output

Jobs report: method and sample, timeline per interview (summary), forces table, job list (type, statement, circumstance, interview count, representative paraphrased evidence), job stories, hypotheses still to test, implications for product.

## Edge cases

* Only hypothetical data available: label every job *Hypothesis*, propose the interview plan.
* B2B: separate the jobs of the buyer, the user and the approver.
* Jobs that conflict across segments: keep segments separate; do not average them.

## Acceptance criteria

* Jobs contain no product features or UI words.
* Every job has a circumstance and an evidence count.
* Quotes are paraphrased or short, attributed to anonymized participants; no invented quotes.

## Sources

* Nielsen Norman Group on JTBD and interviewing: https://www.nngroup.com/
* Strategyzer, customer jobs in the Value Proposition Canvas: https://www.strategyzer.com/
