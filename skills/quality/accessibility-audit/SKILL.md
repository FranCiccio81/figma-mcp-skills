---
name: accessibility-audit
description: >-
  Audits a design (Figma, screenshots) or an implementation (web, iOS, Android) against
  WCAG 2.2 level AA and platform accessibility guidance, and reports each finding with
  success criterion, evidence, severity, confidence, effort and fix. Use when the user
  asks for an accessibility or WCAG review, a contrast or target-size check, a
  screen-reader or keyboard review, or an accessibility conformance summary.
metadata:
  domain: quality
  version: "2.0.0"
  status: beta
  scope: universal
  trust: authored
  last-reviewed: "2026-11-17"
---

# Accessibility audit

## When to use

* Any request to check accessibility, WCAG conformance, contrast, keyboard, focus, screen reader, target size, motion, forms.
* Before release of a component, screen or flow; after a design system token change.
* Platform specifics: pair with `apple-accessibility` or `android-accessibility`. Cognitive load: pair with `cognitive-accessibility`.

## Inputs

* Scope: URL, build, component, Figma link or screenshots. State what was **not** available.
* Target: WCAG 2.2 AA by default. If the user cites a law or contract (European Accessibility Act, EN 301 549, Section 508, a national standard), ask which version applies; do not assert legal applicability yourself.
* Optional: assistive technologies and browsers to cover, user groups.

## Procedure

1. **Plan coverage.** List the WCAG 2.2 AA criteria relevant to the scope. A static design can only support a partial audit; say so.
2. **Automated checks (when code exists).** Run available tools (axe-core, Lighthouse, Accessibility Inspector on Apple, Accessibility Scanner on Android). Automated tools find only part of the issues; never report "compliant" from them alone.
3. **Visual checks.**
   * Contrast: text 4.5:1, large text (at least 24 px, or 18.66 px bold) 3:1 (1.4.3); UI components, focus indicators and meaningful graphics 3:1 (1.4.11). Compute ratios; 4.48:1 fails 4.5:1.
   * Target size: at least 24 × 24 CSS px or sufficient spacing (2.5.8, AA). Platform minimums are stricter: 44 × 44 pt on iOS, 48 × 48 dp on Android. 44 × 44 CSS px is AAA (2.5.5), useful as a goal, not an AA requirement.
   * Reflow at 320 CSS px (1.4.10), text spacing (1.4.12), resize text 200 % (1.4.4), color not sole carrier of meaning (1.4.1).
4. **Interaction checks.** Keyboard reachability and order (2.1.1, 2.4.3), visible focus (2.4.7) not obscured by sticky UI (2.4.11), no keyboard trap (2.1.2), dragging alternatives (2.5.7), pointer cancellation (2.5.2).
5. **Semantics.** Name, role, value (4.1.2); labels and instructions (3.3.2); error identification and suggestion (3.3.1, 3.3.3); status messages (4.1.3); headings and landmarks (1.3.1, 2.4.6).
6. **WCAG 2.2 additions.** Consistent help (3.2.6), redundant entry (3.3.7), accessible authentication without cognitive tests (3.3.8).
7. **Assistive technology pass.** VoiceOver, TalkBack, NVDA or JAWS on the critical path. Record what was actually tested.
8. **Rate each finding.** Severity: Critical (blocks a task), Serious, Moderate, Minor. Confidence: High (tested), Medium (inspected), Low (inferred from design). Effort: S, M, L.

## Output

1. Scope and method: what was tested, with which tools and AT, and what could not be tested.
2. Findings table: ID, criterion (number and name), location, evidence (measurement, screenshot reference, code line), severity, confidence, effort, fix.
3. Summary by severity and by criterion; no overall "compliant" claim unless every in-scope criterion was verified.
4. Retest checklist.

## Edge cases

* Design-only input: mark keyboard, screen-reader and focus findings as Low confidence or Not testable.
* Disabled controls are exempt from contrast (1.4.3) but must still be understandable.
* Brand colors that fail: propose the nearest compliant token, keep the brand intent, show both ratios.
* Conflicting guidance between WCAG and a platform: the stricter rule wins unless the project has a validated exception.

## Acceptance criteria

* Every finding cites a WCAG 2.2 criterion number or a named platform guideline.
* Every contrast finding includes both colors and the computed ratio.
* Severity, confidence and effort are present on every finding.
* Untested areas are listed; no blanket conformance claim.

## Sources

* WCAG 2.2: https://www.w3.org/TR/WCAG22/
* Understanding and techniques (W3C WAI): https://www.w3.org/WAI/standards-guidelines/wcag/
* ARIA Authoring Practices: https://www.w3.org/WAI/ARIA/apg/
* Apple accessibility: https://developer.apple.com/accessibility/
* Material accessibility: https://m3.material.io/
* Archived March 2026 guide (contains errata, see header): [references/legacy-guide.md](references/legacy-guide.md)
