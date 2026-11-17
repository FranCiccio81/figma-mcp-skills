---
name: journey-mapping
description: >-
  Creates customer journey maps and service blueprints from evidence: stages, user
  actions, thoughts and emotions, touchpoints, frontstage and backstage processes,
  support systems, pain points and opportunities. Use when the user wants a journey
  map, an experience map, a service blueprint, an end-to-end view across channels, or
  to find where a service breaks between teams.
metadata:
  domain: ux
  version: "1.0.0"
  status: beta
  scope: universal
  trust: authored
  last-reviewed: "2026-11-17"
---

# Journey mapping and service blueprints

Two modes: **Journey map** (the customer's experience of a goal) and **Service blueprint** (how the organization delivers it, front and back stage).

## When to use

* Understanding an end-to-end experience across channels (app, web, branch, call center, email).
* Locating failures between teams or systems.
* Aligning stakeholders on a current state or designing a future state.

## Inputs

* Persona or segment and one scenario with a clear goal.
* Evidence: research, support logs, analytics, process documentation, staff interviews.
* Current state or future state (do not mix them in one map).

## Procedure

1. **Scope.** One actor, one scenario, start and end points.
2. **Stages** from the customer's perspective (for example: realize need, explore, sign up, first use, ongoing use, leave).
3. **Journey lanes:** actions, goals, thoughts (paraphrased evidence), emotional curve, touchpoints and channels, pain points, moments that matter.
4. **Blueprint lanes (blueprint mode):** frontstage actions (staff or interface), line of visibility, backstage actions, support processes and systems, line of internal interaction, policies, time and handoffs. Mark failure points and wait points.
5. **Evidence tagging.** Every cell is *Observed* (with source) or *Assumed*. Assumed cells are styled distinctly.
6. **Opportunities.** For each major pain, an opportunity statement (`opportunity-solution-tree`), owner and metric.

## Output

Map as a Markdown table (stages as columns, lanes as rows) or a Mermaid diagram, plus pain points and opportunities table, evidence legend, and list of assumptions to verify.

## Edge cases

* Several personas with different paths: one map each, or one map with explicit branches.
* No backstage knowledge: interview staff before drawing the blueprint; do not guess internal processes.
* Emotional curve without research: omit it rather than invent it.

## Acceptance criteria

* Single actor and scenario per map.
* Every cell labeled Observed or Assumed.
* Pain points link to evidence and to an opportunity with an owner.

## Sources

* This is Service Design Doing, journey maps and blueprints: https://www.thisisservicedesigndoing.com/
* Nielsen Norman Group, journey mapping and service blueprints: https://www.nngroup.com/
