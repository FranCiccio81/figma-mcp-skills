---
name: react-typescript-components
description: >-
  Builds and reviews React components in TypeScript: typed props that make invalid
  states unrepresentable, composition over configuration, controlled and uncontrolled
  patterns, accessibility semantics, design tokens instead of literals, state and
  effects discipline, and co-located tests and stories. Use when the user writes or
  refactors React components, designs a component's TypeScript API, or reviews React
  code for correctness, accessibility and maintainability.
metadata:
  domain: engineering
  version: "1.0.0"
  status: beta
  scope: universal
  trust: authored
  last-reviewed: "2026-11-17"
---

# React and TypeScript components

## When to use

* Creating or refactoring React components, hooks or component libraries.
* Implementing a design system component (`component-api-design`) on the web.

## Inputs

* The repository: React version, framework (Next.js, Vite, Remix...), styling approach, lint and test setup, existing components.

## Procedure

1. **Follow the project.** Match its conventions (file layout, styling, state library, naming). Do not add dependencies when the stack already covers the need.
2. **Typed API.** Discriminated unions for variants that carry different props; required props for meaning (accessible name); extend native element props (`React.ComponentPropsWithoutRef<'button'>`) and forward refs where consumers need them; no `any`.
3. **Semantics first.** Use the native element (`button`, `a`, `input`, `dialog`, `details`) before ARIA; when building a custom widget, follow the WAI-ARIA Authoring Practices keyboard pattern.
4. **Composition.** Children and slots over boolean prop explosions; compound components for related parts.
5. **State.** Keep state minimal and derived values computed; lift state only as needed; support controlled and uncontrolled use for inputs (`value`/`onChange` and `defaultValue`).
6. **Effects.** Use effects only to sync with external systems; no effects to compute derived data; clean up subscriptions; avoid race conditions in data fetching (abort or ignore stale responses).
7. **Styling with tokens.** CSS variables or theme values from the token pipeline; no literal colors and sizes; visible `:focus-visible` styles; respect `prefers-reduced-motion`.
8. **Performance** only where measured (`frontend-performance`): avoid premature memoization.
9. **Tests and docs.** Behavior tests with Testing Library querying by role and name (`frontend-testing`), stories for each state, JSDoc on public props.

## Output

Component files in the project structure, tests, stories or examples, and a short note on API decisions.

## Edge cases

* Server components and client components (Next.js App Router): keep interactivity in client components; do not pass non-serializable props across the boundary.
* Polymorphic `as` props: type them carefully or prefer separate components; incorrect polymorphism breaks semantics.
* Third-party UI kits: wrap them to keep the project's API and tokens stable.

## Acceptance criteria

* Type check passes with strict settings; no `any` in public APIs.
* Keyboard and screen reader behavior match the relevant ARIA pattern or native element.
* No literal design values where tokens exist.
* Tests query by role and accessible name.

## Sources

* React documentation: https://react.dev/
* TypeScript handbook: https://www.typescriptlang.org/docs/
* WAI-ARIA Authoring Practices: https://www.w3.org/WAI/ARIA/apg/
