---
name: android-accessibility
description: >-
  Audits and implements accessibility on Android: TalkBack labels, roles, states, headings,
  traversal order and custom actions in Compose and Views; font scaling up to 200 %; 48 dp touch
  targets; color contrast and non-color cues; Switch Access and keyboard; testing with Accessibility
  Scanner, TalkBack and automated checks. Use when asked to make an Android app accessible, review
  TalkBack behaviour, fix font scaling or prepare an Android accessibility test plan. Do not use for
  web WCAG audits (use accessibility-audit) or Apple platforms (use apple-accessibility).
license: MIT
metadata:
  version: "1.0.0"
  domain: android
  status: beta
  trust: official-derived
  sources: "ANDROID-DESIGN,ANDROID-COMPOSE,M3,W3C-WCAG22"
  platforms: "android"
  last-reviewed: "2026-11-17"
---

# Android accessibility

TalkBack users navigate by semantics, not by pixels. If the semantics tree is wrong, the screen is wrong.

## When to use

- Building or reviewing Android screens.
- Release accessibility gate.
- Fixing issues reported by Accessibility Scanner or Play Console pre-launch reports.

## Inputs

- Compose or View code, a build, or designs.
- Min and target SDK, form factors.
- Project accessibility requirements (for example WCAG 2.2 AA mapped to native).

## Workflow

1. **Semantics tree:** meaningful images and icons have `contentDescription`; decorative ones
   have `null`; list rows merge descendants so TalkBack reads one coherent item; custom controls
   declare `Role`, `stateDescription` and toggleable or selectable semantics; section titles use
   `heading()`.
2. **Traversal order:** follows reading order; fix with `traversalIndex` or `isTraversalGroup`
   only when layout order cannot express it.
3. **Actions:** gestures (swipe to dismiss, long press) also exposed as `customActions` or visible controls.
4. **Font scaling:** text in `sp`, layouts tested at 200 % (nonlinear scaling from Android 14);
   no fixed heights that clip text; single-line labels allowed to wrap.
5. **Touch targets:** at least 48 × 48 dp (`minimumInteractiveComponentSize()` or Material
   components); adequate spacing between targets.
6. **Color and contrast:** 4.5:1 for text, 3:1 for large text and UI components; never color
   alone for state (gains and losses need a sign or icon).
7. **Other inputs:** Switch Access and keyboard can reach every action; focus is visible on
   keyboard and D-pad.
8. **Test:** Accessibility Scanner on each screen, manual TalkBack pass on critical flows,
   automated checks (Compose semantics assertions, Espresso `AccessibilityChecks` where used),
   font scale 200 % and display size largest.
9. **Report** issues with screen, steps, impact, severity, fix (with API) and WCAG mapping where required.

## Outputs

Findings table and test matrix (screens × TalkBack, font 200 %, Switch Access, keyboard), plus
code fixes when implementing.

## Edge cases

- **Clickable `Row` without role:** add `Role.Button` or use a Material component.
- **Charts and sparklines:** provide a text summary.
- **WebView content:** follows web WCAG rules; audit with `accessibility-audit`.
- **Live updates (prices):** avoid announcing every tick; use polite live regions for meaningful changes only.

## Acceptance criteria

- [ ] Every interactive element has a role, label and state where relevant.
- [ ] Lists merge semantics into meaningful items.
- [ ] Screens remain usable at 200 % font scale.
- [ ] Touch targets are at least 48 × 48 dp.
- [ ] No information is conveyed by color alone.
- [ ] Critical flows pass a manual TalkBack test, with results recorded.

## Sources

- Android accessibility design guidance: https://developer.android.com/design/ui/mobile
- Compose accessibility and semantics: https://developer.android.com/develop/ui/compose
- Material Design 3 accessibility: https://m3.material.io/
- W3C WCAG 2.2: https://www.w3.org/WAI/standards-guidelines/wcag/
