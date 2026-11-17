---
name: react-component-engineering
description: >-
  Builds and refactors React and TypeScript UI the maintainable way: typed props APIs, composition
  over configuration, native elements for accessibility, controlled and uncontrolled patterns,
  state colocation, effects only for external synchronisation, typed API integration with loading,
  empty, error and retry states, and design tokens instead of hardcoded styles. Use when
  implementing React components or screens, integrating an API in a React UI, translating Figma
  output into project React code, or refactoring React code. Do not use for design-system
  component governance (use component) or for test strategy alone (use frontend-testing).
license: MIT
metadata:
  version: "1.0.0"
  domain: engineering
  status: beta
  trust: internal
  sources: "REACT-DOCS,TS-DOCS,WEB-MDN,W3C-APG"
  platforms: "web"
  last-reviewed: "2026-11-17"
---

# React component engineering

Correctness, readability, accessibility and maintainability come before visual novelty. Use what
the project already uses before adding a dependency.

## When to use

- Implementing components or screens in an existing React codebase.
- Converting Figma MCP output (React plus Tailwind by default) into the project's conventions.
- Integrating a backend API into the UI.

## Inputs

- The codebase: React version, TypeScript config, styling approach (CSS modules, Tailwind,
  CSS-in-JS, BEM), state and data libraries, folder conventions, existing components and tokens.
- Designs or spec, API contract (OpenAPI or types).

## Workflow

1. **Survey before writing:** search for an existing component or hook that already does it; read
   two neighbouring components to copy conventions; check the React version (React 19 accepts
   `ref` as a regular prop; older versions need `forwardRef`).
2. **Design the props API:** minimal, typed, named after intent (`variant="danger"`, not
   `red`); extend native element props when wrapping a native element; prefer `children` and
   slots over boolean flag explosions; document with JSDoc.
3. **Use native semantics:** `button` for actions, `a` for navigation, `label` with inputs,
   lists and headings in order; add ARIA only for patterns that need it, following the APG.
4. **Place state correctly:** derive instead of duplicating; colocate state with its only user;
   lift only when shared; controlled components expose `value` and `onChange`, uncontrolled ones
   `defaultValue`.
5. **Effects:** use `useEffect` only to synchronise with something outside React (subscriptions,
   DOM APIs); compute derived values during render; handle events in handlers.
6. **API integration:** typed client generated from the contract or typed by hand; use the
   project's data library (for example TanStack Query or SWR) if present; handle loading, empty,
   error (with retry) and success states; abort on unmount; never leak secrets to the client.
7. **Styling:** tokens through the project mechanism (CSS custom properties, Tailwind theme,
   theme object); no hex or pixel literals for design decisions; respect reduced motion.
8. **Errors and resilience:** error boundary at route or feature level, user-friendly messages,
   logging without personal data.
9. **Tests and stories:** add tests per `frontend-testing` and a story per state if Storybook exists.

## Outputs

Code in the project's structure (component, styles, index export, tests, story), JSDoc on public
components, and a short note listing reused components, new dependencies (ideally none) and
remaining TODOs.

## Edge cases

- **Figma MCP returns absolute positioning:** rebuild with flex or grid; never ship `position:
  absolute` layouts copied from Figma.
- **Localhost asset URLs from Figma MCP:** usable during development; move assets into the
  project's asset pipeline before merging.
- **Long content and translations:** test with long strings; no fixed widths on text containers.
- **Server components (Next.js App Router):** keep interactivity in client components; do not
  import server-only code into them.

## Acceptance criteria

- [ ] No duplicated component when an equivalent exists.
- [ ] Props are typed and documented; no `any` without justification.
- [ ] Native elements carry semantics; ARIA follows the APG.
- [ ] Loading, empty, error and success states are implemented for data views.
- [ ] No hardcoded design values; tokens are used.
- [ ] No new dependency without a stated reason.

## Sources

- React documentation: https://react.dev/
- TypeScript handbook: https://www.typescriptlang.org/
- MDN Web Docs: https://developer.mozilla.org/
- WAI-ARIA Authoring Practices Guide: https://www.w3.org/WAI/ARIA/apg/
