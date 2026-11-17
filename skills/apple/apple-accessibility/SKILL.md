---
name: apple-accessibility
description: >-
  Designs, implements and tests accessibility on Apple platforms: VoiceOver labels,
  traits, grouping and focus order, Dynamic Type up to accessibility sizes, Voice
  Control, Switch Control, Full Keyboard Access, Reduce Motion and Transparency,
  Increase Contrast, and testing with Accessibility Inspector and UI test audits. Use
  when the user works on accessibility of an iOS, iPadOS, macOS, watchOS or visionOS
  app, asks about VoiceOver or Dynamic Type, or needs an Apple accessibility review.
metadata:
  domain: apple
  version: "1.0.0"
  status: beta
  scope: universal
  trust: official-derived
  last-reviewed: "2026-11-17"
---

# Apple accessibility

## When to use

* Any Apple-platform accessibility question, design review or implementation task.
* Pair with `accessibility-audit` for the WCAG mapping and with `swiftui-implementation` for code.

## Inputs

* Screens or code, deployment targets, the critical user tasks.

## Procedure

1. **VoiceOver model.** For each screen define: reading order, which elements are grouped (a card read as one element with combined label), what each element is called (label), what it does (traits such as button, header, selected), its current state (value), and optional hint. Labels are concise, not repeating the trait ("Delete", not "Delete button").
2. **Headings and rotor.** Mark section titles as headers so users can navigate by heading; add custom rotors for long, structured content when useful.
3. **Custom actions.** Swipe-only or long-press-only actions get accessibility actions; drag interactions get an alternative.
4. **Dynamic Type.** All text uses text styles; layouts reflow up to the largest accessibility sizes; truncation is avoided for essential content; icons that sit with text scale with it.
5. **Visual settings.** Respect Reduce Motion (replace large motion with fades), Reduce Transparency (solid backgrounds behind glass and blurs), Increase Contrast and Differentiate Without Color (do not rely on color alone), Bold Text, Smart Invert (do not invert images and media).
6. **Input alternatives.** Voice Control needs visible labels that match accessible names; Full Keyboard Access and Switch Control need every control reachable and a logical focus order; minimum target 44 × 44 pt.
7. **Announcements.** Post announcements for important changes that happen without focus moving (for example a transfer completed); do not over-announce.
8. **Test.** Accessibility Inspector audit; VoiceOver pass on device for the critical task; largest Dynamic Type; UI test accessibility audits where supported; record what was tested.

## Output

Per screen: VoiceOver specification table (element, label, trait, value, hint, grouping, order), settings behavior notes, and findings (issue, guideline or WCAG criterion, severity, fix) for reviews.

## Edge cases

* Charts and data visualizations: provide summaries and an accessible data representation (for example Audio Graphs or a table alternative).
* Financial amounts: ensure VoiceOver reads currency and sign correctly (use formatted values, not raw strings).
* Custom controls built from shapes: they have no accessibility by default; add element, label, traits and actions explicitly.

## Acceptance criteria

* The critical task is completable with VoiceOver alone, verified on a device.
* No text is clipped at the largest accessibility text size on the critical path.
* Reduce Motion and Reduce Transparency produce a usable, legible UI.
* Every interactive element has a label matching its visible text where there is one.

## Sources

* Apple accessibility for developers: https://developer.apple.com/accessibility/
* Human Interface Guidelines, accessibility: https://developer.apple.com/design/human-interface-guidelines/
* SwiftUI accessibility APIs: https://developer.apple.com/documentation/swiftui/
* WCAG 2.2: https://www.w3.org/TR/WCAG22/
