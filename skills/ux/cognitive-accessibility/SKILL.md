---
name: cognitive-accessibility
description: >-
  Reviews and designs for cognitive and learning accessibility: memory load, attention,
  language complexity, predictability, error tolerance, time limits and authentication,
  following W3C cognitive accessibility guidance and the related WCAG 2.2 criteria.
  Use when the user asks about cognitive load, plain language, users with dyslexia,
  ADHD, memory or learning disabilities, older users, or simplifying complex flows
  such as finance or health tasks.
metadata:
  domain: ux
  version: "1.0.0"
  status: beta
  scope: universal
  trust: authored
  last-reviewed: "2026-11-17"
---

# Cognitive accessibility

## When to use

* Complex or high-stakes flows (money, health, legal, identity).
* Reviewing whether a design depends on memory, fast reading or perfect attention.
* Complementing `accessibility-audit`, which focuses on WCAG conformance.

## Inputs

* Flow or screens, target users, and the content (actual copy, not lorem ipsum).

## Procedure

1. **Purpose and structure.** Is the purpose of each page clear in the first lines? One main task per screen; clear headings; consistent layout and navigation across pages.
2. **Memory.** Users should not need to remember information from a previous step; show it again. Avoid codes users must copy; support paste and password managers. Authentication must not rely on a cognitive function test unless an alternative exists (WCAG 2.2, 3.3.8).
3. **Language.** Plain language, defined terms, examples, no double negatives, numbers presented with context ("CHF 1,200 per month, about the same as now").
4. **Attention and distraction.** No auto-playing content or moving elements without control; pause, stop, hide (2.2.2); limit interruptions.
5. **Errors.** Prevent them (constraints, confirmations on consequential actions), explain them, make undo easy; do not erase input.
6. **Time.** No time limits, or adjustable or extendable ones (2.2.1); save progress.
7. **Help.** Consistent location for help (3.2.6); human contact for high-stakes tasks.
8. **Validate** with participants who have cognitive disabilities when possible; expert review alone is limited.

## Output

Findings table (location, pattern from W3C cognitive guidance or WCAG criterion, issue, impact on users, severity, recommendation), plus rewritten copy samples where language is the issue.

## Edge cases

* Required complexity (legal disclosures, risk warnings): layer the information (summary first, details available), never remove required content.
* Security requirements versus memory load: prefer passkeys, password managers and copy-paste over memorized codes.

## Acceptance criteria

* Each finding references a W3C cognitive accessibility pattern or WCAG criterion.
* No recommendation removes legally required information.
* Rewritten copy keeps the original meaning (checked by the content owner).

## Sources

* W3C WAI, cognitive accessibility guidance (Making Content Usable): https://www.w3.org/WAI/
* WCAG 2.2: https://www.w3.org/TR/WCAG22/
* Nielsen Norman Group: https://www.nngroup.com/
