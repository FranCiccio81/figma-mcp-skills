# Bridge 2.0 foundations (shared reference)

Source of truth: Figma file "SQ • Bridge2.0 Foundations WIP [1.0]" (variables, text styles, effect styles, grid styles), read in November 2026. Values below are a snapshot. When a Figma MCP connection is available, read the live variables first and treat this file as a fallback.

## Contents
1. Token architecture and naming
2. Themes and modes
3. Colour: roles and key values
4. Typography
5. Spacing, padding, radius, sizes, strokes
6. Elevation, focus, blur
7. Icons
8. Mobile collection (05mobile)
9. Data formats and copy
10. Design principles in one page
11. Known gaps to confirm with the Design System Governance
12. Colour token index (exact names)

## 1. Token architecture and naming

Two levels only. Components point to semantic tokens. There is no component level by decision, with a few named exceptions (badge heights, drawer and modal widths).

| Level | Collections | Use |
|---|---|---|
| 1. Primitives | 01colorBase, 01colorBrandSQ, 01colorBrandPF, 01colorBrandDefault, 02sizeBase, 04typographyBase | Never referenced in designs or product code |
| 2. Semantic | 01colorSemantic, 02sizeSemantic, 03breakpoints, 04typographySemantic, 04typographyBrand | The only tokens a screen or component uses |
| Platform | 05mobile (modes iOS, Android), Android (Material 3 theme mapping) | Mobile only. Web and mobile share levels 1 and 2 |

Rules that hold on every platform:
- Tokens only. No raw hex, no primitive (`color/orange/500`, `numbers/n-4`) in a design or in code.
- No opacity to obtain a tint. Use the solid tint token of the ramp (for example `background/surface/status/info/tertiary`). Alpha tokens exist only for scrims and shadows.
- Token names are decided by design. Code aligns on them. Path separator is `/` in Figma; keep the same segments in code (`color-text-neutral-default`, `Color.Text.Neutral.default`).
- Sizes follow a t-shirt scale: `2xs, xs, sm, md, lg, xl, 2xl ...`.

Token names are not fully regular. Before writing a token name in a spec or in code, check it in section 12 (exact names) or in Figma. If the exact leaf is not listed, name the family (`color/control/field/*`) and write "leaf to read in Figma". A plausible but invented name is worse than an honest family reference because developers will search for it.

Colour token grammar, as a guide only: `color/{role}/{family}/{variant}[-{state}]`
- role: `background`, `text`, `icon`, `border`, `action`, `control`, `feedback`, `utility`, `data`, `shadow`
- status families: `error`, `warning`, `success`, `info`. Thematic families: `brand`, `product`, `crypto`, `insight`, `secure`, `caution`
- emphasis ladder inside a family: `primary`, `secondary`, `tertiary`, each with an `on-*` counterpart for content placed on it, plus `on-outlined`
- states: `-hover`, `-pressed`, `-focus`, `-disabled`, `-loading`, `-selected`

## 2. Themes and modes

`01colorSemantic` has six modes: SQ Light, SQ Dark, Default Light, Default Dark, PF Light, PF Dark.
- SQ is Swissquote. PF is the PostFinance white label: system colours equal SQ, the brand ramp and neutrals change (petrol, postgeld). Default is the unbranded grey theme.
- Brand font switches with the theme through `family/brand`: Swissquote CT (SQ), Inter (Default), Grotesk Roc (PF).
- Every screen is designed and checked in light and dark. Dark is a full mode of the semantic collection, never an inverted light screen.

## 3. Colour: roles and key values

Values are SQ Light | SQ Dark, for orientation only. Use the token.

Surfaces and text
| Token | Light | Dark | Use |
|---|---|---|---|
| background/canvas/default | #f7f9fd | #121212 | Page or screen background |
| background/canvas/neutral | #ffffff | #121212 | Plain canvas |
| background/surface/default/base | #ffffff | #323232 | Cards, sheets, rows |
| background/surface/subtle/base | #f4f4f5 | #26272b | Quiet grouping, table header |
| background/surface/selected/base | #eef0f3 | #535861 | Selected row or item |
| background/surface/emphasis/base | #121212 | #f6f7f9 | Inverse surface |
| background/overlay/scrim-weak, -medium, -strong | #121212 at 24, 48, 72 | #000000 at 16, 32, 56 | Scrims |
| text/neutral/strong | #121212 | #ffffff | Titles, key figures |
| text/neutral/default | #323232 | #f6f7f9 | Body |
| text/neutral/muted | #6a7079 | #eef0f3 | Secondary text |
| text/neutral/subtle | #5d6b98 | #b9c0d4 | Tertiary text, placeholders |
| text/neutral/disabled | #b9c0d4 | #4a5578 | Disabled |
| text/link | #004fc4 | #93baf8 | Links |
| border/subtle, default, strong | #eef0f3, #dcdfea, #717784 | #535861, #4a5578, #525866 | Dividers, field borders, emphasis |
| border/focus | #146af0 | #4388f3 | Focus ring |

Actions (`color/action/*`)
| Family | Primary background | Meaning |
|---|---|---|
| product | #323232 light, #f6f7f9 dark | Default for every action inside the logged in product. Neutral ink, not orange |
| brand | #fa5b35 light, #fb7c5d dark | Marketing, welcome, onboarding and offers only |
| destructive | #f95959 light, #ec0000 dark | Deletion, revocation, closure. Cancelling is not destructive |
| trade/buy | #146af0 light, #4388f3 dark | Buy orders only |
| trade/sell | #ec0000 light, #f95959 dark | Sell orders only |
| neutral, info, compact, custom | | Link buttons and compact buttons |

Each family exposes `primary`, `secondary`, `outlined`, `tertiary` (ghost) with `-bg`, `-border`, `on-*-text`, `on-*-icon` and states.

Market data: `data/up` #059669 | #10b978, `data/down` #fb2c36 | #ff6568. Buy is blue and sell is red; up is green and down is red. Never colour a Buy button green. Colour is never the only carrier of meaning: add a sign, an arrow or a label.

Status surfaces: `background/surface/status/{error|warning|success|info}/{primary|secondary|tertiary}`. Thematic families: `crypto` (violet), `insight` (indigo), `secure` (teal), `caution` (fuchsia), `brand` (orange).

Brand ramp SQ: 50 #fff7ed, 100 #feeeea, 200 #fdbdae, 300 #fc9d85, 400 #fb7c5d, 500 #fa5b35, 600 #e44200, 700 #c2410c, 800 #8a321d, 900 #692616.

## 4. Typography

Families: `family/brand` Swissquote CT for display and headings; `family/sans-serif` Inter for everything else; `family/numeric-value` DM Mono for aligned figures; `family/monospace` Courier Prime.

`04typographySemantic` has two modes: Medium (default) and Small (compact viewports). Only display and large headings change.

| Style | Font | Size / line (Medium) | Small mode | Weight | Tracking |
|---|---|---|---|---|---|
| display/2xl | Brand | 44 / 56 | 40 / 44 | 700 | -1 (Small -2) |
| display/xl | Brand | 40 / 48 | 36 / 40 | 700 | -1 |
| display/lg | Brand | 36 / 44 | 32 / 36 | 700 | -0.2 |
| heading/2xl (H1) | Brand | 32 / 38 | 28 / 34 | 600 | -0.2 |
| heading/xl (H2) | Brand | 28 / 34 | 24 / 30 | 600 | -0.2 |
| heading/lg (H3) | Brand | 22 / 28 | 20 / 26 | 600 | -0.2 |
| heading/md (H4) | Brand | 18 / 24 | same | 600 | 0 |
| heading/sm (H5) | Brand | 16 / 20 | same | 600 | 0 |
| heading/xs (H6) | Brand | 14 / 16 | same | 600 | 0 |
| subheading/lg, md, sm, xs | Inter | 16/24, 14/20, 12/18, 11/12 | same | 500 | 1.5, 1.5, 2, 1 (uppercase variants exist) |
| label/xl, lg, md, sm, xs | Inter | 18/24, 16/24, 14/20, 12/16, 10/12 | same | 500 | 0 |
| paragraph/xl, lg, md, sm | Inter | 18/24, 16/24, 14/20, 12/16 | same | 400, bold variant 600 | 0 |
| caption/md, sm, xs | Inter | 12/16, 11/12, 10/12 | same | 500 | 1, 0, 0 |

Usage: labels for controls and buttons, paragraphs for reading text, captions for metadata, subheadings for section eyebrows. Body default is paragraph/md on web and dense screens, paragraph/lg for reading.

## 5. Spacing, padding, radius, sizes, strokes

Base unit 4. All from `02sizeSemantic`.

| Scale | Values |
|---|---|
| spacing (gap between elements) | none 0, 3xs 1, 2xs 2, xs 4, sm 6, md 8, lg 10, xl 12, 2xl 16, 3xl 20, 4xl 24, 5xl 32, 6xl 40, 7xl 48, 8xl 80, 9xl 96, 10xl 128, 11xl 160 |
| padding (inside a container) | 4xs 2, 3xs 4, 2xs 6, xs 8, sm 10, md 12, lg 16, xl 20, 2xl 24, 3xl 32, 4xl 40, 5xl 48, 6xl 56, 7xl 80, 8xl 96 |
| margin (outside a block) | 3xs 2, 2xs 4, xs 6, sm 8, md 10, lg 12, xl 16, 2xl 20, 3xl 24, 4xl 28, 5xl 32, 6xl 40, 7xl 48, 8xl 80 |
| radius | none 0, 2xs 2, xs 4, sm 6, md 8, lg 10, xl 12, 2xl 16, 3xl 20, 4xl 24, 5xl 30, 6xl 36, 7xl 40, full 9999 |
| icon | 6xs 6, 5xs 8, 4xs 10, 3xs 12, 2xs 16, xs 20, sm 24, md 32, lg 36, xl 40, 2xl 48 |
| height (bars, tracks) | xs 4, sm 6, md 8, lg 12, xl 16, 2xl 20, 3xl 24, 4xl 30, 5xl 40, 6xl 48 |
| width (containers) | 2xs 320, xs 384, sm 480, md 560, lg 640, xl 720, 2xl 768, 3xl 960, 4xl 1024, 5xl 1280, 6xl 1440 |
| stroke | border 1, border-bold 2, focus-ring 2 |
| component | badges height xs 16, sm 20, md 24, lg 28; modal 480; drawer-floating 480; drawer-sticky 560 |

Pick the scale by intent: `spacing` between siblings, `padding` inside, `margin` around. Do not use a spacing token as a padding because the number matches.

## 6. Elevation, focus, blur

Effect styles: `regular-shadow/x-small`, `regular-shadow/medium`, `custom-shadows/{x-small|small|medium|large}`, `card-shadow/large`, `colored-shadows/*`, `backdrop-blurs/backdrop-blur-{sm 8|md 16|lg 24|xl 40}`.
Focus: `focus-rings/ring-primary` is a 2 px ring in the surface colour plus a 4 px spread in `shadow/focus/default` (#146af0). Variants exist for error and success. The ring needs 3:1 contrast against its surroundings.
Shadows are light and layered. Prefer a border (`border/subtle`) to a shadow for grouping; keep shadows for floating layers (menus, popovers, drawers, toasts).

## 7. Icons

BridgeIcons, built on Remix Icon, about 3000 icons in line and fill styles. Line is the default; fill marks a selected state. Drawn on 24 and 16 grids. Colour comes from `color/icon/*` tokens that mirror the text tokens (`icon/neutral/default`, `icon/status/success/primary` ...). Feature icons and pictograms are separate sets with their own `pictogram/*` sizes. App section icons (Home, Trade, Bank, Plan) come from the Mobile library component "Navigation icon [Mobile]".

## 8. Mobile collection (05mobile)

Two modes: iOS | Android. Values follow HIG and Material by decision.

| Token | iOS | Android |
|---|---|---|
| size/touch-target/min | 44 pt | 48 dp |
| size/icon-button/default | 44 | 48 |
| size/top-app-bar/standard, large | 44, 96 | 64, 112 |
| size/tab-bar/height | 49 | 80 |
| size/list-item/one-line, two-line | 44, 60 | 56, 72 |
| size/text-field/height | 56 | 56 |
| size/switch | 63 x 28 | 52 x 32 |
| size/control/md, lg | 40, 48 | 40, 48 |
| size/sheet/grabber | 36 x 5 | 32 x 4 |
| spacing/screen-margin/compact, regular | 16, 20 | 16, 24 |
| spacing/bar-item-inset | 21 | 16 |
| radius/sheet, dialog | 34 | 28 |
| radius/menu | 26 | 16 |
| radius/text-field | 12 | 4 |
| radius/control-capsule | full | full |
| size/list-pane/width-regular | 380 | 360 |
| size/form-sheet/width-regular | 540 | 560 |
| size/reading-width/max-regular | 680 | 680 |
| size/sidebar/width | 320 | n/a |
| size/navigation-rail/collapsed, expanded | n/a | 96, 220 |
| size/split-view/inner-display-region | 334 | n/a |
| size/safe-area/top-reference, bottom-reference | 62, 34 | 40, 24 (mockup reference only) |
| opacity/disabled-container, disabled-content | 0.3, 0.6 | 0.12, 0.38 |
| elevation/level0 to level5 | n/a | 0, 1, 3, 6, 8, 12 dp |
| motion/duration/short | 0.2 s | 150 ms |
| motion/scheme | system | expressive |
| motion/spring/default-response | 0.35 | n/a |
| haptic/selection, impact-light, success, error, long-press | .selection, .light, .success, .error, .medium | SEGMENT_TICK, VIRTUAL_KEY, CONFIRM, REJECT, LONG_PRESS |
| glass/material | regular | none |
| typography/max-scale | 3.1 | 2 |

Mobile decisions already taken: no hover on mobile, use `-pressed` tokens; Badge default size on mobile is md (24); the active navigation item on iOS is orange (`color/text/product/primary`); the app has four sections in this order: Home, Trade, Bank, Plan.

## 9. Data formats and copy

- Currency code before the amount: `CHF 1,234.50`. Period as decimal separator in every language on web and mobile. Two decimals.
- Abbreviate large numbers per language (EN `1M`, `5B`; FR `1 M`, `5 Md`; DE `1 Mio.`, `5 Mrd.`).
- Dates: long form for key dates (expiry, dividend), short numeric form in tables and dense lists. Times: 24 h in tables (`08:00 - 12:15`), locale form in sentences. On mobile, follow the device locale.
- IBAN in blocks of four, no padding on the last block: `CH93 0076 2011 6238 5295 7`.
- Phone: one field, auto formatting, country selector, minimum 8 characters.
- Figures in tables use tabular numerals (DM Mono or the tabular feature) and align right.
- Voice: friendly expert. Concise, clear, positive without hype. Second person, present tense, active voice, sentence case. Sentences under 20 words. "Turn on notifications", "Save changes?", "Your password is incorrect". Labels make sense on their own. A Buy or Sell label names the order: "Buy 20 NESN".
- Product copy is written in English first and localised (EN, FR, DE, IT and more). Leave room for 30 to 40 percent text expansion.

## 10. Design principles in one page

1. Finance for all: clarity over jargon, progressive complexity, nothing critical hidden.
2. Embrace guidance, celebrate progress: visible steps, milestones, no dead ends.
3. Consistent, clean and confident: hierarchy drives decisions, dense data stays legible, no decorative noise, one clear primary action, consistency across devices while respecting native conventions.
4. Design for trust: risks, fees and steps shown before commitment; AI is identifiable, explainable and controllable; the human confirms financial decisions.
5. Learn by doing: contextual help, demo and simulation.
6. Fast, fluid, scalable: perceived speed, skeletons, patterns that scale.
7. Design for everyone: WCAG 2.2 AA as the floor, AAA aimed at trade confirmation, authentication and fee disclosure; keyboard, screen reader and voice from the start.
8. Think big, start small, learn fast.
9. Build systems, not silos: use the library component, report gaps, do not fork.
10. Design for emotion, not just function: micro interactions and warm copy with restraint.

## 11. Known gaps to confirm with the Design System Governance

Flag these instead of guessing when a task depends on them:
- Heading weight: text styles use Swissquote CT Bold, typography variables say semibold 600.
- `03breakpoints/gutter` is 0 while the layout grid styles use 24 (web, tablet) and 16 (mobile). The Layout and Breakpoint pages are marked coming soon.
- Motion: five speed options are announced, values are not published as tokens for web. Mobile has `motion/duration/short` only.
- No button tokens for inverse surfaces inside a theme yet (the Buttons page says dark or inverse surface; dark themes themselves are covered).
- iOS sidebar width: token 320, documentation text says 300.
- Tab bar description lists Home, Markets, Orders, Inbox, Profile; the validated navigation is Home, Trade, Bank, Plan.

## 12. Colour token index (exact names)

All names are prefixed with `color/`. `{a|b}` means one of. Read from `01colorSemantic` in November 2026 (1945 variables).

Frequent mistakes to avoid
- Text status tokens have no `status` segment: `text/error/primary`, not `text/status/error/primary`. Icon, border and background do have it: `icon/status/error/primary`, `border/status/error/primary`, `background/surface/status/error/primary`.
- Trade tokens put the side in the leaf: `action/trade/buy-primary-bg`, not `action/trade/buy/primary-bg`.
- Badge and alert tokens carry the style: `control/badge/error/tonal/bg`, `feedback/alert/error/subtle-bg`. There is no `control/badge/error/bg`.

background
- `background/canvas/{default|neutral|inverse}`
- `background/overlay/{scrim-weak|scrim-medium|scrim-strong}`
- `background/surface/default/{base|base-hover|base-pressed|base-focus}`
- `background/surface/{subtle|neutral}/{base|base-hover|divider}`, `background/surface/selected/{base|base-hover}`, `background/surface/disabled/base`
- `background/surface/emphasis/{base|base-hover|base-subtle|base-subtle-hover}`
- `background/surface/status/{brand|error|warning|success|info|crypto|insight|secure|caution}/{primary|secondary|tertiary}[-alt]`
- `background/surface/drawer/{panel-bg|panel-border|panel-shadow|header-bg|header-border|footer-bg|footer-border|scrim}`, `background/surface/modal/panel-bg`
- `background/surface/collapsible/{panel-bg|panel-bg-hover|panel-border|panel-divider|focus}`
- `background/table/header/{default|disabled}`, `background/table/row/{default|hover|focus|selected|selected-hover|disabled}`

text
- `text/neutral/{strong|default|muted|subtle|disabled|on-emphasis}`
- `text/{error|warning|success|info|brand|crypto|insight|secure|caution}/{primary|secondary|tertiary|on-primary|on-secondary|on-tertiary}`
- `text/product/{primary|secondary|tertiary}`
- `text/link`, `text/link-{hover|pressed|visited|disabled|on-emphasis}`, `text/link-danger[-{hover|pressed|visited}]`
- `text/table/{header|row}/{default|disabled}`, `text/drawer/{title|subtitle|body|helper|disabled}`

icon
- `icon/neutral/{strong|default|muted|subtle|disabled|on-emphasis}`
- `icon/status/{error|warning|success|info}/{primary|secondary|tertiary|on-primary|on-secondary|on-tertiary}`
- `icon/{brand|product|crypto|insight|secure|caution}/{primary|secondary|tertiary|on-primary|on-secondary|on-tertiary}` (brand and product also `on-outlined`)

border
- `border/{subtle|default|strong|hover|pressed|selected|focus|disabled|read-only|transparent|white}`
- `border/status/error/{primary|secondary|tertiary|outlined}[-{hover|focus}]`, `border/status/{info|success|warning}/{subtle|default|strong}`
- `border/{brand|crypto|insight|secure|caution}/{default|subtle}`, `border/table/row/focus`

action
- `action/{product|brand|destructive}/{primary|secondary|outlined|tertiary}-{bg|border}[-{hover|pressed|focus|loading}]`
- `action/{product|brand|destructive}/on-{primary|secondary|outlined|tertiary}-{text|icon}`, plus `bg-disabled`, `border-disabled`, `text-disabled`, `icon-disabled`
- `action/product/icon-button-{bg|border}[-{hover|pressed|focus|selected|disabled}]`, `action/product/{icon|text}`
- `action/{product|neutral|info|destructive|custom}/link-{text|icon}[-{hover|pressed|disabled}]`, `link-focus`
- `action/trade/{buy|sell}-primary-{bg|border}[-{hover|pressed|focus|loading}]`, `action/trade/{buy|sell}-primary-text`, `action/trade/{buy|sell}-on-primary-icon`, `action/trade/{bg|border|text}-disabled`
- `action/compact/{stroke|ghost|white|custom}-{bg|border|icon}[-{hover|active|focus|disabled}]`
- `action/disabled/{base|strong}`

control
- Generic: `control/{bg|border|text|icon}` with `-hover`, `-focus`, `-disabled`; `control/{text-muted|text-strong|icon-strong|on-emphasis}`
- Field (text input, select, text area): `control/field/{bg|border|text|placeholder|label-text|label-required|icon|focus}`, `bg-{hover|disabled|readonly|selected}`, `border-{hover|active|disabled|readonly}`, `help-text[-{error|success|warning|info|disable}]`, `{danger|success|warning|info}-{bg|border|text}`
- Selection (checkbox, radio, switch): `control/selection/{neutral|brand|error|success}/{box-bg|box-border|check|checked-box-bg|checked-track-bg|unchecked-track-bg|checked-thumb-bg|unchecked-thumb-bg}` with `-hover`, `-pressed`, `-focus`, `-disabled`
- Badge: `control/badge/{neutral|info|success|warning|error|brand|crypto|insight|secure|caution}/{filled|tonal|outlined|dash|emphasis}/{bg|border|text|icon|dot}` (neutral has no tonal)
- Chip and tag: `control/chip/neutral/{bg|border|text|icon}[-{hover|pressed|selected|disabled}]`, `control/tag/neutral/{bg|border|text|icon}`
- Segmented: `control/segmented/{group-bg|group-border|item-bg|item-text|item-selected-bg|item-selected-text|item-focus}`
- Button group: `control/button-group/{group-bg|group-border|item-bg|item-text|item-selected-bg|item-selected-text}`
- Pagination: `control/pagination/{ghost|stroke}-{bg|border|text}[-{hover|pressed|selected|disabled}]`, `control/pagination/count-text`
- Picker and calendar: `control/picker/*`, `control/picker/calendar/*`. Slider: `control/slider/*`. Upload: `control/upload/*`. Breadcrumb: `control/breadcrumb/*`. Disclosure (accordion): `control/disclosure/*`

feedback
- `feedback/alert/{error|warning|success|info|neutral}/{subtle|outlined}-{bg|title|body|icon|link|focus}` (outlined also `-border`)
- `feedback/banner/{error|warning|success|info|neutral}/{filled|subtle|outlined}-{bg|title|body|icon|link|close-icon}`
- `feedback/tooltip/{primary|secondary}-{bg|border|title|description|icon}`

data, utility, shadow
- `data/up`, `data/down`, `data/chart/01..07`, `data/chart-area/01..07`, `data/graph/01..02`, `data/esg/*`
- `utility/divider/{line|text|band-bg|solid-bg}`, `utility/progress/*`, `utility/avatar/{neutral|blue|cyan|purple|red|yellow}/avatar-{bg|border|text|icon}`, `utility/indicator/{online|offline|busy|away|unread}-dot`, `utility/features/{family}/{filled|light|outline}-{bg|border|icon}`
- `shadow/focus/{default|error|success}`, `shadow/surface/{card|dropdown|popover|tooltip|drawer|modal|date-picker|floating-action}`, `shadow/elevation/0..5`

Dark mode note: in SQ Dark, `border/default` (#4a5578) on `background/surface/default/base` (#323232) is about 1.8:1. Field and control borders that must be perceivable need 3:1; flag it when a dark screen relies on that border alone.
