---
name: compose-implementation
description: >-
  Implements or reviews Jetpack Compose UI with Material 3: theme mapping from design tokens,
  state hoisting and unidirectional data flow, Material components, adaptive layouts with window
  size classes, edge-to-edge insets, navigation, semantics for TalkBack, previews and Compose UI
  tests, delegating deep topics to the official Android skills. Use when writing, porting or
  reviewing Compose code, translating a Figma design to Compose, or checking Compose UI quality. Do
  not use for XML Views without Compose or for design-only review (use material3-design-review).
license: MIT
compatibility: "Requires the Android SDK and Gradle to build; check Compose BOM and Material 3 versions in the project."
metadata:
  version: "1.0.0"
  domain: android
  status: beta
  trust: official-derived
  sources: "ANDROID-COMPOSE,ANDROID-ADAPTIVE,M3,REPO-ANDROID-SKILLS"
  platforms: "android"
  last-reviewed: "2026-11-17"
---

# Compose implementation

Compose code should read like the official samples: stateless composables, hoisted state,
`MaterialTheme` for every visual decision, and layouts that respond to the window.

## When to use

- Building screens or components in Compose, including from Figma.
- Reviewing Compose pull requests.
- Making an existing Compose app adaptive or edge-to-edge.

## Inputs

- Project structure, Compose BOM and Material 3 versions, min and target SDK.
- Existing theme, tokens and components.
- Designs and acceptance criteria.

## Workflow

1. **Read the project:** theme files, component library, navigation library (Navigation 2 or 3),
   architecture (ViewModel, state holders), test setup. Follow existing conventions.
2. **Install or consult the official Android skills** for deep topics instead of improvising:
   `adaptive`, `edge-to-edge`, `navigation-3`, `testing-setup`, `jetpack-compose-performance`
   from https://github.com/android/skills.
3. **Theme:** map project tokens to `ColorScheme` roles, `Typography` and `Shapes`; add custom
   tokens through a `CompositionLocal` or theme extension only when Material roles do not fit.
   No raw `Color(0xFF...)` or `dp` values for design decisions inside components.
4. **State:** composables receive state and emit events (`value`, `onValueChange`); state lives
   in a ViewModel or state holder; use `remember` and `rememberSaveable` for UI state that must
   survive configuration changes.
5. **Components:** Material 3 components first; custom components expose a `modifier: Modifier =
   Modifier` parameter applied to the root, and follow Material slot APIs.
6. **Adaptive layout:** read `currentWindowAdaptiveInfo().windowSizeClass` at the top level and
   pass layout decisions down; use list-detail or supporting pane scaffolds for larger windows.
7. **Edge-to-edge:** enable edge-to-edge, consume `WindowInsets` through `Scaffold` or
   `Modifier.windowInsetsPadding`, handle `imePadding` for forms.
8. **Semantics:** `contentDescription` for meaningful icons (null for decorative), merged
   semantics for list items, `Role` and `stateDescription` for custom controls, minimum touch
   target via Material components or `Modifier.minimumInteractiveComponentSize()`.
9. **Previews and tests:** previews for light and dark, font scale 2.0, RTL and window sizes;
   Compose UI tests with `createComposeRule` and semantic matchers; screenshot tests if the
   project uses them.

## Outputs

Kotlin code in the project structure, with KDoc on public composables, a list of tokens or theme
roles used, previews and tests added, and links to the official skill used for any delegated topic.

## Edge cases

- **Design built on iOS patterns:** adapt with `material3-design-review` before coding.
- **Old Compose BOM:** check API availability (adaptive and Material 3 APIs evolve quickly).
- **XML interop:** use `ComposeView` or `AndroidView` and keep the boundary small.
- **Performance problems in lists:** stable keys in `LazyColumn`, avoid heavy work in composition; see the official performance skill.

## Acceptance criteria

- [ ] No hardcoded colors, typography or design dimensions in components.
- [ ] State is hoisted; composables are previewable without a ViewModel.
- [ ] Layout adapts to at least compact and expanded widths.
- [ ] Edge-to-edge insets, including the keyboard, are handled.
- [ ] Semantics and 48 dp targets are in place.
- [ ] Previews include dark mode, large font scale and RTL.

## Sources

- Jetpack Compose: https://developer.android.com/develop/ui/compose
- Adaptive apps: https://developer.android.com/develop/adaptive-apps
- Material Design 3: https://m3.material.io/
- Official Android skills: https://github.com/android/skills
