---
name: bridge-accessibility
description: >-
  Applies the Bridge 2.0 accessibility rules to Swissquote and PostFinance screens on
  web, iOS and Android: WCAG 2.2 AA floor and AAA targets for trade confirmation,
  authentication and fee disclosure, contrast of Bridge token pairs in light and dark,
  touch targets and focus ring tokens, text scaling limits, screen-reader patterns for
  financial rows, and known risky token pairings. Use when designing, building or
  reviewing a Bridge screen for accessibility, choosing token pairs for text or
  borders, or checking dark mode legibility.
metadata:
  domain: bridge
  version: "1.0.0"
  status: beta
  scope: project
  trust: project-specific
  last-reviewed: "2026-11-17"
---

# Bridge accessibility

Method and WCAG mapping: `accessibility-audit`. Platform specifics: `apple-accessibility`, `android-accessibility`. This skill adds Bridge facts. Tokens: `references/bridge-foundations.md`. Computed contrast for key token pairs: [references/contrast-matrix.md](references/contrast-matrix.md).

## When to use

* Designing, implementing or reviewing any Bridge screen; choosing text, icon and border tokens; checking dark mode.

## Inputs

* Screen or component, platform, themes in scope, whether the flow includes trade confirmation, authentication or fee disclosure (AAA targets).

## Procedure

1. **Targets.** WCAG 2.2 AA for everything. For trade confirmation, authentication and fee disclosure aim for AAA (for example 7:1 text contrast, 4.5:1 for large text).
2. **Contrast with Bridge tokens.** Use the matrix to pick pairs. Watch the known risky pairs (snapshot values, verify live):
   * `data/up` and `data/down` as small text on light surfaces are below 4.5:1 (about 3.8:1). Use them for icons, arrows, large figures or chart marks, and keep small text in neutral tokens with a sign, or confirm a darker text token with the Governance.
   * In SQ Dark, `border/default` and `border/strong` on `background/surface/default/base` are below 3:1 (about 1.8:1). Fields and controls that rely on the border alone fail 1.4.11.
   * In light, `border/default` on white is about 1.3:1: fine for decorative dividers, not for the only boundary of an input.
   * Brand and destructive primary backgrounds (`#fa5b35`, `#f95959` in SQ Light) reach about 3.2:1 against white. If the on-primary text is white, label text below large-text size fails 4.5:1: check the actual `on-primary-text` token value in Figma.
3. **Colour is never alone.** Up and down, buy and sell, status: always a sign, arrow, icon or word too.
4. **Targets and focus.** Mobile minimums from `05mobile`: 44 pt on iOS, 48 dp on Android, also for chips and icon buttons. Web: at least 24 × 24 CSS px (2.5.8), 44 on touch layouts. Focus ring: 2 px ring plus the `shadow/focus/default` spread (`border/focus`), 3:1 against its surroundings, never removed; focus not hidden by sticky headers or footers.
5. **Text scaling.** iOS Dynamic Type up to the largest accessibility size (Bridge scale cap 3.1); Android font scale up to 200 % (cap 2). Text wraps, rows grow, pairs stack; figures never truncate, labels may.
6. **Screen readers.** One element per financial row with a combined label ("Nestlé, 20 shares, CHF 1,690.00, up 0.8 percent"); icon-only buttons labelled; headings marked; toasts announced without moving focus; dialogs and sheets move focus in and back to the trigger.
7. **Motion and transparency.** Honour Reduce Motion and `prefers-reduced-motion`; Liquid Glass and blurs have the opaque fallback surface with Reduce Transparency.
8. **Authentication.** No cognitive test alone; allow paste and password managers.

## Output

Findings or a checklist per screen: token pairs checked with ratios (light and dark), target sizes, focus, scaling behaviour, screen-reader labels, and any token pair to escalate to the Governance.

## Edge cases

* Snapshot values differ from live Figma: recompute with live values; the matrix is a starting point.
* PF and Default themes: the brand ramp and neutrals change; recompute brand-dependent pairs for PF.
* Disabled controls are exempt from contrast requirements but must still be identifiable as disabled.

## Acceptance criteria

* Every text and essential border pair used on the screen has a ratio in light and dark.
* No small text in `data/up` or `data/down` on light surfaces without a confirmed passing token.
* Targets and focus ring follow the tokens; text scales to the platform cap without loss.

## Sources

* WCAG 2.2: https://www.w3.org/TR/WCAG22/
* Apple accessibility: https://developer.apple.com/accessibility/
* Material Design 3 accessibility: https://m3.material.io/
* WAI-ARIA Authoring Practices: https://www.w3.org/WAI/ARIA/apg/
