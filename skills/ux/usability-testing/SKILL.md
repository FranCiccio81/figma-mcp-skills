---
name: usability-testing
description: >-
  Plans, runs and analyses usability tests (moderated or unmoderated, remote or in person):
  objectives, participant criteria, realistic task scenarios, script, consent, metrics (task
  success, time, errors, SEQ, SUS), observation grid, synthesis and a findings report with
  severity. Use when asked to prepare a usability test, write test tasks or a script, or analyse
  session notes and recordings. Do not use for broad generative research (use research-planning)
  or for expert-only review (use ux-heuristic-evaluation).
license: MIT
metadata:
  version: "1.0.0"
  domain: ux
  status: beta
  trust: internal
  sources: "NNG,W3C-WAI"
  platforms: "any"
  last-reviewed: "2026-11-17"
---

# Usability testing

Watch real people attempt real tasks. Report what they did, not what the team hoped.

## When to use

- Validating a prototype or a live flow before or after release.
- Comparing two design directions on the same tasks.
- Turning raw session notes into prioritised findings.

## Inputs

- What the team needs to learn and the decisions that depend on it.
- The artifact and its fidelity.
- Target participants, including people with disabilities when possible.
- For analysis: notes, transcripts or recordings, with participant IDs.

## Workflow

### Plan

1. **Objectives:** three to five learning goals linked to decisions.
2. **Participants:** criteria and screener; about five participants per distinct user group for
   formative qualitative tests; more (and a quantitative design) for benchmarking.
3. **Tasks:** realistic scenarios with a goal, not instructions ("You want to send 200 CHF to your
   landlord before Friday", not "Tap Transfer"). Define success criteria for each task in advance.
4. **Script:** introduction, consent, think-aloud explanation, warm-up, tasks, post-task question
   (SEQ, 1 to 7), closing questionnaire (SUS when comparing over time), debrief.
5. **Logistics and ethics:** consent form, recording permission, data storage and deletion date,
   incentive, accessibility of the test setup, a pilot session.

### Analyse

6. **Code observations** per task and participant: success (full, partial, fail), time, errors,
   quotes (verbatim only, with participant ID), and behaviour.
7. **Synthesise** into findings: issue, how many participants (counts), evidence, severity (use the
   0 to 4 scale from `ux-heuristic-evaluation`), recommendation.
8. **Report metrics honestly:** with small samples show counts and ranges, not percentages; SUS
   scores need a reference benchmark and a sufficient sample.

## Outputs

- Test plan: objectives, participants and screener, tasks with success criteria, script,
  logistics, consent and data handling.
- Findings report: summary, task success matrix, findings table with counts and quotes, severity,
  recommendations, what to test next, limitations.

## Edge cases

- **No sessions run yet:** produce the plan only; never simulate participants or results.
- **Leading task wording:** rewrite tasks that contain UI labels or hints.
- **Assistive technology users:** allow extra time, test on their own setup, let them use their
  own settings.
- **Sensitive domains (money, health):** use fictitious data in prototypes, never real accounts.

## Acceptance criteria

- [ ] Tasks are scenarios with pre-defined success criteria.
- [ ] Consent and data retention are addressed.
- [ ] Findings report counts out of N and verbatim quotes with participant IDs only.
- [ ] No result, quote or participant is fabricated.
- [ ] Limitations (sample, fidelity, recruiting) are stated.

## Sources

- Nielsen Norman Group, usability testing methods and metrics: https://www.nngroup.com/
- W3C WAI, involving users with disabilities: https://www.w3.org/WAI/
- SEQ (J. Sauro) and SUS (J. Brooke, 1996), cited by name only.
