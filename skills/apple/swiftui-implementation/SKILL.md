---
name: swiftui-implementation
description: >-
  Implements or reviews SwiftUI interfaces the native way: app and view architecture with
  Observation, navigation with NavigationStack and NavigationSplitView, system components first,
  design tokens mapped to SwiftUI, Liquid Glass adoption gated by availability, Dynamic Type,
  VoiceOver, localization and right-to-left layout, previews and tests. Use when writing, porting
  or reviewing SwiftUI code, translating a Figma design into SwiftUI, or checking API availability
  against deployment targets. Do not use for UIKit-only codebases without SwiftUI or for design
  review without code (use apple-hig-review).
license: MIT
compatibility: "Requires Xcode and Apple SDKs to build and run; API availability must be checked against the project's deployment targets."
metadata:
  version: "1.0.0"
  domain: apple
  status: beta
  trust: official-derived
  sources: "APPLE-SWIFTUI,APPLE-HIG,APPLE-LIQUID-GLASS,APPLE-ACCESSIBILITY"
  platforms: "ios,ipados,macos,watchos,visionos"
  last-reviewed: "2026-11-17"
---

# SwiftUI implementation

Write SwiftUI that a platform engineer at Apple would recognise: system components, semantic
styles, data flow through Observation, and no invented APIs.

## When to use

- Building new SwiftUI screens or components, including from Figma (combine with
  `figma-design-context`; the official Figma plugin also ships a `figma-swiftui` skill).
- Reviewing SwiftUI pull requests.
- Adopting Liquid Glass or new SDK features without breaking older OS versions.

## Inputs

- Deployment targets per platform (from the Xcode project), Swift and Xcode versions.
- Existing architecture, design system tokens and components in the codebase.
- Designs and acceptance criteria.

## Workflow

1. **Read the project first:** deployment targets, existing patterns (Observation versus
   `ObservableObject`), folder structure, token and component modules. Follow them.
2. **Verify every API** you are not certain of in the SwiftUI documentation for the target SDK.
   Never invent a modifier or type name; if unsure, write the code with a `TODO` and say so.
3. **Model data flow:** `@State` for view-local state, `@Observable` models (iOS 17 and later)
   passed in or through `@Environment`, `@Bindable` for bindings to observable models; keep side
   effects in models or `.task`.
4. **Navigation:** `NavigationStack` with value-based `navigationDestination` on iPhone,
   `NavigationSplitView` for sidebar layouts on iPad and Mac, `TabView` for top-level areas,
   sheets for focused tasks.
5. **System components first:** `List`, `Form`, `Toggle`, `Picker`, `Menu`, `ToolbarItem`,
   `searchable`, `ShareLink`, `Label`, `ContentUnavailableView` before custom views.
6. **Tokens:** map semantic tokens to asset catalog colors (with dark and high contrast variants)
   or a `Color`/`ShapeStyle` extension; typography to text styles (`.body`, `.headline`) or
   `Font.custom(_:size:relativeTo:)` so custom fonts still scale; spacing via `@ScaledMetric`
   where it should follow Dynamic Type. No hex literals in views.
7. **Liquid Glass (26-series SDKs):** let standard bars and controls adopt it automatically;
   for custom floating controls use `glassEffect(_:in:)` inside a `GlassEffectContainer`,
   `.buttonStyle(.glass)` or `.buttonStyle(.glassProminent)`; gate with
   `if #available(iOS 26, *)` (and the matching versions for other platforms) and provide the
   previous material as fallback. See [references/liquid-glass.md](references/liquid-glass.md).
8. **Accessibility and localization:** accessibility labels on icon-only controls, combined
   elements where it helps VoiceOver, layouts that reflow at accessibility text sizes
   (`ViewThatFits`, `dynamicTypeSize`), String Catalogs, leading and trailing instead of left and
   right, previews in a right-to-left locale. Details in `apple-accessibility`.
9. **Previews and tests:** previews for states, dark mode, large text and RTL; unit tests with
   Swift Testing or XCTest per project; UI tests with XCUITest for critical flows.

## Outputs

SwiftUI code that follows the project's structure, a short note listing APIs used with their
minimum OS versions, the availability fallbacks, previews added, tests added and any `TODO`
requiring verification.

## Edge cases

- **Deployment target below iOS 17:** use `ObservableObject` and `@StateObject` instead of Observation.
- **Pixel-perfect Figma requests:** respect Dynamic Type and system spacing; document deviations.
- **Custom tab bar in Figma:** use `TabView` and style it; a fully custom bar loses system behaviour.
- **UIKit interop:** wrap with `UIViewRepresentable` only when no SwiftUI equivalent exists.

## Acceptance criteria

- [ ] Every non-trivial API is checked against the deployment target, with `#available` fallbacks where needed.
- [ ] No invented API names; uncertain calls are marked `TODO` and reported.
- [ ] No hardcoded colors, fonts or spacing in views.
- [ ] Text uses text styles or relative custom fonts and survives accessibility sizes.
- [ ] Icon-only controls have accessibility labels.
- [ ] Previews cover dark mode, large text and RTL for new screens.

## Sources

- SwiftUI documentation: https://developer.apple.com/documentation/swiftui/
- Applying Liquid Glass to custom views and Liquid Glass overview: https://developer.apple.com/documentation/technologyoverviews/liquid-glass
- Apple Human Interface Guidelines: https://developer.apple.com/design/human-interface-guidelines/
- Apple accessibility: https://developer.apple.com/accessibility/
