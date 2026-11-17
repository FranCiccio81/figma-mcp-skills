---
name: apple-hig-review
description: >-
  Designs or reviews interfaces for Apple platforms (iOS, iPadOS, macOS, watchOS,
  visionOS) against the Human Interface Guidelines: navigation, system components,
  layout and adaptivity, typography and SF Symbols, materials including Liquid Glass,
  gestures and feedback, and platform-specific conventions. Use when the user designs
  an Apple app screen or flow, asks whether a design feels native, adapts an iPhone
  design to iPad, Mac, Watch or Vision Pro, or adopts the latest Apple design language.
metadata:
  domain: apple
  version: "1.0.0"
  status: beta
  scope: universal
  trust: official-derived
  last-reviewed: "2026-11-17"
---

# Apple HIG review

Design guidance, not code. For implementation use `swiftui-implementation`; for accessibility depth use `apple-accessibility`.

## When to use

* Designing or reviewing screens and flows for Apple platforms.
* Adapting a design between Apple platforms, or from Android or web to Apple.

## Inputs

* Screens, flows or Figma frames; target platforms and minimum OS versions (they decide which system components and materials exist).
* The project design system, to resolve conflicts (platform guidance ranks above it, see `skill-router`).

## Procedure

1. **Confirm platforms and deployment targets.** Features introduced in a given OS (for example Liquid Glass from the 26 releases) need a fallback for older targets.
2. **Navigation.** Use the platform's structures: tab bar for top-level peers on iPhone; sidebar and split views on iPad and Mac when space allows; hierarchical navigation with a back affordance; sheets for focused, dismissible tasks. Do not replace system back behavior or the swipe-back gesture.
3. **System components first.** Prefer standard controls, bars, lists, menus, pickers and sheets: they bring accessibility, Dynamic Type, materials and future OS updates for free. Custom controls need a clear reason.
4. **Layout and adaptivity.** Respect safe areas and layout margins; support size classes, rotation, Split View and window resizing on iPad and Mac; content must reflow, not scale.
5. **Typography.** System text styles and Dynamic Type sizes; no fixed font sizes for body content; test the largest accessibility sizes.
6. **Iconography.** SF Symbols with matching weight and scale to adjacent text; custom symbols follow the same grid.
7. **Materials and Liquid Glass.** Reserve Liquid Glass for the navigation and control layer that floats above content (bars, toolbars, controls), not for content itself; avoid stacking glass on glass; check legibility over varied content and with Reduce Transparency and Increase Contrast.
8. **Interaction.** Touch targets at least 44 × 44 pt on iOS and iPadOS; standard gestures keep their system meaning; every gesture has a visible alternative; haptics used sparingly and consistently.
9. **Platform specifics.** macOS: menu bar commands, keyboard shortcuts, pointer hover, multiple windows. watchOS: glanceable, short interactions, Digital Crown. visionOS: comfortable placement in space, larger targets, gaze and pinch, no content locked to the head.
10. **Localization.** Right-to-left mirroring, text expansion, locale formats.

## Output

Review table (screen, issue, HIG area, guideline reference, severity, recommendation, platform or OS availability note) or, for new designs, a platform adaptation spec per target.

## Edge cases

* Brand wants a custom tab bar or navigation: keep system behavior (back, accessibility, materials) and change only appearance where the system allows.
* Ported Android patterns (floating action button, top navigation drawer): replace with the Apple equivalent rather than copying.
* Older deployment targets: specify the fallback appearance explicitly.

## Acceptance criteria

* Every finding cites the relevant HIG area.
* Any feature tied to an OS version states its availability and fallback.
* No custom component replaces a system component without a stated reason.

## Sources

* Human Interface Guidelines: https://developer.apple.com/design/human-interface-guidelines/
* Adopting Liquid Glass: https://developer.apple.com/documentation/technologyoverviews/adopting-liquid-glass
* Apple Design Resources: https://developer.apple.com/design/resources/
