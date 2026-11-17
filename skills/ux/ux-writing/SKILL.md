---
name: ux-writing
description: >-
  Writes and reviews interface copy: buttons, labels, errors, empty states, confirmations,
  notifications, onboarding and legal-adjacent microcopy, with plain language, cognitive
  accessibility, voice and tone, inclusive wording and localization constraints. Use when asked to
  write or improve UI text, error messages, microcopy, a content style guide, or to check copy for
  clarity and accessibility. Do not use for marketing campaigns or long-form content.
license: MIT
metadata:
  version: "1.0.0"
  domain: ux
  status: beta
  trust: internal
  sources: "NNG,W3C-WAI,W3C-WCAG22"
  platforms: "any"
  last-reviewed: "2026-11-17"
---

# UX writing and cognitive accessibility

Interface text is interface. It should be specific, short, and understandable on a bad day.

## When to use

- Writing copy for a new flow or component.
- Reviewing copy for clarity, consistency, tone or accessibility.
- Creating or extending a content style guide.

## Inputs

- The screen or flow (Figma link, screenshots or a list of strings with keys).
- Audience, context of use, brand voice and existing style guide.
- Languages and character limits; legal or regulatory text that cannot change.

## Workflow

1. **Understand the moment:** what the user is trying to do and what they know at that point.
2. **Write for the action:** buttons start with a verb and say what happens ("Send 200 CHF", not
   "OK"); keep the same verb from entry point to confirmation.
3. **Errors:** say what happened, why if useful, and how to fix it, next to the field; never blame
   the user; keep their input. Meet WCAG 2.2 SC 3.3.1 (error identification) and 3.3.3 (error suggestion).
4. **Empty, loading and success states:** explain what will appear and the next step.
5. **Plain language and cognitive accessibility** (W3C COGA guidance *Making Content Usable for
   People with Cognitive and Learning Disabilities*): short sentences, common words, one idea per
   sentence, explain unavoidable jargon, avoid double negatives, give clear steps, do not rely on
   memory between screens.
6. **Tone:** adapt to the emotional moment (calm for errors involving money, neutral for legal).
7. **Inclusive wording:** gender-neutral where the language allows, no idioms that do not translate,
   no ableist metaphors.
8. **Localization:** leave room for text expansion (French and German strings are often
   noticeably longer than English), avoid concatenated strings, use placeholders with context
   notes, plural rules, locale formats for dates, numbers and currency.
9. **Check against the style guide** and record new terms in a glossary.

## Outputs

A copy table: key, location, current text, proposed text, rationale, character count, notes for
translators. For a review: issues table with severity and suggested rewrite. Optionally, glossary
updates.

## Edge cases

- **Legally mandated text:** do not rewrite meaning; propose a plain-language summary next to it and flag for legal review.
- **Character limits too tight:** propose a shorter alternative and the layout change needed.
- **Brand voice conflicts with clarity:** clarity wins in errors and transactional moments.
- **Screen reader context:** visible labels and accessible names should match (WCAG 2.5.3 Label in Name).

## Acceptance criteria

- [ ] Every button label starts with a verb or is a standard platform label.
- [ ] Every error states the problem and the way to fix it.
- [ ] Sentences are short and free of unexplained jargon.
- [ ] Strings avoid concatenation and include translator notes where ambiguous.
- [ ] Legal text meaning is untouched and flagged for review when edited.

## Sources

- Nielsen Norman Group, UX writing and error messages: https://www.nngroup.com/
- W3C WAI Cognitive Accessibility (COGA), *Making Content Usable*: https://www.w3.org/WAI/
- W3C WCAG 2.2 (3.3.1, 3.3.3, 2.5.3): https://www.w3.org/WAI/standards-guidelines/wcag/
