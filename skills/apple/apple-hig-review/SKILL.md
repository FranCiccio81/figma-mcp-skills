---
name: apple-hig-review
description: >-
  Reviews or designs interfaces for Apple platforms against the Human Interface Guidelines: iOS
  navigation, iPadOS adaptivity and pointer, macOS windows, menus and toolbars, watchOS glanceable
  interaction, visionOS spatial input, Liquid Glass and materials, SF Symbols, system colors, Dynamic
  Type, dark mode and haptics. Use when asked whether a design "feels native" on iPhone, iPad, Mac,
  Apple Watch or Vision Pro, to adapt a design to an Apple platform, or to check HIG compliance. Do
  not use for Android or web conventions, or for SwiftUI code (use swiftui-implementation).
license: MIT
metadata:
  version: "1.0.0"
  domain: apple
  status: beta
  trust: official-derived
  sources: "APPLE-HIG,APPLE-LIQUID-GLASS,APPLE-ACCESSIBILITY,APPLE-DESIGN"
  platforms: "ios,ipados,macos,watchos,visionos"
  last-reviewed: "2026-11-17"
---

# Apple HIG review

Native Apple apps feel familiar because they reuse system structures, components and behaviours.
Deviate only with a reason that serves users, and keep the deviation consistent.

## When to use

- Designing or reviewing screens for one or several Apple platforms.
- Porting a design from web or Android to Apple platforms.
- Checking a design against Liquid Glass and the current system appearance.

## Inputs

- Designs (Figma via `figma-design-context`, screenshots) or a running build.
- Target platforms and minimum OS versions (deployment targets).
- Brand and design system constraints from the project.

## Workflow

1. **Fix the platform scope and OS versions.** Liquid Glass applies from the 26-series releases
   (iOS 26, iPadOS 26, macOS Tahoe 26, watchOS 26, tvOS 26, visionOS 26); earlier targets keep the
   previous appearance. Note which guidance applies to which version.
2. **Structure and navigation** per platform using [the platform matrix](references/platform-matrix.md):
   tab bars and navigation stacks on iPhone, sidebars and split views on iPad and Mac, menus and
   keyboard shortcuts on Mac, short focused flows on Apple Watch, windows, volumes and spaces on
   Vision Pro.
3. **Components:** prefer system components (lists, forms, pickers, sheets, menus, toolbars,
   search) before custom ones; check that custom components reproduce system behaviours
   (states, accessibility, Dynamic Type).
4. **Materials and Liquid Glass:** Liquid Glass is for the navigation and control layer that
   floats above content, not for content itself; avoid glass on glass; use the clear variant only
   over visually rich content; keep legibility with Reduce Transparency and Increase Contrast.
5. **Typography and color:** system text styles with Dynamic Type; semantic system colors and
   asset catalog colors with light, dark and increased contrast variants; brand color as tint,
   not as text on low-contrast backgrounds.
6. **Icons:** SF Symbols where possible, matching text weight and scale; custom symbols exported
   as symbol templates; app icon per current HIG layers and appearances.
7. **Input and feedback:** touch targets (44 × 44 pt default on iOS, see matrix), pointer and
   keyboard on iPad and Mac, Digital Crown on Watch, gaze and pinch on Vision Pro, haptics for
   meaningful feedback only.
8. **Accessibility pass:** hand off to `apple-accessibility` for VoiceOver, Dynamic Type and
   motion settings.
9. **Report** each deviation with HIG topic, platform, severity and recommendation; separate
   design guidance (should) from implementation requirements (must, for example App Review rules).

## Outputs

A review table: ID, platform, screen, HIG topic, finding, evidence, severity (0 to 4), guidance
or requirement, recommendation. Plus a summary of platform adaptations needed and open questions.

## Edge cases

- **Brand wants a custom tab bar:** keep system placement and behaviour; style through tint and
  symbols; document the deviation.
- **Android patterns imported** (floating action button, top-left drawer, back arrow on the
  first screen): replace with Apple equivalents (toolbar button, sidebar or tab bar, no back on root).
- **iPad treated as a big iPhone:** require size class adaptation, multitasking windows and pointer support.
- **Unknown deployment target:** ask, or give both pre-26 and 26 guidance.

## Acceptance criteria

- [ ] Platforms and OS versions are stated, and Liquid Glass guidance is applied only where available.
- [ ] Each finding cites the HIG topic and platform.
- [ ] System components are preferred, or the custom component's extra behaviours are listed.
- [ ] Guidance and hard requirements are distinguished.
- [ ] Accessibility findings are handed to `apple-accessibility`.

## Sources

- Apple Human Interface Guidelines: https://developer.apple.com/design/human-interface-guidelines/
- Liquid Glass technology overview: https://developer.apple.com/documentation/technologyoverviews/liquid-glass
- Apple accessibility: https://developer.apple.com/accessibility/
- Apple design hub: https://developer.apple.com/design/
