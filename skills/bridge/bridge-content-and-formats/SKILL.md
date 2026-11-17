---
name: bridge-content-and-formats
description: >-
  Applies the Bridge 2.0 voice and data format rules to Swissquote and PostFinance
  interfaces: friendly-expert tone, sentence case, button labels that name the action,
  error and confirmation copy, and the formats for amounts, large numbers, dates, times,
  IBAN and phone numbers, with localisation rules. Use when someone writes or reviews
  copy, labels or error messages for a Swissquote or PostFinance screen, formats
  amounts or dates in a design or in code, or prepares strings for translation.
metadata:
  domain: bridge
  version: "1.0.0"
  status: beta
  scope: project
  trust: project-specific
  last-reviewed: "2026-11-17"
---

# Bridge content and data formats

The rules come from `references/bridge-foundations.md` (section 9). Generic UX writing method: `ux-writing`.

## When to use

* Writing or reviewing copy, labels, errors, empty states, confirmations for Swissquote or PostFinance.
* Formatting amounts, numbers, dates, IBAN or phone numbers in Figma or in code.
* Preparing or reviewing strings for localisation.

## Inputs

* The screen and its states, the language(s), the platform (web or mobile: date and time conventions differ).

## Procedure

1. **Voice: friendly expert.** Concise, clear, positive without hype. Second person, present tense, active voice, sentence case. Sentences under 20 words. Labels make sense on their own.
2. **Actions.** The label says what happens: "Save changes", "Turn on notifications". Orders name the order: "Buy 20 NESN". The confirmation uses the same verb as the button. Cancelling is not destructive.
3. **Errors.** What happened and how to fix it, next to the field, without blame: "Your password is incorrect". Never an error code alone. Risk and regulatory messages are never transient.
4. **Amounts.** Currency code before the amount, two decimals, period as decimal separator in every language: `CHF 1,234.50`. Figures in tables use tabular numerals and align right.
5. **Large numbers.** Abbreviate per language: EN `1M`, `5B`; FR `1 M`, `5 Md`; DE `1 Mio.`, `5 Mrd.`.
6. **Dates and times.** Long form for key dates (expiry, dividend); short numeric form in tables and dense lists. Times in 24 h in tables (`08:00 - 12:15`), locale form in sentences. On mobile, follow the device locale.
7. **Identifiers.** IBAN in blocks of four, no padding on the last block: `CH93 0076 2011 6238 5295 7`. Phone: one field, automatic formatting, country selector, at least 8 characters.
8. **Localisation.** English first, then EN, FR, DE, IT and more. Leave 30 to 40 percent room for expansion. No concatenated strings, no text in images, placeholders named (`{amount}`), plural rules handled by the i18n library.
9. **Implementation note for developers.** Use one shared formatter per platform. Several locale defaults disagree with Bridge (decimal separator, currency position), so components never call locale formatting directly.

## Output

Copy table (element, state, EN copy, character count, notes for translators) or format examples, plus findings for reviews (location, rule, current, proposed).

## Edge cases

* Thousands separator outside English: the foundations show `1,234.50` for English and fix the decimal separator for every language, but do not state the thousands separator for FR, DE or IT. Flag it to the Design System Governance before implementing a choice.
* Negative amounts and changes: always show the sign (and an arrow or word) in addition to colour.
* Legal texts: keep the approved wording; add a plain-language summary only with legal approval.

## Acceptance criteria

* Every action label names its outcome; order labels name the order.
* Every error explains recovery.
* All amounts, dates, IBAN and phone examples follow the formats above.
* Strings are ready for translation (no concatenation, room for expansion).

## Sources

* WCAG 2.2 (labels, error identification): https://www.w3.org/TR/WCAG22/
* Nielsen Norman Group (writing for interfaces): https://www.nngroup.com/
* MDN, `Intl.NumberFormat` (for the shared formatter): https://developer.mozilla.org/
