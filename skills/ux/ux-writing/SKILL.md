---
name: ux-writing
description: >-
  Writes and reviews interface copy: buttons, labels, helper text, error messages,
  empty states, confirmations, notifications and onboarding, following a voice and
  tone, plain-language and localization rules. Use when the user asks for microcopy,
  error message wording, button labels, a content review of screens, or a UX writing
  style guide.
metadata:
  domain: ux
  version: "1.0.0"
  status: beta
  scope: universal
  trust: authored
  last-reviewed: "2026-11-17"
---

# UX writing

## When to use

* Writing or reviewing copy for a screen, component or flow.
* Building a content style guide or glossary.

## Inputs

* Screen or component context, user goal, state (default, error, empty, success).
* Product voice and terminology glossary, if they exist (read them first).
* Languages and markets.

## Procedure

1. **Purpose first.** What must the user understand or do after reading? Write that, then cut.
2. **Be specific and actionable.** Buttons say what happens ("Save changes", "Transfer CHF 500"), not "OK" or "Submit". Keep the verb consistent between the button and the resulting confirmation.
3. **Errors:** what happened, why if useful, how to fix, in plain words, near the field. No blame, no codes alone, no humor in errors that cost users money or data.
4. **Empty states:** what this area is for and the first action to take.
5. **Plain language:** common words, short sentences, active voice, one idea per sentence, front-load the key word. Explain unavoidable domain terms (financial, legal) at the point of use (`cognitive-accessibility`).
6. **Consistency:** same term for the same concept everywhere; maintain the glossary.
7. **Accessibility:** labels make sense out of context (screen readers list links and buttons), no "click here", no meaning carried by color or icon only, accessible names match visible labels.
8. **Localization:** allow text expansion (often 30 % or more), avoid concatenated strings, idioms and text in images; use the locale's number, currency and date formats.

## Output

Copy table (element, state, copy, character count, notes), alternatives when tone is uncertain, glossary additions, and for reviews a findings list (location, issue, rule, suggested copy).

## Edge cases

* Legal or regulatory text: keep required wording; add a plain-language summary next to it rather than rewriting it, after legal approval.
* Character limits from the design: give a short and a long variant.
* Brand voice conflicts with clarity: clarity wins in errors, security and money movements.

## Acceptance criteria

* Every action label names its outcome.
* Every error explains how to recover.
* Terminology matches the glossary; new terms are added to it.
* Strings are localization-ready (no concatenation, room for expansion).

## Sources

* Nielsen Norman Group, writing for interfaces: https://www.nngroup.com/
* WCAG 2.2 (labels, error identification, link purpose): https://www.w3.org/TR/WCAG22/
* U.S. Web Design System, content guidance: https://designsystem.digital.gov/
