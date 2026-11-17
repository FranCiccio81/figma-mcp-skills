---
name: apple-accessibility
description: >-
  Audits and implements accessibility on Apple platforms: VoiceOver labels, traits, grouping, rotor
  and custom actions; Dynamic Type including accessibility sizes; Reduce Motion, Reduce
  Transparency, Increase Contrast, Bold Text, Smart Invert; Voice Control and Switch Control; hit
  targets; color contrast; testing with Accessibility Inspector and real assistive technology. Use
  when asked to make an iOS, iPadOS, macOS, watchOS or visionOS app accessible, review VoiceOver
  behaviour, support Dynamic Type or prepare Accessibility Nutrition Labels. Do not use for web
  WCAG audits (use accessibility-audit).
license: MIT
metadata:
  version: "1.0.0"
  domain: apple
  status: beta
  trust: official-derived
  sources: "APPLE-ACCESSIBILITY,APPLE-HIG,APPLE-SWIFTUI,W3C-WCAG22"
  platforms: "ios,ipados,macos,watchos,visionos"
  last-reviewed: "2026-11-17"
---

# Apple accessibility

Respect the settings people chose. An app that ignores Dynamic Type or Reduce Motion overrides a
decision the user already made.

## When to use

- Building or reviewing any screen for Apple platforms.
- Before release, as an accessibility gate.
- Answering App Store Accessibility Nutrition Label questions.

## Inputs

- Code (SwiftUI or UIKit), build or designs.
- Target platforms and OS versions.
- Project accessibility requirements (for example WCAG 2.2 AA mapped to native apps).

## Workflow

1. **VoiceOver semantics:** every meaningful element has a concise label (no role words such as
   "button"), correct traits, values for adjustable controls, hints only when needed. Group
   related content (`accessibilityElement(children: .combine)`), hide decorative images, order
   elements logically, mark headings for rotor navigation, expose custom actions instead of
   hidden gestures.
2. **Dynamic Type:** test every screen at the largest accessibility size; text must not be
   truncated or overlap; layouts switch from horizontal to vertical when needed; icons and
   spacing that accompany text scale too.
3. **Motion and visual settings:** honour Reduce Motion (replace large or parallax motion with
   fades), Reduce Transparency (opaque fallbacks for materials and Liquid Glass), Increase
   Contrast (high contrast color variants), Bold Text, Smart Invert (exclude photos and media),
   Differentiate Without Color.
4. **Targets and input:** hit targets per the HIG table (44 × 44 pt default on iOS); Voice
   Control works when visible text matches accessibility labels; Switch Control and Full Keyboard
   Access can reach every action.
5. **Contrast:** text up to 17 pt needs 4.5:1, larger or bold text 3:1; provide higher contrast
   variants under Increase Contrast.
6. **Media and time:** captions and audio descriptions for video, no time limits without
   extension, no flashing content.
7. **Test:** Accessibility Inspector audit, then manual VoiceOver walkthrough of each critical
   flow, largest text size, and the motion and contrast settings; include people who use
   assistive technology when possible.
8. **Report** each issue with platform, screen, setting, steps to reproduce, impact, severity,
   fix (with API) and mapping to WCAG 2.2 where the project requires it.

## Outputs

An accessibility report (findings table, test matrix of settings × screens, pass or fail) and,
when implementing, code changes with a summary of the APIs used.

## Edge cases

- **Custom controls:** must expose traits, value and adjustable actions like the system control they replace.
- **Charts:** provide audio graphs or an accessible summary and data table.
- **Liquid Glass over busy content:** verify legibility with Reduce Transparency and Increase Contrast.
- **Financial amounts:** make VoiceOver read currency and sign correctly ("minus 200 Swiss francs").

## Acceptance criteria

- [ ] Every interactive element has a label, trait and, where relevant, a value.
- [ ] No truncation or overlap at the largest accessibility text size.
- [ ] Reduce Motion, Reduce Transparency and Increase Contrast are honoured.
- [ ] Hit targets meet the HIG platform size.
- [ ] Critical flows are tested manually with VoiceOver, with results recorded.

## Sources

- Apple accessibility for developers: https://developer.apple.com/accessibility/
- Apple Human Interface Guidelines, Accessibility: https://developer.apple.com/design/human-interface-guidelines/
- SwiftUI accessibility modifiers: https://developer.apple.com/documentation/swiftui/
- W3C WCAG 2.2: https://www.w3.org/WAI/standards-guidelines/wcag/
