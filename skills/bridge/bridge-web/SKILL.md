---
name: bridge-web
description: >-
  Design, review or build Swissquote web interfaces with the Bridge 2.0 design system: eBanking and trading platforms, back office tools, dashboards, forms, tables, responsive pages, marketing pages. Use this skill for any Swissquote or PostFinance web work: Figma web mockups, React components, HTML and CSS, design critique, handoff specs, responsive behaviour, keyboard and screen reader accessibility, dark mode, theming. Trigger on mentions of web, desktop, browser, responsive, React, Storybook, CSS, breakpoint, dashboard, table, sidebar, eBanking, "plateforme web", even when Bridge is not named. For native apps use bridge-ios or bridge-android.
compatibility: Swissquote and PostFinance products only. Reads the Bridge Figma libraries through the Figma MCP when connected; otherwise uses the bundled foundations snapshot.
metadata:
  domain: bridge
  version: "0.2.1"
  status: beta
  scope: project
  trust: project-specific
  last-reviewed: "2026-11-17"
  origin: "bridge-platform-skills v0.2 (2026-11-12), imported 2026-11-17"
---

# Bridge on the web

You help designers and developers produce Swissquote web interfaces from Bridge 2.0. On the web Bridge is the whole system: there is no native layer to defer to, so the Bridge component, its tokens and its documented rules are the standard, completed by web platform conventions (semantic HTML, keyboard, WAI-ARIA patterns, WCAG 2.2).

Read `references/bridge-foundations.md` before choosing any colour, size or text style.

## When to use

* Any Swissquote or PostFinance web work: eBanking and trading platforms, back office, dashboards, forms, tables, marketing pages, React code, review, handoff.
* Not for native apps (`bridge-ios`, `bridge-android`). Generic web work outside Swissquote: `react-typescript-components`, `semantic-html-css`.

## Inputs

* Brief, Figma frame or existing code; breakpoints to deliver; themes; component status in the library.
* Whether the Figma MCP, Code Connect and Storybook are available.

## Edge cases

* Figma MCP not connected: use `references/bridge-foundations.md` as a snapshot, mark every value taken from it as "snapshot, verify in Figma", never invent a token leaf (name the family instead).
* No Bridge component for the concept: compose from documented components, name the frame with `[gap]` and report it (`bridge-design-system`, contribution section).
* The task depends on an open governance question (foundations section 11): flag it in the output instead of choosing silently.
* Screen for PostFinance: check PF Light and PF Dark modes, the brand font switches with the theme.
* Component marked work in progress: use it and say so in the handoff; planned: compose and mark `[gap]`.
* Buttons on an inverse surface inside a theme: no token set exists yet; do not place buttons there.

## Sources, in order of authority

1. Live Figma files through the Figma MCP when connected: Foundations (`jnTucpT3dDk7LLnbKjXavK`) and Components Library (`IL9AFNRoFqsJBPwjYlP3lT`). Code Connect mappings and Storybook when available: prefer the coded Bridge component and its props to anything rebuilt.
2. This skill and its reference file.
3. WAI-ARIA Authoring Practices and WCAG 2.2 for behaviour not documented in Bridge.

Each Bridge component page documents design guidelines, technical guidelines and examples in context. Read the page before using a component in a new way.

Official references:
* WAI-ARIA Authoring Practices: https://www.w3.org/WAI/ARIA/apg/
* WCAG 2.2: https://www.w3.org/TR/WCAG22/
* Radix UI primitives (used by the Bridge React components): https://www.radix-ui.com/primitives

## Step 1: use the component, check its status

| Status | Components |
|---|---|
| Stable, released | Alert, Notification and Toast; Badges; Checkbox and Radio; Date picker; Drawer; Pagination; Segmented control |
| Ready for core | Accordion; Avatar; Banner; Breadcrumb; Buttons; Button group; Progress bar; Slider; Tab menu; Select; Table; Text area; Text input; Toggle switch; Tooltip |
| Work in progress | Content divider; Popover; Tag and Chip; Charts; Dropdown items; Collapsible container; File upload; Modal; Rating; Stepper; Card |
| Planned | Multi select; AI; Chat; WYSIWYG editor; Empty state; Filters; Frame; Item; Tree |

Rules
- Use stable and ready components as they are. For work in progress components, use them and say so in the handoff. For planned ones, compose from existing components, name the frame with `[gap]` and report it. Do not create a look alike.
- The old "SQ Component" kit and the library marked "Don't use - Old DS" are not sources.
- Components are built with React on Radix UI primitives. In code, keep the primitive's behaviour (focus management, roles, keyboard) and style with tokens.
- Variant values are lowercase; booleans, text and swap properties follow the Figma property names. Never detach an instance.

Buttons, the most misused component
- Families: product (logged in platform), brand (marketing and public site), destructive, Buy-Sell (orders only), link, compact, icon button with notification.
- Styles: primary, secondary, outlined, ghost. Primary is the one action that moves the task forward: one per view, section or dialog. Secondary is a real alternative. Outlined stays visible on any surface (Export, Filter). Ghost is low emphasis (Cancel, row actions, dense toolbars).
- Sizes: xs 28, sm 32, md 36, lg 40, xl 44, 2xl 48. Default md in product UI, sm in dense tables and toolbars. Compact buttons 24, 20, 16 for constrained spaces. Do not mix sizes in a group.
- States: default, hover, pressed, focus, disabled, submitting. A submitting button keeps its width and shows a leading loader with its label.
- Prefer an active button with validation on click and errors on the fields to a disabled button with no explanation. If an action is blocked, say why.
- One family per view. Cancel is neutral, not destructive. Counters cap at 99+.
- A button triggers an action (`<button>`); navigation is a link (`<a>`), styled as a button only when it is the main call to action.
- Buttons work in every theme, SQ Dark included, because `action/*` tokens have dark values. What is missing is a button set for an inverse surface inside a theme (for example `background/surface/emphasis/base`): do not place buttons there.

## Step 2: layout and responsive behaviour

Breakpoints (collection `03breakpoints`)

| Mode | Viewport | Columns | Page padding | Space between sections | Grid style |
|---|---|---|---|---|---|
| Large | 960 to 1440 and above | 12 | 32 | 40 | gutter 24, margin 32 |
| Medium | 640 to 959 | 8 | 24 | 32 | gutter 24, margin 32 |
| Small | 320 to 639 | 4 | 16 | 24 | gutter 16, margin 16 |

Content max width 1440. Above it, center the layout or let fluid data regions (tables, charts) grow while text stays capped. The typography collection has a Small mode: switch it at the Small breakpoint so display and large headings step down.

Application shell (desktop reference frame 1440 x 900, 4 px base grid)

| Shell | Navigation width | Use |
|---|---|---|
| Sidebar expanded | 272 | Default for platforms with many sections |
| Sidebar collapsed | 80 | Data heavy screens, user choice |
| Sidebar and submenu | 80 + 264 | Deep sections |
| Topbar | safe areas of 80 each side | Simple products, marketing |

Content starts 32 after the navigation, in a 12 column grid with 24 gutters.

Responsive rules
- Design the Small layout as a first class layout: single column, navigation in a drawer or bottom area, tables turned into stacked rows or with a pinned first column and horizontal scroll, filters in a drawer.
- Overlays: Modal 480 wide, Drawer floating 480, Drawer sticky 560. On Small they become full width sheets with a pinned footer.
- On Small, buttons are full width and stacked, size xl or 2xl, primary first. Touch targets reach at least 44 px there.
- Content reflows down to 320 px wide with no horizontal scroll, except data tables and charts. Zoom to 200 percent keeps everything usable.
- Line length for reading text about 45 to 90 characters; container widths come from `width/*` tokens.
- Density: product screens use paragraph/md (14 / 20) and md controls. Dense is allowed for professional trading tools with sm controls; never go below 12 px text or a 24 px target.

## Step 3: apply Bridge

- Page background `background/canvas/default`; panels and cards `background/surface/default/base` with `border/subtle`; quiet groups `background/surface/subtle/base`; table header `background/table/header/default`, row hover `background/table/row/hover`, selected row `background/table/row/selected`.
- Text `text/neutral/strong` for titles and key figures, `default` for body, `muted` for secondary, `subtle` for hints.
- Product actions use `action/product/*` (dark ink). Orange `action/brand/*` belongs to marketing and brand moments. Buy is blue, Sell is red, only for orders. Up is green, down is red, with a sign or arrow.
- Status uses the semantic families (`feedback/alert/*`, `feedback/banner/*`, `control/badge/*`). Tints are solid tokens, never opacity.
- Elevation: borders for grouping, shadows only for floating layers (menus, popovers, drawers, toasts, modals) with the effect styles.
- Themes: SQ Light, SQ Dark, Default, PF Light, PF Dark come from the same tokens. Expose tokens as CSS custom properties per theme and switch at the root; honour `prefers-color-scheme` unless the user chose a theme. Check every component in dark; the dark values are their own set.
- Icons: BridgeIcons, line style by default, 16, 20 or 24 px, coloured by `icon/*` tokens. Decorative icons are hidden from assistive technology; meaningful icons have a text alternative.
- Figures: tabular numerals, right aligned in tables, currency code before the amount (`CHF 1,234.50`), period as decimal separator.

## Step 4: interaction states and motion

- Every interactive component defines default, hover, pressed, focus visible, disabled, and where relevant selected, loading, read only, error.
- Focus: 2 px ring in `border/focus` (#146af0) with the focus ring effect style, 3:1 against its surroundings, shown on keyboard focus (`:focus-visible`), never removed.
- Hover is an enhancement: nothing is reachable by hover only. Tooltips also open on focus and close with Escape.
- Motion is short and functional (hover dissolve with ease out, drawers and modals sliding or fading). Bridge announces five speed options; when exact durations are not available as tokens, stay between 100 and 300 ms and flag it. Honour `prefers-reduced-motion`.
- Perceived speed: skeletons for content, inline loaders for actions, optimistic updates only where safe. Never optimistic for orders and payments.

## Step 5: patterns that carry financial risk

- Forms: label above the field, help text below, error text replaces help text and is tied to the field (`aria-describedby`), validation on blur and on submit, summary of errors at the top for long forms. One column. Use the right input types and `autocomplete`. IBAN, amount, date and phone follow the Bridge formats and are auto formatted in a single field.
- Review and confirm before any order, payment or transfer: amount, fees, account, timing. The confirm button uses the verb of the action. Step-up authentication after review.
- Destructive actions: confirmation in a modal naming the object and the consequence; destructive button; safe action present and focused by default.
- Tables: sortable headers as buttons with `aria-sort`, sticky header, numeric columns right aligned, row actions in a ghost icon button or menu, pagination with the Bridge component, empty, loading and error states. The filter system of the Table is under review: keep filters outside the table component in a toolbar or drawer.
- Feedback: toast for confirmations, alert or banner for messages that must be read, inline errors on fields. Regulatory and risk messages are never transient.
- Session and security: timeouts warn before expiry and let the user extend; sensitive values can be masked.

## Step 6: accessibility on the web

Baseline WCAG 2.2 AA, AAA aimed at trade confirmation, authentication and fee disclosure.
- Semantic HTML first: landmarks (`header`, `nav`, `main`, `aside`, `footer`), one `h1`, ordered headings, lists, tables with `th` and scope, `button` and `a` used for what they are.
- Keyboard: everything operable, logical tab order, no trap, skip link, Escape closes overlays, focus moves into a dialog on open and returns to the trigger on close, arrow keys inside composite widgets (tabs, menus, radio groups, segmented control) per WAI-ARIA patterns.
- Contrast: text 4.5:1, large text and UI parts 3:1. Colour never the only signal.
- Target size at least 24 x 24 CSS px (WCAG 2.2), 44 on touch layouts. Focus not obscured by sticky headers or footers.
- Names and states: icon buttons have accessible names, toggles expose pressed or checked, expandable items expose expanded, live regions announce toasts and async results politely, errors assertively when they block.
- Authentication does not rely on a cognitive test alone; allow paste and password managers.
- Language set on the page; content localised; layouts absorb 30 to 40 percent longer strings.

## Working in Figma

- Frames at 1440 (Large), 768 (Medium) and 390 (Small), with the Bridge layout grid styles applied. Add a 320 check for reflow on critical flows.
- Auto layout everywhere, with fills, strokes, radius, padding and gaps bound to Foundations variables and text bound to text styles. Set the variable mode for theme and for typography (Medium or Small) on the frame.
- Nudge 1 and big nudge 8; snap to the 4 px grid.
- Handoff: group finished work in a Section and mark it Ready for dev. Developers set Completed. A change after that shows as Changed.

## Output formats

Design or spec request

```
Screen: Payments to validate (web, Large 1440, shell: sidebar expanded 272)
Layout: 12 columns, padding 32, sections spaced 40
1. Page header: heading/xl title, paragraph/md description, Buttons product primary md "New payment"
2. Toolbar: Text input (search) md, Select md, Buttons product outlined md "Filter"
3. Table: columns ..., numeric right aligned, row action Compact button, Pagination
Responsive: Medium 8 columns, sidebar collapsed 80; Small single column, rows stacked, filters in Drawer, buttons full width xl
States: loading skeleton, empty, error, selected rows with bulk bar
Tokens: ...
Accessibility: landmarks, headings, keyboard path, announcements
Gaps and open questions: ...
```

Code request: React with the Bridge components when available, otherwise semantic HTML on Radix primitives styled with Bridge CSS custom properties. No literal hex, px values only through tokens, states and keyboard behaviour included, light and dark verified.

Review request: findings by severity with the rule broken and the fix, covering component use, tokens, hierarchy, responsive behaviour, states, accessibility and copy.

## Final check

- Bridge component instance, right family and status known; nothing detached or redrawn.
- Tokens only; no hex, no primitive, no opacity tint.
- One primary action per view; brand orange only in brand contexts; Buy blue, Sell red.
- Large, Medium and Small layouts defined; reflow at 320; zoom 200 percent.
- Hover, pressed, focus visible, disabled, loading and error states defined.
- Keyboard path complete; names, roles and states exposed; contrast checked in light and dark.
- Fees, risks and consequences visible before any financial commitment.
- Copy concise, sentence case, second person; formats per Bridge.
