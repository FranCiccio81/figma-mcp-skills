---
name: usability-testing
description: >-
  Plans, runs and reports usability tests of prototypes or live products: goals,
  realistic task scenarios, moderated or unmoderated setup, metrics (task success,
  errors, time, confidence), think-aloud facilitation, and a findings report with
  severity and evidence. Use when the user wants to test a design with users, write
  usability tasks or a test script, or analyze usability session results.
metadata:
  domain: ux
  version: "1.0.0"
  status: beta
  scope: universal
  trust: authored
  last-reviewed: "2026-11-17"
---

# Usability testing

## When to use

* Evaluating whether people can complete key tasks with a prototype or product.
* Comparing two design directions on task performance.

## Inputs

* Prototype or product, the tasks that matter most, target participants.
* Constraints: remote or in person, moderated or not, accessibility needs of participants.

## Procedure

1. **Goals.** What must be true for the design to ship? Turn these into measurable task goals.
2. **Tasks.** Realistic scenarios with a motivation and an end state, without UI words that give away the path ("You want to check whether you can afford to retire at 62" rather than "Click on Retirement planner").
3. **Setup.** Small rounds of five or so participants per distinct user group are usually enough to find major problems; iterate between rounds. Include participants who use assistive technologies when feasible.
4. **Script.** Introduction (we test the design, not you), consent, think-aloud practice, tasks, post-task question (ease rating), final questions. Pilot once.
5. **Facilitate neutrally.** Do not help, do not explain; answer questions with questions; note what people *do*, not only what they say.
6. **Measure.** Task success (complete, partial, fail), errors, time on task (secondary in think-aloud), post-task ease, observed confusion points.
7. **Analyze.** One row per issue: what happened, how many participants, which task, severity, likely cause (link to heuristic or principle), recommendation.

## Output

Test plan and script, or a findings report: summary, task success table, issues ranked by severity (0 cosmetic to 4 blocker) with participant counts and evidence, positive findings, recommendations, limitations of the study.

## Edge cases

* Prototype too low-fidelity for the task: test the concept or flow, not visual details.
* One participant hits a severe issue: report it with count 1/n; severity is about impact, frequency is reported separately.
* Quantitative claims (percentages) from five participants: avoid; report counts.

## Acceptance criteria

* Tasks contain no interface labels that reveal the path.
* Every issue reports frequency (k of n) and severity separately, with evidence.
* Limitations (sample, fidelity, setting) are stated.

## Sources

* Nielsen Norman Group, usability testing and severity ratings: https://www.nngroup.com/
* W3C WAI, involving users with disabilities: https://www.w3.org/WAI/
