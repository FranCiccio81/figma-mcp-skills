---
name: frontend-testing
description: >-
  Plans and writes frontend tests that catch real regressions: unit and component tests with
  Testing Library queries by role, accessibility checks with axe, visual regression on component
  states, end-to-end tests with Playwright using resilient locators and web-first assertions, API
  mocking, and a policy for flaky tests. Use when asked to add or review tests for a web UI, set up
  component, visual or end-to-end testing, or choose what to test. Do not use for native mobile
  test setup (see compose-implementation and swiftui-implementation).
license: MIT
metadata:
  version: "1.0.0"
  domain: engineering
  status: beta
  trust: internal
  sources: "TESTING-LIBRARY,PLAYWRIGHT,STORYBOOK,W3C-WCAG22"
  platforms: "web"
  last-reviewed: "2026-11-17"
---

# Frontend testing

Test behaviour the user can observe. A test that breaks on every refactor and passes on every bug
is worse than none.

## When to use

- Adding tests to a new component or flow.
- Reviewing a test suite or a flaky pipeline.
- Setting up visual regression or end-to-end testing.

## Inputs

- Test stack already in the project (Jest or Vitest, Testing Library, Playwright or Cypress,
  Storybook), CI setup.
- The feature's acceptance criteria and risk areas.

## Workflow

1. **Decide what to test where:** pure logic in unit tests; component behaviour (render,
   interaction, states) in component tests; critical user journeys (login, payment, onboarding)
   in end-to-end tests; appearance of component states in visual tests.
2. **Component tests:** query by role and accessible name (`getByRole('button', { name: 'Send' })`),
   then label and text; avoid test IDs unless nothing else is stable; simulate with `user-event`;
   assert on visible outcomes, not internal state.
3. **States coverage:** loading, empty, error, success, disabled, long content, RTL if supported.
4. **Accessibility checks:** run axe on components and pages (for example with jest-axe or
   `@axe-core/playwright`); remember automated tools catch only part of WCAG issues; keep manual
   checks in `accessibility-audit`.
5. **Network:** mock at the network layer (for example MSW) with fixtures that match the API
   contract; include error responses.
6. **End-to-end with Playwright:** `getByRole` locators, web-first assertions (`await
   expect(locator).toBeVisible()`), no fixed sleeps, isolated test data, run on the browsers that matter.
7. **Visual regression:** one story or fixture per state; stable data and fonts; review diffs
   before accepting baselines.
8. **Flaky tests:** quarantine with an issue and an owner, fix root causes (timing, shared state,
   test order), never add blind retries as the fix.
9. **CI:** fast tests on every PR, end-to-end and visual on merge or nightly if slow; report
   coverage of critical paths, not a raw percentage target.

## Outputs

Test files in the project's conventions, a test plan table (behaviour, level, file), and notes
on gaps and flaky risks.

## Edge cases

- **Snapshot tests of whole trees:** replace with targeted assertions.
- **Time and dates:** freeze time and set time zone in tests.
- **Animations:** disable or use reduced motion in test environments.
- **Third-party widgets:** test the integration contract, not the vendor's UI.

## Acceptance criteria

- [ ] Queries use roles and accessible names first.
- [ ] Each data component has tests for loading, empty, error and success.
- [ ] Automated accessibility checks run on new components or pages.
- [ ] End-to-end tests contain no fixed sleeps.
- [ ] Network mocks follow the API contract and include errors.

## Sources

- Testing Library guiding principles and queries: https://testing-library.com/
- Playwright best practices: https://playwright.dev/
- Storybook visual and interaction testing: https://storybook.js.org/
- W3C WCAG 2.2: https://www.w3.org/WAI/standards-guidelines/wcag/
