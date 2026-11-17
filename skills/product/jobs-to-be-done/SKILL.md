---
name: jobs-to-be-done
description: >-
  Applies Jobs-to-be-Done to real evidence: writes job statements and job stories, builds a job map,
  analyses the forces of progress (push, pull, anxiety, habit) and derives desired-outcome
  statements and value proposition fit. Use when the user asks for JTBD, job stories, switch
  interviews, a value proposition canvas, or wants to understand why customers hire or fire a
  product. Do not use as a substitute for research: without evidence it produces an interview guide,
  not jobs.
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

# Jobs-to-be-Done

A job is the progress a person tries to make in a given circumstance. Jobs are stable over time;
solutions change.

## When to use

- Explaining adoption or churn ("why do people switch to or away from us?").
- Framing a value proposition or positioning on customer progress, not features.
- Turning interview notes into job stories that a team can design against.

## Inputs

- Interview transcripts or notes, ideally switch interviews about a recent real decision.
- Optional: survey verbatims, support tickets, churn reasons, competitor alternatives used.
- The segment and the decision being studied (adoption, switch, cancellation).

With no evidence: produce a switch interview guide (timeline from first thought to purchase,
past behaviour only) and stop.

## Workflow

1. **Scope the job.** Name the core functional job as verb + object + context
   ("move savings into investments without studying markets"). Avoid product names.
2. **Extract circumstances** from evidence: the triggering situation, time, place, constraints.
3. **Write job stories**: `When <situation>, I want to <motivation>, so I can <expected outcome>.`
   One story per distinct circumstance, each linked to the evidence IDs that support it.
4. **Analyse forces of progress** for the switch decision: push of the current situation, pull of
   the new solution, anxiety of the new, habit of the present. Tag each with `[Observed]` or
   `[Assumption]`.
5. **Map the job** (define, locate, prepare, confirm, execute, monitor, modify, conclude) and mark
   the steps where people struggle today.
6. **Write desired outcomes** as measurable statements: direction + metric + object + context
   ("minimise the time it takes to confirm a transfer reached the right account").
7. **Check value proposition fit** against the Strategyzer Value Proposition Canvas: pains to
   pain relievers, gains to gain creators. Mark gaps and over-served areas.
8. **Note emotional and social jobs** only when the evidence shows them.

## Outputs

- Job statement and segment definition.
- Job stories table: story, evidence IDs, frequency in the sample.
- Forces of progress diagram (2 x 2 table).
- Job map with struggle points.
- Desired outcome statements, ranked by evidence of importance and current dissatisfaction.
- Value proposition fit table with gaps.
- Limits of the evidence (sample size, recruiting bias).

## Edge cases

- **Feature requests as jobs:** "I want export to Excel" is a solution; ask what the export enables.
- **Mixed segments:** split jobs by circumstance, not by demographic.
- **Small samples:** report counts ("4 of 9 participants"), never percentages under 30 people.
- **B2B:** separate the job of the user, the buyer and the approver.

## Acceptance criteria

- [ ] No job statement contains a product, feature or brand name.
- [ ] Every job story cites at least one piece of evidence or is labelled `[Assumption]`.
- [ ] Forces of progress include anxiety and habit, not only push and pull.
- [ ] Desired outcomes are measurable and solution-free.
- [ ] Sample size and its limits are stated.

## Sources

- Nielsen Norman Group on JTBD and interviews: https://www.nngroup.com/
- Strategyzer Value Proposition Canvas: https://www.strategyzer.com/
- Job stories (Intercom, A. Klement) and forces of progress (B. Moesta, Re-Wired Group), cited by name only.
