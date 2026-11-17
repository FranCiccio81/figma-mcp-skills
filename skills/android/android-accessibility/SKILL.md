---
name: android-accessibility
description: >-
  Designs, implements and tests accessibility for Android apps built with Compose or
  Views: TalkBack semantics (labels, roles, states, headings, grouping, custom
  actions), focus order, font scaling up to 200 %, touch targets, color and contrast,
  Switch Access and keyboard, and testing with Accessibility Scanner and automated
  checks. Use when the user works on Android accessibility, TalkBack behavior, font
  scaling issues, or needs an Android accessibility review.
metadata:
  domain: android
  version: "1.0.0"
  status: beta
  scope: universal
  trust: official-derived
  last-reviewed: "2026-11-17"
---

# Android accessibility

## When to use

* Any Android accessibility design, implementation or review task.
* Pair with `accessibility-audit` for WCAG mapping and `material3-compose` for UI code.

## Inputs

* Screens or code, `minSdk` and `targetSdk`, critical user tasks.

## Procedure

1. **TalkBack model per screen:** reading order, grouping, label, role, state for each element.
   * Compose: `contentDescription` for meaningful images and icon buttons (null for decorative), `Modifier.semantics { heading() }` for section titles, `mergeDescendants = true` to read a card as one item, `stateDescription` for custom states, `Role` for custom clickable elements, `customActions` for swipe or long-press actions.
   * Views: `contentDescription`, `importantForAccessibility`, `accessibilityHeading`, `labelFor`.
2. **Labels** are short, describe purpose, and do not include the role ("Search", not "Search button").
3. **Live updates.** Use live regions or announcements sparingly for important asynchronous changes.
4. **Font scaling.** Text in `sp`; layouts reflow at 200 % (supported since Android 14 with nonlinear scaling); no fixed heights around text; essential text not truncated.
5. **Touch targets** at least 48 × 48 dp (Material components handle it; custom ones need `minimumInteractiveComponentSize()` or equivalent padding).
6. **Color and contrast:** WCAG contrast for text and UI elements in light and dark themes, including with dynamic color; never color alone.
7. **Focus and input:** logical traversal order, visible focus, full keyboard and Switch Access operation, no traps; dialogs move focus in and return it on close.
8. **Test.** Accessibility Scanner on the critical screens; TalkBack walk-through of the critical task on a device; automated accessibility checks in UI tests where the project's test stack supports them; record what was tested.

## Output

TalkBack specification table (element, label, role, state, grouping, order), findings (issue, guideline or WCAG criterion, severity, fix), and test record.

## Edge cases

* Custom canvas drawings and charts: expose semantics nodes or a text alternative.
* Merged semantics hiding interactive children: keep interactive children separately focusable.
* Amounts and dates: provide spoken-friendly descriptions when the visual format is ambiguous.

## Acceptance criteria

* The critical task is completable with TalkBack alone, verified on a device.
* Layout remains usable at 200 % font scale.
* All interactive elements are at least 48 dp and have labels.
* Accessibility Scanner reports no unresolved high-impact issues on critical screens.

## Sources

* Android accessibility (Compose and Views): https://developer.android.com/develop/ui/compose
* Material Design 3 accessibility: https://m3.material.io/
* Android design guidance: https://developer.android.com/design/ui/mobile
* WCAG 2.2: https://www.w3.org/TR/WCAG22/
