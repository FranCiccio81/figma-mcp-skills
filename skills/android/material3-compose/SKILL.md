---
name: material3-compose
description: >-
  Designs and implements Android UI with Material Design 3 and Jetpack Compose: theme
  (color scheme roles, dynamic color, typography, shapes) mapped from design tokens,
  Material components, navigation patterns, edge-to-edge and insets, states, previews
  and Compose UI tests. Use when the user builds or reviews Android screens in
  Compose, converts a Figma design to Compose, sets up a Material 3 theme, or adapts
  an iOS or web design to Android conventions.
compatibility: Requires an Android project using Jetpack Compose. For deeper official workflows install the matching skills from https://github.com/android/skills.
metadata:
  domain: android
  version: "1.0.0"
  status: beta
  scope: universal
  trust: official-derived
  last-reviewed: "2026-11-17"
---

# Material 3 with Jetpack Compose

## When to use

* Building or reviewing Compose screens, themes and components.
* Translating a design (Figma, iOS, web) to Android.
* For edge-to-edge migrations, adaptive layouts, Navigation 3 and test setup, prefer the official Android skills (`edge-to-edge`, `adaptive`, `navigation-3`, `testing-setup`) and use this skill for design-system alignment.

## Inputs

* The project: `minSdk`, `targetSdk`, Compose and Material 3 versions, architecture, existing theme and components.
* Design tokens or Figma variables (`design-token-architecture`).

## Procedure

1. **Read the project.** Versions, theme, component library, navigation approach. Reuse before creating.
2. **Theme from tokens.** Map semantic tokens to Material roles (`primary`, `onPrimary`, `primaryContainer`, `surface`, `surfaceContainer*`, `onSurface`, `onSurfaceVariant`, `outline`, `error`) in `MaterialTheme(colorScheme, typography, shapes)`. Brand colors map to roles, components never read raw palette values. Provide light and dark schemes.
3. **Dynamic color.** Decide explicitly: use dynamic color on supported devices (Android 12 and higher) or keep brand colors; if mixing, keep brand-critical elements on fixed roles and check contrast in both cases.
4. **Typography and shapes.** Map the type scale to Material roles (display, headline, title, body, label) with `sp` units; shapes to the small, medium, large scale.
5. **Components and navigation.** Material components first (`Scaffold`, top app bars, `NavigationBar`, `NavigationRail`, buttons, cards, lists, dialogs, bottom sheets). Respect system back and predictive back. Do not port iOS patterns directly (for example an iOS-style back chevron in a custom top bar, or a tab bar with iOS spacing).
6. **Edge-to-edge and insets.** Apps targeting recent SDKs draw edge-to-edge; apps targeting Android 16 (API 36) can no longer opt out. Handle insets with `Scaffold` and `WindowInsets` APIs, keep tappable content out of system bar and gesture areas, handle the IME.
7. **Touch targets** at least 48 × 48 dp; state layers for pressed, focused, hovered; visible keyboard focus.
8. **States and content.** Loading, empty, error; long text and font scale up to 200 %; right-to-left.
9. **Previews and tests.** `@Preview` per state, theme and font scale; Compose UI tests on semantics (not on pixel positions); screenshot tests if the project has them (`visual-regression-qa`).

## Output

Theme code, composables in the project structure, previews, tests, and a mapping table (design token → Material role or project theme value) with gaps.

## Edge cases

* Brand palette fails contrast against Material role pairings: adjust tones, not the role mapping.
* Custom design system on top of Material: wrap Material components and expose project-level APIs; keep Material accessibility behavior.
* Wear OS, TV, Auto: different guidance and components; use the official Android skills for those form factors.

## Acceptance criteria

* No hard-coded colors, text sizes or shapes in composables where theme values exist.
* Content is never obscured by system bars or the keyboard.
* Interactive targets are at least 48 dp; screens work at 200 % font scale.
* Previews cover light, dark and large font; tests cover the critical flow.

## Sources

* Material Design 3: https://m3.material.io/
* Jetpack Compose: https://developer.android.com/develop/ui/compose
* Android 16 behavior changes (edge-to-edge opt-out removed): https://developer.android.com/about/versions/16/behavior-changes-16
* Official Android agent skills: https://github.com/android/skills
