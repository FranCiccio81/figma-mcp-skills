---
name: semantic-html-and-css
description: >-
  Writes and reviews semantic HTML and maintainable CSS: landmarks, headings, forms and native
  controls, CSS architecture with tokens as custom properties, cascade layers, naming conventions
  (BEM or modules per project), responsive and fluid layouts with grid, flex, container queries and
  logical properties for right-to-left languages, and user preference media queries. Use when
  building or reviewing markup and styles, fixing layout or responsive issues, or setting a CSS
  architecture. Do not use for React state or data logic (use react-component-engineering).
license: MIT
metadata:
  version: "1.0.0"
  domain: engineering
  status: beta
  trust: internal
  sources: "WEB-MDN,W3C-WCAG22,W3C-APG,WEB-DEV"
  platforms: "web"
  last-reviewed: "2026-11-17"
---

# Semantic HTML and CSS

The right element gives accessibility, keyboard support and resilience for free. CSS should
express design decisions through tokens and adapt to content, language and user preferences.

## When to use

- Writing markup and styles for any web UI.
- Reviewing a stylesheet or a page for semantics and responsiveness.
- Defining a CSS architecture for a design system.

## Inputs

- Existing styling conventions, token files, browser support targets.
- Designs for each breakpoint or container size.

## Workflow

1. **Structure with landmarks:** `header`, `nav`, `main` (one per page), `aside`, `footer`;
   one `h1`, headings without skipped levels; lists for lists; tables for tabular data with
   `th` and `scope`.
2. **Forms:** every input has a visible `label`; group with `fieldset` and `legend`; use correct
   `type`, `inputmode` and `autocomplete`; error text linked with `aria-describedby`; do not
   disable paste.
3. **Interactive elements:** `button` for actions, `a href` for navigation; no click handlers on
   `div`; visible focus styles with `:focus-visible` meeting WCAG 2.2 focus requirements.
4. **CSS architecture:** tokens as custom properties at the root and per theme; components
   consume semantic tokens only; organise with `@layer` (for example reset, tokens, base,
   components, utilities); naming per project (BEM or CSS modules); avoid `!important` and deep selectors.
5. **Layout:** grid for two-dimensional layouts, flex for one dimension; container queries for
   components that live in different widths; fluid type and spacing with `clamp()` bounded by tokens.
6. **Internationalisation:** logical properties (`margin-inline-start`, `inset-inline-end`) so
   layouts mirror in RTL; no fixed widths on text.
7. **User preferences:** `prefers-reduced-motion`, `prefers-color-scheme`, `prefers-contrast`,
   `forced-colors` (keep borders and focus visible in Windows high contrast).
8. **Resilience:** content reflows at 320 CSS px width and 400 % zoom (WCAG 1.4.10); text spacing
   overrides do not break layout (WCAG 1.4.12).

## Outputs

HTML and CSS following the project's conventions, or a review with findings (element or selector,
issue, impact, fix).

## Edge cases

- **Design shows a div-based custom select:** prefer the native `select` or a component that
  follows the APG listbox or combobox pattern.
- **Tailwind projects:** map tokens in the Tailwind theme instead of arbitrary values like `[#0057ff]`.
- **Legacy browsers:** check support for container queries and `@layer` against the project's targets.
- **Icon fonts:** prefer inline SVG with accessible names or `aria-hidden`.

## Acceptance criteria

- [ ] One `main`, logical heading order, landmarks present.
- [ ] Every form control has a visible label and correct `autocomplete` where applicable.
- [ ] No interactive `div` or `span`.
- [ ] Styles consume semantic tokens; no raw design values.
- [ ] Layout works in RTL, at 320 px width and with reduced motion.

## Sources

- MDN Web Docs (HTML, CSS, accessibility): https://developer.mozilla.org/
- W3C WCAG 2.2: https://www.w3.org/WAI/standards-guidelines/wcag/
- WAI-ARIA Authoring Practices Guide: https://www.w3.org/WAI/ARIA/apg/
- web.dev, responsive design and CSS: https://web.dev/
