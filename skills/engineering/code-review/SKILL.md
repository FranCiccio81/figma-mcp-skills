---
name: code-review
description: >-
  Reviews code changes (pull requests, diffs) for correctness, security, accessibility,
  design system compliance, tests, readability and maintainability, and writes
  actionable, prioritized comments distinguishing blocking issues from suggestions. Use
  when the user asks to review a PR, a diff or a file, or wants a second opinion on a
  change before merging.
metadata:
  domain: engineering
  version: "1.0.0"
  status: beta
  scope: universal
  trust: authored
  last-reviewed: "2026-11-17"
---

# Code review

## When to use

* Reviewing a pull request, diff, or set of files before merge.

## Inputs

* The diff and its description, linked requirements or issue, repository conventions (lint rules, contribution guide, design system rules).

## Procedure

1. **Understand intent.** Read the PR description and linked requirement; if missing, ask. Review against the intended behavior, not your preferred design.
2. **Run what you can.** Build, type check, lint, tests. Report what you ran and the result; do not claim something passes without running it.
3. **Review in priority order:**
   1. Correctness: logic, edge cases, error handling, concurrency, data loss.
   2. Security and privacy (`frontend-security`).
   3. Accessibility of UI changes (`accessibility-audit`).
   4. Tests: do they cover the change and fail without it?
   5. Design system compliance: tokens, existing components, no duplication.
   6. Readability and maintainability: naming, size of functions, dead code, comments explaining why.
   7. Performance where relevant and measurable.
4. **Write comments** with location, the problem, why it matters, and a concrete suggestion. Label each: *Blocking*, *Should fix*, *Suggestion*, *Question*, *Praise*.
5. **Scope discipline.** Note unrelated problems separately; do not request rewrites outside the change.
6. **Summarize:** verdict (approve, approve with suggestions, request changes), blocking items, and what was not reviewed.

## Output

Review summary plus a list of comments (file and line, label, comment, suggestion).

## Edge cases

* Very large PRs: review the riskiest parts first and recommend splitting.
* Generated code (including AI-generated): review with the same bar; verify APIs exist.
* Disagreement on style not covered by the project's rules: suggestion at most.

## Acceptance criteria

* Every blocking comment states the risk and a fix.
* The review states which checks were run and their results.
* Unreviewed areas are named.

## Sources

* Google Engineering Practices, code review guide: https://google.github.io/eng-practices/review/
* OWASP Cheat Sheet Series: https://cheatsheetseries.owasp.org/
