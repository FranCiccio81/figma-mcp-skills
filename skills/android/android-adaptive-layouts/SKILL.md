---
name: android-adaptive-layouts
description: >-
  Designs and reviews adaptive Android layouts for phones, foldables, tablets,
  ChromeOS and desktop windows: window size classes, canonical layouts (list-detail,
  supporting pane, feed), adaptive navigation (bar, rail), posture and hinge handling,
  resizability and state preservation. Use when the user designs for large screens or
  foldables, asks which layout to use at which width, adapts a phone design to tablet,
  or prepares an app for Android 16 large-screen behavior.
compatibility: Implementation details evolve quickly; for code, install and follow the official `adaptive` skill from https://github.com/android/skills.
metadata:
  domain: android
  version: "1.0.0"
  status: beta
  scope: universal
  trust: official-derived
  last-reviewed: "2026-11-17"
---

# Android adaptive layouts

## When to use

* Designing the large-screen and foldable behavior of an Android app.
* Reviewing whether an app adapts correctly to window changes.
* Code work: the official Android `adaptive` skill covers implementation (Compose adaptive APIs, Navigation 3 scenes, MediaQuery, Grid and FlexBox); this skill covers design decisions and review.

## Inputs

* Screens and navigation structure, target devices, `targetSdk`.

## Procedure

1. **Think in windows, not devices.** Window size classes describe the space the app gets, which changes with multi-window, folding, rotation and desktop resizing. No `isTablet` logic.
2. **Width breakpoints:** compact < 600 dp, medium 600 to 840 dp, expanded 840 to 1200 dp, large 1200 to 1600 dp, extra-large ≥ 1600 dp. **Height:** compact < 480 dp, medium 480 to 900 dp, expanded ≥ 900 dp. Width usually drives layout; check height for landscape phones.
3. **Navigation by width:** navigation bar at compact, navigation rail at medium and larger (or a permanent drawer when many destinations and wide space). Keep destinations identical across sizes.
4. **Canonical layouts:** list-detail (one pane at compact, two panes from medium or expanded), supporting pane, feed (adaptive grid columns). Choose per screen.
5. **Content width.** Avoid stretching text lines and forms across wide windows; constrain readable width, use additional panes instead.
6. **Foldables.** Avoid placing controls or content across a separating hinge; consider tabletop posture for media or camera; continuity when folding and unfolding without losing state.
7. **Resizability.** Apps targeting Android 16 (API 36) have orientation, resizability and aspect-ratio restrictions ignored on large screens (smallest width ≥ 600 dp): every screen must work in any orientation and size.
8. **State preservation** across configuration changes: scroll position, selection, input, playback.
9. **Input:** keyboard, mouse and stylus on large screens; hover states, shortcuts, focus traversal.
10. **Test** at the compact, medium and expanded breakpoints at least, in both orientations, in split screen, and on a foldable emulator.

## Output

Adaptive layout spec per screen: layout per width class, navigation per class, pane behavior, content width rules, foldable posture behavior, state preservation list, test matrix.

## Edge cases

* Screens that cannot meaningfully use more space (a short form): center and constrain width rather than stretching.
* Camera or video screens that previously forced portrait: design landscape and resizable behavior explicitly.
* Same app on ChromeOS desktop windows: support free resizing and pointer input.

## Acceptance criteria

* Every screen has defined behavior at compact, medium and expanded widths.
* No layout logic depends on device type.
* State survives rotation, folding and resizing.
* No interactive element crosses a separating hinge.

## Sources

* Window size classes: https://developer.android.com/develop/ui/compose/layouts/adaptive/use-window-size-classes
* Adaptive apps: https://developer.android.com/develop/adaptive-apps
* Android 16 behavior changes: https://developer.android.com/about/versions/16/behavior-changes-16
* Official Android `adaptive` skill: https://github.com/android/skills
