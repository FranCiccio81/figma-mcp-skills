---
name: material3-design-review
description: >-
  Reviews or adapts designs for Android with Material Design 3: color roles and dynamic color,
  type scale, shape, components, navigation by window size class (navigation bar, rail, drawer),
  canonical adaptive layouts for tablets and foldables, edge-to-edge and system bars, predictive
  back, 48 dp touch targets and Android-specific patterns. Use when asked whether a design fits
  Android, to adapt an iOS or web design to Android, or to check Material 3 compliance. Do not use
  for Compose code (use compose-implementation) or for Apple platforms.
license: MIT
metadata:
  version: "1.0.0"
  domain: android
  status: beta
  trust: official-derived
  sources: "M3,ANDROID-DESIGN,ANDROID-ADAPTIVE,REPO-ANDROID-SKILLS"
  platforms: "android"
  last-reviewed: "2026-11-17"
---

# Material 3 design review

Android users expect system back, edge-to-edge content, Material components and layouts that
adapt to the window, not to a device name.

## When to use

- Designing or reviewing Android screens.
- Porting designs from iOS or web.
- Preparing a design for tablets, foldables, ChromeOS or desktop windows.

## Inputs

- Designs (Figma via `figma-design-context`, screenshots) or a build.
- Minimum and target SDK, supported form factors.
- Project design system and its mapping to Material roles, if any.

## Workflow

1. **Window size classes first:** review layouts for compact (< 600 dp), medium (600 to 840 dp)
   and expanded (840 to 1200 dp) widths, plus large and extra-large where desktop or large
   tablets matter. Window size, not device type, drives layout.
2. **Navigation:** navigation bar with three to five destinations on compact; navigation rail on
   medium and larger; modal or standard drawer when destinations exceed five; top app bar
   patterns; system back always works (no custom back that fights predictive back).
3. **Canonical layouts:** list-detail, supporting pane and feed for larger windows; check the
   single-pane fallback on compact.
4. **Edge-to-edge:** content draws behind status and navigation bars (enforced for apps targeting
   SDK 35 on Android 15 and later); check insets for bars, display cutouts and the keyboard (IME);
   gesture navigation areas stay clear of swipe interactions.
5. **Color:** use Material color roles (primary, on-primary, primary-container, surface,
   surface-container levels, outline...) mapped from the project tokens; decide whether dynamic
   color (Android 12 and later) is allowed by the brand and provide a static scheme fallback;
   check contrast of each role pair.
6. **Type, shape and elevation:** Material type scale roles, shape scale, tonal elevation; map to
   project tokens rather than raw values.
7. **Components and patterns:** Material components (buttons, FAB when one primary action
   exists, chips, cards, bottom sheets, snackbars, dialogs); avoid iOS-only patterns (action
   sheets from the bottom with Cancel, back chevron labels, segmented controls where tabs or
   chips fit better).
8. **Touch targets:** at least 48 × 48 dp for interactive elements, even when the visual is smaller.
9. **Report** findings with M3 or Android guideline reference, window class, severity and fix.
   See [references/m3-checklist.md](references/m3-checklist.md).

## Outputs

Review table: ID, window class, screen, guideline, finding, evidence, severity, recommendation;
plus required adaptations per window class and the color role mapping table if relevant.

## Edge cases

- **Brand rejects dynamic color:** keep static brand scheme, still use color roles.
- **Foldable hinge or tabletop posture:** avoid placing critical content across the fold; consider a tabletop layout.
- **Tablet design missing:** propose medium and expanded adaptations instead of stretching the phone layout.
- **Material 3 Expressive components:** check that the Compose Material 3 version used by the project provides them before designing with them.

## Acceptance criteria

- [ ] Layouts are reviewed for at least compact, medium and expanded widths.
- [ ] Navigation component matches the window class and destination count.
- [ ] Edge-to-edge and insets, including IME, are addressed.
- [ ] Colors map to Material roles with contrast checked.
- [ ] Touch targets are at least 48 × 48 dp.
- [ ] No iOS-only pattern remains without justification.

## Sources

- Material Design 3: https://m3.material.io/
- Android design for mobile: https://developer.android.com/design/ui/mobile
- Adaptive apps and window size classes: https://developer.android.com/develop/adaptive-apps
- Official Android skills (adaptive, edge-to-edge, navigation-3): https://github.com/android/skills
