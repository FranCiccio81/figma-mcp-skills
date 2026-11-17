---
name: semantic-html-css
description: >-
  Writes and reviews semantic HTML and maintainable CSS: document structure and
  landmarks, forms, native elements before ARIA, CSS architecture with design tokens
  as custom properties, cascade layers, responsive and intrinsic layouts, container
  queries, logical properties for RTL, and user preferences (reduced motion, color
  scheme, contrast). Use when the user builds or reviews markup, page layouts,
  responsive behavior, or a CSS architecture.
metadata:
  domain: engineering
  version: "1.0.0"
  status: beta
  scope: universal
  trust: authored
  last-reviewed: "2026-11-17"
---

# Semantic HTML and CSS architecture

## When to use

* Markup and styling for pages and components; responsive layouts; CSS refactors.

## Inputs

* Repository conventions (CSS Modules, utility CSS, CSS-in-JS, Sass), token output, browser support policy.

## Procedure

1. **Structure.** One `h1`, ordered headings; landmarks (`header`, `nav`, `main`, `footer`, `aside`); lists for lists; tables for tabular data with headers; buttons for actions, links for navigation.
2. **Forms.** Visible `label` for each control, `fieldset` and `legend` for groups, correct `type`, `autocomplete` and `inputmode`, errors linked with `aria-describedby`, no placeholder used as the label.
3. **ARIA only when needed.** Native semantics first; incorrect ARIA is worse than none.
4. **CSS architecture.** Tokens as custom properties from the token pipeline; component-scoped styles; cascade layers (`@layer`) to order reset, base, components, utilities; low specificity; no `!important` except in utilities by convention.
5. **Layout.** Flexbox and Grid with intrinsic sizing (`minmax`, `auto-fit`, `clamp`), container queries for component-level responsiveness, media queries for page-level changes. Content-driven breakpoints aligned with the design system.
6. **Internationalization.** Logical properties (`margin-inline-start`, `inset-inline`), `dir` support, no fixed widths on text containers.
7. **User preferences.** `prefers-reduced-motion`, `prefers-color-scheme`, `prefers-contrast`, forced colors mode (`forced-colors: active`) keeps borders and focus visible.
8. **Focus.** Visible `:focus-visible` indicator with sufficient contrast; never remove outlines without a replacement.
9. **Validate.** HTML validator, axe or Lighthouse, keyboard pass, 320 px reflow and 200 % zoom.

## Output

Markup and styles in the project's structure, and for reviews a findings list (location, issue, rule, fix).

## Edge cases

* Browser support constraints: check feature availability (for example on MDN compatibility tables) and provide fallbacks.
* Third-party widgets with poor semantics: wrap or replace; document residual issues.

## Acceptance criteria

* Landmarks and heading structure are present and logical.
* Every form control has a programmatic label.
* No literal design values where tokens exist.
* Layout works at 320 px width and 200 % zoom without horizontal scrolling for text content.

## Sources

* MDN Web Docs (HTML, CSS, accessibility): https://developer.mozilla.org/
* WCAG 2.2: https://www.w3.org/TR/WCAG22/
* web.dev, responsive design: https://web.dev/
