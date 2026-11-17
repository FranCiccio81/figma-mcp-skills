---
name: visual-regression-qa
description: >-
  Sets up and reviews visual regression testing for UI components and screens:
  choosing what to capture, stabilizing snapshots, configuring thresholds, and triaging
  diffs as regression, intended change or flake. Use when the user wants screenshot or
  snapshot tests, a visual QA gate in CI, or help reviewing failing visual diffs on web,
  iOS or Android.
metadata:
  domain: quality
  version: "1.0.0"
  status: beta
  scope: universal
  trust: authored
  last-reviewed: "2026-11-17"
---

# Visual regression QA

## When to use

* Adding screenshot tests to a component library or app.
* Reviewing a failing visual diff in CI.
* Protecting a design system release from unintended visual change.

## Inputs

* Platform and existing test stack (read the repository first; reuse what exists).
* Components, stories or screens in scope, themes, locales, viewports or devices.
* CI environment details (OS, fonts, browser versions).

## Procedure

1. **Reuse the stack.** Prefer what the project already has. Typical options: Playwright `toHaveScreenshot` or a Storybook-based service for web; Swift snapshot libraries or Xcode UI test attachments for Apple; Compose Preview Screenshot Testing for Android.
2. **Choose the matrix deliberately.** Each component state that has its own visual (default, hover, focus-visible, disabled, error, loading, empty), each theme (light, dark, high contrast), at least one large text setting, one RTL locale. Avoid combinatorial explosion: capture states at one size, sizes at one state.
3. **Stabilize.** Fixed data and dates, disabled animations and carets, preloaded fonts, deterministic random seeds, mocked network, fixed device scale factor, same OS and browser image in CI as baselines.
4. **Threshold.** Start strict (exact or near exact) for components; allow small tolerance for full pages. Never raise thresholds to make a flaky test pass; fix the instability.
5. **Baselines.** Generate in CI's environment, commit with the change that intends them, review them like code.
6. **Triage each diff:** Regression (fix code), Intended (update baseline in the same PR with a note), Flake (fix stabilization, do not update baseline).

## Output

Test configuration and tests in the project's structure, a short README section on how to update baselines, and for diff reviews a triage table (test, classification, evidence, action).

## Edge cases

* Fonts differ between developer machines and CI: generate baselines only in CI or a container.
* Very large pages: split into regions; full-page captures hide small regressions.
* Visual tests are not accessibility tests: they do not check names, roles or focus order.

## Acceptance criteria

* Running the suite twice on unchanged code produces zero diffs.
* Every intended baseline change is linked to a code change and reviewed.
* State, theme, text-size and RTL coverage is listed.

## Sources

* Playwright visual comparisons: https://playwright.dev/docs/test-snapshots
* Compose screenshot testing (official Android skill `jetpack-compose/adaptive` references it): https://github.com/android/skills
* Apple XCTest: https://developer.apple.com/documentation/xctest
