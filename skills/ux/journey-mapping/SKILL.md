---
name: journey-mapping
description: >-
  Builds evidence-based customer journey maps and service blueprints: stages, user actions, goals,
  touchpoints, emotions only when observed, pain points, frontstage and backstage actions, support
  processes and the lines of interaction, visibility and internal interaction, then derives
  opportunities. Use when asked for a journey map, experience map, service blueprint, current-state
  or future-state map, or to find where a cross-channel service breaks. Do not use for screen-level
  flows of a single feature (use interaction-design-spec).
license: MIT
metadata:
  version: "1.0.0"
  domain: ux
  status: beta
  trust: internal
  sources: "TISDD,NNG,DESIGN-COUNCIL"
  platforms: "any"
  last-reviewed: "2026-11-17"
---

# Journey mapping and service blueprinting

A journey map shows the experience; a service blueprint shows what the organisation does to
produce it. Both are only as good as the evidence in their cells.

## When to use

- Aligning teams on a cross-channel experience (app, branch, call center, email, letter).
- Locating the root cause of a pain point in operations rather than in the UI.
- Designing a future-state service.

## Inputs

- Scope: persona or segment, scenario, start and end points, current or future state.
- Evidence: interviews, observation, analytics, support tickets, process documentation, staff input.
- Channels and systems involved.

## Workflow

1. **Set the scope** in one sentence: who, which scenario, from which trigger to which end.
2. **Define stages** from the user's perspective (for example: realise need, compare, sign up,
   first use, ongoing use, leave), not the organisation's departments.
3. **Fill the journey layers** per stage: user goal, actions, touchpoints and channel, thoughts
   (verbatim only, attributed), emotional curve only when observed, pain points.
4. **Add the blueprint layers** for service work: frontstage staff and system actions, backstage
   actions, support processes and systems, policies. Draw the line of interaction, line of
   visibility and line of internal interaction.
5. **Tag every cell** with an evidence label and source; leave cells empty rather than guessing.
6. **Mark moments that matter** and failure points (where the service often breaks, with evidence).
7. **Derive opportunities** phrased as "How might we..." with the stage, evidence and the layer
   where the root cause sits.
8. **For a future state,** show the changes per layer and what each requires (people, process, system).

## Outputs

- A table-based map in Markdown (stages as columns, layers as rows) and, where helpful, a
  Mermaid `journey` or `flowchart` diagram.
- Evidence legend and source list.
- Pain points and failure points ranked by severity and frequency.
- Opportunities with owners to investigate.

## Edge cases

- **No research:** produce an assumption map labelled `[Assumption]` and a plan to validate it with
  `research-planning`; mark it clearly as a hypothesis map.
- **Several personas with different paths:** one map per scenario, not one blended map.
- **Emotions requested without data:** omit the emotion curve and explain why.
- **Sensitive operations data:** summarise processes, do not paste internal system names into public docs.

## Acceptance criteria

- [ ] Scope, trigger and end point are explicit.
- [ ] Stages follow the user's perspective.
- [ ] Every filled cell has an evidence label; unknown cells are left empty or marked.
- [ ] Blueprints show the lines of interaction, visibility and internal interaction.
- [ ] Opportunities point to the layer where the root cause sits.

## Sources

- This Is Service Design Doing, journey maps and service blueprints: https://www.thisisservicedesigndoing.com/
- Nielsen Norman Group, journey mapping and service blueprinting: https://www.nngroup.com/
- Design Council, service design methods: https://www.designcouncil.org.uk/
