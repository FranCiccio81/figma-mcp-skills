---
name: ux-research-planning
description: >-
  Plans user research that answers a real decision: research questions, method
  choice, participant criteria and screener, consent and privacy, interview or
  discussion guide with neutral questions, and synthesis approach. Use when the user
  needs a research plan, an interview guide, a screener, help choosing between
  research methods, or a synthesis of interview notes into findings.
metadata:
  domain: ux
  version: "1.0.0"
  status: beta
  scope: universal
  trust: authored
  last-reviewed: "2026-11-17"
---

# UX research planning

## When to use

* "Plan research for X", "write an interview guide", "who should we recruit", "synthesize these notes".
* Not for: usability test scripts (use `usability-testing`), switch interviews specifically (use `jobs-to-be-done`).

## Inputs

* The decision the research informs, deadline, budget, access to participants.
* What is already known (prior studies, analytics, support data).

## Procedure

1. **Decision and questions.** State the decision; derive three to five research questions. Research questions are what *we* need to learn, not questions to ask participants.
2. **Method choice.** Attitudinal vs behavioral, qualitative vs quantitative, generative vs evaluative. Interviews and field studies for understanding context; diary studies for behavior over time; surveys to size what qualitative work found; analytics for what happens at scale.
3. **Participants.** Behavioral criteria, exclusions, quotas, and a screener whose questions do not reveal the "right" answer. For qualitative studies, plan small rounds and stop when new sessions add little.
4. **Ethics and privacy.** Informed consent, recording permission, data minimization, storage and deletion, incentives. Extra care with vulnerable participants and sensitive topics (finance, health).
5. **Interview guide.** Warm-up, context, past-behavior questions ("tell me about the last time…"), probes ("what happened next?", "why was that important?"), wrap-up. Avoid leading, double-barreled and hypothetical questions. Pilot the guide once.
6. **Synthesis plan.** Notes per session, affinity clustering, findings stated as *observation → interpretation → implication*, each with the number of participants supporting it.

## Output

Research plan: decision, research questions, method and rationale, participant criteria and screener, logistics, consent and data handling, interview guide, synthesis approach, timeline. For synthesis requests: findings table (finding, evidence count, confidence, implication) plus open questions.

## Edge cases

* Stakeholders want validation of a chosen solution: reframe toward learning; include questions that could disconfirm it.
* No access to real users: say so; proxies (support, sales) produce hypotheses, not findings.
* Recruiting internal staff as participants: label results as biased.

## Acceptance criteria

* Each guide question maps to a research question.
* No leading or hypothetical questions remain in the guide.
* Consent and data-retention steps are present.
* Findings separate observation, interpretation and recommendation, with participant counts.

## Sources

* Nielsen Norman Group, research methods and interviewing: https://www.nngroup.com/
* This is Service Design Doing, methods: https://www.thisisservicedesigndoing.com/
