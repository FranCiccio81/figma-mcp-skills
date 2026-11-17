---
name: swiftui-implementation
description: >-
  Implements and reviews SwiftUI interfaces: view structure and state, navigation,
  native components, design tokens as a theme, Dynamic Type, accessibility modifiers,
  localization, Liquid Glass adoption with availability checks, previews and tests
  (Swift Testing, XCTest UI tests, accessibility audits). Use when the user builds or
  reviews SwiftUI code, converts a design to SwiftUI, adopts a new SwiftUI API, or
  writes tests for an Apple app.
compatibility: Requires Xcode and the Apple SDKs for the deployment targets. Check every API's availability against the project's minimum OS versions.
metadata:
  domain: apple
  version: "1.0.0"
  status: beta
  scope: universal
  trust: official-derived
  last-reviewed: "2026-11-17"
---

# SwiftUI implementation

## When to use

* Building or changing SwiftUI views, converting Figma designs (with `figma-design-to-code`), adopting new APIs, testing Apple UI.

## Inputs

* The project: minimum deployment targets, architecture (state management, navigation), existing components and theme.
* The design (Figma, spec) and requirements.

## Procedure

1. **Read the project first:** deployment targets, Swift version, architecture conventions, existing reusable views and theme. Follow them.
2. **Verify API availability.** Never use an API you cannot find in Apple's documentation, and never invent names. Wrap newer APIs in `if #available` or `@available` with a fallback matching the HIG (for example glass effects exist from iOS 26 and the matching releases of other platforms).
3. **Structure.** Small views with a single responsibility; state owned at the right level; derived values computed, not stored twice. Use the project's state approach (for example `@Observable` models where the target allows).
4. **Native components and navigation:** `NavigationStack` or `NavigationSplitView`, `TabView`, `List`, `Form`, `Menu`, `.sheet`, `.toolbar`. Keep system back behavior.
5. **Tokens.** Map design tokens into a theme (colors in the asset catalog with appearance variants, spacing and radius constants, text styles). No literal colors or sizes in views.
6. **Type and layout.** System text styles (`.font(.body)`), `@ScaledMetric` for spacing or icons that should scale, layouts that reflow at accessibility sizes (`ViewThatFits`, stack axis switching). Avoid fixed frames around text.
7. **Accessibility.** Meaningful `accessibilityLabel`, `accessibilityValue`, `accessibilityHint` only when helpful; traits; combine related elements; hide decorative images; custom actions for swipe-only operations; respect `accessibilityReduceMotion` and `accessibilityReduceTransparency`. Details in `apple-accessibility`.
8. **Liquid Glass.** Prefer system bars and controls, which adopt it automatically when built with the new SDK. For custom floating controls use `glassEffect(_:in:)`, group nearby glass elements in a `GlassEffectContainer`, keep glass off content.
9. **Localization.** String Catalogs, no concatenated strings, formatted numbers, dates and currencies, previews in a right-to-left locale and at large Dynamic Type sizes.
10. **Tests.** Unit tests for models (Swift Testing or XCTest per project), UI tests for critical flows, `performAccessibilityAudit()` in UI tests where the target supports it, previews for each state, snapshot tests if the project uses them (`visual-regression-qa`).

## Output

Code in the project structure, previews for each state, tests, and a note listing APIs used with their minimum OS version and any fallback.

## Edge cases

* UIKit interop needed (a control SwiftUI lacks): wrap with `UIViewRepresentable` and keep accessibility intact.
* Custom design conflicts with Dynamic Type (fixed-height cards): change the layout, not the text size.
* Performance: large lists use lazy containers and stable identity; avoid heavy work in `body`.

## Acceptance criteria

* Builds for the minimum deployment target without availability warnings.
* No hard-coded colors, fonts or spacing where theme values exist.
* Screens remain usable at the largest accessibility text size and with VoiceOver.
* Tests cover the critical flow and pass.

## Sources

* SwiftUI documentation: https://developer.apple.com/documentation/swiftui/
* Glass effect API (`glassEffect(_:in:)`, availability): https://developer.apple.com/documentation/swiftui/view/glasseffect(_:in:)
* Human Interface Guidelines: https://developer.apple.com/design/human-interface-guidelines/
* Apple accessibility: https://developer.apple.com/accessibility/
