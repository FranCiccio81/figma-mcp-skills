---
name: frontend-testing
description: >-
  Plans and writes frontend tests at the right level: unit tests for logic, component
  tests that query by role and accessible name, end-to-end tests for critical journeys,
  accessibility checks, and visual tests, with stable, non-flaky practices. Use when
  the user adds tests to a web frontend, chooses between unit, component and
  end-to-end tests, fixes flaky tests, or reviews test quality.
metadata:
  domain: engineering
  version: "1.0.0"
  status: beta
  scope: universal
  trust: authored
  last-reviewed: "2026-11-17"
---

# Frontend testing

## When to use

* Adding or reviewing tests for web components, pages and flows.
* Native apps: use `swiftui-implementation` (Apple) or `material3-compose` and the official Android `testing-setup` skill.

## Inputs

* Existing test stack (Vitest or Jest, Testing Library, Playwright or Cypress, Storybook), CI setup, critical user journeys.

## Procedure

1. **Use the existing stack.** Add tools only with a reason the current stack cannot cover.
2. **Choose the level:**
   * Unit: pure logic (formatters, reducers, validation).
   * Component: behavior of a component through its public interface, rendered in a DOM environment.
   * End-to-end: a few critical journeys in a real browser (sign-in, payment, onboarding).
   * Visual: `visual-regression-qa`. Accessibility: automated checks in component and e2e tests, plus manual testing (`accessibility-audit`).
3. **Test behavior, not implementation.** Query by role and accessible name (`getByRole('button', { name: 'Save' })`), interact like a user (keyboard included), assert on visible outcomes. Avoid snapshotting large DOM trees.
4. **Stability.** No arbitrary sleeps; wait for conditions; control time, randomness and network (mock at the network boundary); isolate test data; run in parallel safely.
5. **Coverage that matters.** Each requirement's acceptance criteria (`product-requirements`) maps to at least one test; error, empty and loading states included.
6. **CI.** Fast tests on every change, e2e on main paths per PR or nightly as the team decides; failing tests block merges; quarantine flaky tests with an owner and a deadline.

## Output

Test files in the project's structure, a short test plan mapping acceptance criteria to tests, and CI changes when needed.

## Edge cases

* Legacy code without seams: start with e2e or component tests around the behavior before refactoring.
* Third-party iframes (payment providers): test up to the boundary, mock the provider in component tests, use the provider's sandbox in e2e.
* Feature flags: test both states of flags that ship.

## Acceptance criteria

* Tests use accessible queries and user-level interactions.
* No fixed sleeps; suite passes repeatedly without flakes.
* Each acceptance criterion of the feature is traceable to a test.

## Sources

* Testing Library guiding principles: https://testing-library.com/docs/guiding-principles
* Playwright documentation: https://playwright.dev/docs/intro
* web.dev, testing strategies: https://web.dev/
