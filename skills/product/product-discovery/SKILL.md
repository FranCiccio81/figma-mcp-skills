---
name: product-discovery
description: >-
  Runs a structured product discovery cycle: frames a desired outcome, maps user opportunities in an
  opportunity solution tree, surfaces the riskiest assumptions and plans the smallest tests that would
  reduce them. Use when a team must decide what to build next, when a feature request arrives without
  a validated problem, or when someone asks for an opportunity solution tree, assumption map or
  discovery plan. Do not use to write a delivery-ready spec (use product-requirements) or to size an
  A/B test (use experiment-design).
license: MIT
metadata:
  version: "1.0.0"
  domain: product
  status: beta
  trust: internal
  sources: "NNG,DESIGN-COUNCIL,STRATEGYZER"
  platforms: "any"
  last-reviewed: "2026-11-17"
---

# Product discovery

Discovery reduces the risk of building the wrong thing. The output is a decision about what to learn
next, never a fabricated certainty.

## When to use

- A stakeholder brings a solution ("we need a dashboard") and the underlying problem is unclear.
- A team has an outcome to move (activation, retention, cost to serve) and no shared view of options.
- Before committing a quarter of engineering effort to an idea.

Do not use when the problem and solution are already validated and the team needs a build plan.

## Inputs

- The business or product outcome, ideally measurable, and its owner.
- Existing evidence: research reports, interview notes, support tickets, analytics extracts.
- Constraints: regulation, platform, deadlines, team capacity.
- Optional: candidate solutions already on the table.

If no evidence is provided, say so explicitly and switch to producing a research plan
(see `research-planning`). Never invent quotes, personas or numbers.

## Workflow

1. **Frame the outcome.** Rewrite the goal as one measurable outcome with a time frame. Reject
   output goals ("ship X") and propose the outcome they serve.
2. **Inventory evidence.** List every input and tag each statement with an evidence label
   (`[Observed]`, `[Validated]`, `[Assumption]`, `[Recommendation]`). Note sample size and recency.
3. **Map opportunities.** Express user needs, pains and desires as opportunities phrased from the
   user's point of view. Group them into a tree under the outcome (Opportunity Solution Tree,
   T. Torres). Keep solutions out of this level.
4. **Pick a target opportunity.** Compare opportunities on reach, severity, strategic fit and
   evidence strength. State why the chosen one wins and what was left out.
5. **Generate at least three solutions** for the target opportunity, including one that is not
   software (process, content, policy).
6. **Surface assumptions** behind each solution across four risks: desirability, usability,
   feasibility and viability (including legal and compliance). Use
   [the assumption map](references/assumption-map.md) to rank them by importance and evidence.
7. **Design the smallest tests** for the two or three riskiest assumptions: method, participants or
   data source, success threshold decided before the test, cost, duration.
8. **Write the discovery brief** using the output structure below.

## Outputs

A Markdown discovery brief with:

1. Outcome statement and owner.
2. Evidence inventory table (statement, label, source, date, sample).
3. Opportunity solution tree as a Mermaid `graph TD` block.
4. Target opportunity and the reasoning.
5. Solution options with their assumptions.
6. Assumption map (risk type, importance, evidence strength).
7. Test plan for the riskiest assumptions with pre-registered success thresholds.
8. Open questions and decisions needed, with owners.

## Edge cases

- **Solution-first request:** keep the solution as one branch of the tree, list the opportunity it
  presumes and test that opportunity first.
- **Contradictory evidence:** show both sides, weigh by method quality and recency, do not average.
- **Regulated domain (finance, health):** add compliance as a viability risk and flag who must
  sign off. Discovery tests involving real customer data need a privacy review first.
- **Only quantitative data:** analytics shows what happens, not why; add a qualitative step.

## Acceptance criteria

- [ ] The outcome is measurable and distinct from any output.
- [ ] Every claim carries an evidence label and a source, and no data point is invented.
- [ ] The tree separates opportunities from solutions.
- [ ] At least three solutions exist for the target opportunity.
- [ ] Each test has a success threshold written before it runs.
- [ ] The brief names what the team will stop doing or not test, and why.

## Sources

- Nielsen Norman Group, research methods and discovery articles: https://www.nngroup.com/
- Design Council, Double Diamond and Systemic Design Framework: https://www.designcouncil.org.uk/
- Strategyzer, testing business ideas and assumption mapping: https://www.strategyzer.com/
- Opportunity Solution Tree: Teresa Torres, *Continuous Discovery Habits* (2021), cited by name only.
