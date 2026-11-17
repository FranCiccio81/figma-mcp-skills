---
name: frontend-code-review
description: >-
  Reviews frontend pull requests with a consistent checklist and severity: correctness, design
  system and token compliance, accessibility, performance, security, tests, readability and
  maintainability, with actionable comments and a merge verdict. Use when asked to review a PR,
  diff or component code for a web or native UI, or to define a frontend review checklist. Do not
  use for writing new features from scratch.
license: MIT
metadata:
  version: "1.0.0"
  domain: engineering
  status: beta
  trust: internal
  sources: "W3C-WCAG22,OWASP,WEB-DEV,REACT-DOCS"
  platforms: "any"
  last-reviewed: "2026-11-17"
---

# Frontend code review

A review protects users and the next developer. Comment on what matters, explain why, and
propose a fix.

## When to use

- Reviewing a pull request or diff touching UI code.
- Self-review before opening a pull request.
- Agreeing on a team review checklist.

## Inputs

- The diff and its description, linked ticket or spec, designs.
- Project conventions (CLAUDE.md, lint rules, design system docs).

## Workflow

1. **Understand intent:** read the description and spec; if the change does not match them, say
   so first.
2. **Correctness:** logic, edge cases, error handling, race conditions, state updates, types.
3. **Design system compliance:** existing components reused, tokens instead of literal values,
   all states implemented, visual parity with designs (use `design-implementation-qa` when
   designs are available).
4. **Accessibility:** semantics, labels, keyboard and focus, contrast, motion preferences; deep
   checks via `accessibility-audit` or platform skills.
5. **Performance:** unnecessary renders, heavy dependencies, unoptimised images, blocking work.
6. **Security and privacy:** raw HTML, secrets, personal data in logs, unsafe redirects (see `frontend-security`).
7. **Tests:** behaviour covered at the right level, meaningful assertions, no flaky patterns.
8. **Readability:** naming, size of functions and components, comments that explain why, dead code.
9. **Write comments** with a severity label: `blocker` (must fix, user or security impact),
   `major` (should fix before merge), `minor` (fix soon), `nit` (optional), `question`.
   Each comment: what, why, suggestion.
10. **Verdict:** approve, approve with comments, or request changes, with the list of blockers.

## Outputs

A review summary (intent check, verdict, blockers), followed by comments grouped by file with
severity, rationale and suggested code.

## Edge cases

- **Huge PR:** ask to split, or review by risk area and state what was not reviewed.
- **Generated code (Figma MCP, AI):** review as strictly as human code; check for invented APIs and copied absolute layouts.
- **Style-only disagreements:** defer to linters and conventions; mark as `nit`.
- **Missing context:** ask questions instead of guessing intent.

## Acceptance criteria

- [ ] The review states the intent check and an explicit verdict.
- [ ] Every comment has a severity, a reason and a suggestion.
- [ ] Accessibility, tokens and tests are each checked or explicitly out of scope.
- [ ] Unreviewed areas are named.

## Sources

- W3C WCAG 2.2: https://www.w3.org/WAI/standards-guidelines/wcag/
- OWASP Cheat Sheet Series: https://cheatsheetseries.owasp.org/
- web.dev performance guidance: https://web.dev/
- React documentation: https://react.dev/
