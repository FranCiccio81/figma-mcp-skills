---
name: product-strategy
description: >-
  Builds or critiques a product strategy: diagnosis of the situation, guiding policy, coherent
  actions, target segment, value proposition and positioning, strategic bets with explicit
  assumptions and the metrics that tell if the strategy works. Use when asked to write, review or
  stress-test a product strategy, vision-to-roadmap link, positioning or value proposition. Do not
  use for ranking a backlog (use prioritization) or writing a feature PRD (use product-requirements).
license: MIT
metadata:
  version: "1.0.0"
  domain: product
  status: beta
  trust: internal
  sources: "STRATEGYZER,NNG,DESIGN-COUNCIL"
  platforms: "any"
  last-reviewed: "2026-11-17"
---

# Product strategy

A strategy is a set of choices about where to play and how to win, coherent enough that it also
says what the team will not do.

## When to use

- Writing a yearly or multi-year product strategy, or a strategy for a new product line.
- Reviewing a strategy document that reads like a list of goals or features.
- Aligning a roadmap with company goals.

## Inputs

- Company goals and constraints (financial targets, regulation, brand, capabilities).
- Market and customer evidence: research, segment data, competitor landscape.
- Current product performance and known problems.
- Existing strategy or roadmap if reviewing.

## Workflow

1. **Diagnose.** Describe the situation and the critical challenge in a few sentences, backed by
   evidence labels. A goal is not a diagnosis.
2. **Choose the target.** Segment(s) and their main job (see `jobs-to-be-done`), and who is
   explicitly out of scope.
3. **Define the value proposition** with the Value Proposition Canvas and state the
   differentiator against the real alternatives customers use today (including doing nothing).
4. **Set the guiding policy:** two to four principles that resolve trade-offs
   ("we favour trust over speed when they conflict").
5. **List coherent actions:** the few initiatives that apply the policy, with what each one
   requires from other teams. Check that they reinforce each other.
6. **Expose the bets.** For each action, the assumption that must hold and how it will be tested.
7. **Define success:** one outcome metric per bet plus guardrails (see `product-metrics`).
8. **Write the not-doing list** and the conditions that would trigger a strategy review.
9. **Stress-test** with a pre-mortem: "it is 18 months later and the strategy failed: why?"

## Outputs

A strategy document with: diagnosis, target and non-target, value proposition and positioning
statement, guiding policy, coherent actions, bets and assumptions table, success metrics and
guardrails, not-doing list, review triggers, pre-mortem risks. When reviewing, a findings table
(issue, why it matters, suggested rewrite).

## Edge cases

- **Strategy equals a feature list:** rebuild from diagnosis; keep features as candidate actions.
- **Too many priorities:** force-rank and move the tail to the not-doing list.
- **No market evidence:** label the diagnosis `[Assumption]` and add discovery as the first action.
- **Regulated products:** include regulatory change as a review trigger and compliance as a viability bet.

## Acceptance criteria

- [ ] The diagnosis names a challenge, not a goal.
- [ ] Target and explicitly excluded segments are stated.
- [ ] Each action links to the guiding policy and to a testable bet.
- [ ] A not-doing list exists.
- [ ] Success metrics include guardrails.
- [ ] Every factual claim has an evidence label.

## Sources

- Strategyzer Value Proposition Canvas and Business Model Canvas: https://www.strategyzer.com/
- Design Council, Systemic Design Framework: https://www.designcouncil.org.uk/
- Nielsen Norman Group, UX strategy articles: https://www.nngroup.com/
- Strategy kernel (diagnosis, guiding policy, coherent actions): R. Rumelt, *Good Strategy Bad Strategy* (2011), cited by name only.
