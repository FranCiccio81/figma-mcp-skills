---
name: prioritization
description: >-
  Ranks initiatives, features or opportunities with a method chosen for the context (RICE, cost of
  delay or WSJF, Kano, opportunity scoring, MoSCoW for scope), makes every score's assumptions
  visible, runs a sensitivity check and explains the trade-offs. Use when asked to prioritise a
  backlog or roadmap, compare initiatives, score features or decide what to cut. Do not use to set
  strategy (use product-strategy) or to define metrics (use product-metrics).
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

# Prioritization

A score is a structured argument, not a measurement. The value of the exercise is in the
assumptions it exposes.

## When to use

- Quarterly or sprint planning with more candidates than capacity.
- Comparing initiatives proposed by different stakeholders.
- Deciding the scope of a first release.

## Inputs

- The list of candidates, each with a one-line description.
- The goal or outcome they should serve (strategy, OKR).
- Any data on reach, impact, effort, deadlines or dependencies.
- Constraints: fixed dates, regulatory obligations, team skills.

## Workflow

1. **Check alignment first.** Drop or flag candidates that serve no current outcome.
2. **Separate non-negotiables** (legal obligations, security fixes, contractual dates). They are
   scheduled, not scored.
3. **Pick the method** for the question:
   - Many comparable features, some data: **RICE** = Reach × Impact × Confidence / Effort.
   - Time-sensitive work with deadlines or decay: **Cost of delay** or **WSJF** (cost of delay / duration).
   - Understanding delight versus basic expectations: **Kano** survey.
   - Choosing which user outcomes to address: **opportunity scoring** (importance versus satisfaction).
   - Scoping a single release: **MoSCoW**.
4. **Score with explicit inputs.** Every number gets a source or an `[Assumption]` label.
   Confidence must drop when evidence is weak.
5. **Run a sensitivity check:** which candidates change rank if the most uncertain input moves
   by ±50 %? Those are where discovery pays off.
6. **Review dependencies and sequencing**; a high score blocked by a dependency moves later.
7. **Write the recommendation** with the cut line and what is explicitly not being done.

## Outputs

A ranked table (candidate, inputs, score, confidence, rank, rank stability), the method and why it
was chosen, the sensitivity findings, the cut line, the not-doing list and the decisions needed.

## Edge cases

- **HiPPO override:** record it as a decision with its owner instead of altering scores.
- **Effort unknown:** use T-shirt sizes and say so; do not fake precision.
- **Everything is Must (MoSCoW):** limit Must to about 60 % of capacity.
- **Comparing apples and oranges** (tech debt versus features): express both in the same outcome
  terms (risk avoided, time saved) or keep separate capacity buckets.

## Acceptance criteria

- [ ] The method choice is justified by the question.
- [ ] Every input has a source or an assumption label.
- [ ] Non-negotiables are separated from scored items.
- [ ] A sensitivity check identifies unstable ranks.
- [ ] A cut line and not-doing list are explicit.

## Sources

- Nielsen Norman Group, prioritisation methods for UX: https://www.nngroup.com/
- Strategyzer on evidence strength: https://www.strategyzer.com/
- RICE (Intercom), WSJF (SAFe, after D. Reinertsen), Kano (N. Kano), cited by name only.
