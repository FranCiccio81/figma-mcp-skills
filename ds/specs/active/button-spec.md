# Button — Spec

**Figma:** [Buttons frame](https://www.figma.com/design/YMXQcB0QWivNJGwH3jJUI7/Foundations--Laboratoire-Innotech-International?node-id=729-17557)
**Last updated:** 2026-03-29

---

## User Story

As a developer, I want a Button atom that exposes all Bridge DS types, colours, sizes, and states so that I can compose consistent, accessible call-to-action controls across all product surfaces.

## Component Tree

```
┌─────────────────────────────────────────────────┐
│ Button (<button>)                               │
│  ├── [leadingIcon]   (optional ReactNode)       │
│  ├── label           (children — required)      │
│  └── [trailingIcon]  (optional ReactNode)       │
└─────────────────────────────────────────────────┘
```

**Atomic level:** atom
**Pattern:** single component

## File Structure

```
src/components/atoms/Button/
├── Button.tsx
├── Button.test.tsx
├── Button.stories.tsx
├── Button.figma.tsx       ← Code Connect (node 729:17557)
├── doc.md
└── index.ts
```

## Figma Variant Matrix

From Figma metadata (node 729:17574):

| Prop | Figma values | React prop |
|------|-------------|------------|
| `Type` | `Solid` \| `Outline` \| `Faded` | `type` |
| `Colour` | `Primary` \| `Danger` \| `Neutral` | `colour` |
| `Size` | `Small` \| `Regular` \| `Large` | `size` |
| `State` | `Default` \| `Hover` \| `Pressed` \| `Disabled` | CSS pseudo-classes + `disabled` attr |

**Icon configurations** (showcase): Default · Single Icon Trailing · Single Icon Leading · Double Icon · Disabled

## API

### Props

| Prop | Type | Default | Required | Description |
|------|------|---------|----------|-------------|
| `type` | `'solid' \| 'outline' \| 'faded'` | `'solid'` | No | Visual style (filled / bordered / tinted) |
| `colour` | `'primary' \| 'danger' \| 'neutral'` | `'primary'` | No | Colour scheme |
| `size` | `'small' \| 'regular' \| 'large'` | `'regular'` | No | Size tier (32 / 40 / 56px height) |
| `disabled` | `boolean` | `false` | No | Disabled state — uses native `disabled` attr |
| `loading` | `boolean` | `false` | No | Loading state — shows spinner, suppresses clicks |
| `buttonType` | `'button' \| 'submit' \| 'reset'` | `'button'` | No | Native `<button type>` — renamed to avoid collision with `type` prop |
| `leadingIcon` | `ReactNode` | `undefined` | No | Icon rendered before label (Figma MCP localhost asset) |
| `trailingIcon` | `ReactNode` | `undefined` | No | Icon rendered after label (Figma MCP localhost asset) |
| `fullWidth` | `boolean` | `false` | No | Stretches to 100% container width |
| `onClick` | `(event: React.MouseEvent<HTMLButtonElement>) => void` | `undefined` | No | Click handler |
| `className` | `string` | `undefined` | No | Extra CSS classes — do NOT pass variant classes; those are controlled by props |
| `children` | `ReactNode` | — | **Yes** | Button label |

> **Note on prop naming:** Figma uses `type=Solid|Outline|Faded`. In React, `type` is a reserved HTML button attribute, so the visual type becomes `type` (safe because we expose the native attribute as `buttonType`). Alternatively, rename to `variant` — decision for author (see Blockers).

### Events

| Event | Payload | Description |
|-------|---------|-------------|
| `onClick` | `React.MouseEvent<HTMLButtonElement>` | Fired on click; suppressed when `disabled` or `loading` |

## Dimensions (all confirmed from Figma)

| Size | Height | Padding H | Padding V | Gap | Icon size | Typography |
|------|--------|-----------|-----------|-----|-----------|------------|
| Small | **32px** ✅ | **12px** ✅ | **8px** ✅ | **6px** ✅ | **14px** ✅ | `Caption/Semi Bold` 12px/600/18px |
| Regular | **40px** ✅ | **18px** ✅ | **12px** ✅ | **6px** ✅ | **16px** ✅ | `Paragraph 01/Semi Bold` 14px/600/16px |
| Large | **56px** ✅ | **20px** ✅ | **14px** ✅ | **6px** ✅ | **20px** ✅ | `Paragraph 03/Semi Bold` 18px/600/22px |

> Icon size and typography both scale with button size — confirm in implementation.

**Border radius:** 5px ✅ (confirmed: `rounded-[5px]`, all sizes)

## Token Mapping

### Confirmed from Figma variables

| Figma Token | Hex | Bridge CSS Token | Status |
|-------------|-----|-----------------|--------|
| `Primary/600` | #2563EB | `--color-action-primary` | ⚠️ verify name |
| `Primary/700` | #1D4ED8 | `--color-action-primary-hover` | MISSING TOKEN |
| `Primary/800` | #1E40AF | `--color-action-primary-pressed` | MISSING TOKEN |
| `Primary/50` | #EFF6FF | `--color-action-primary-faded` | MISSING TOKEN |
| `Primary/100` | #DBEAFE | `--color-action-primary-faded-hover` | MISSING TOKEN |
| `Danger/500` | #EF4444 | `--color-feedback-error` | ⚠️ verify name |
| `Danger/600` | #DC2626 | `--color-feedback-error-hover` | MISSING TOKEN |
| `Danger/700` | #B91C1C | `--color-feedback-error-pressed` | MISSING TOKEN |
| `Danger/50` | #FEF2F2 | `--color-feedback-error-faded` | MISSING TOKEN |
| `Grey/300` | #D1D5DB | `--color-border-default` | MAPPED |
| `Grey/100` | #F3F4F6 | `--color-surface-disabled` | MISSING TOKEN |
| `Grey/400` | #9CA3AF | `--color-text-disabled` | MAPPED |
| `Shades/White` | #FFFFFF | `--color-surface-default` | MAPPED |

### State matrix (type × colour)

| Type | Colour | Default bg | Hover bg | Pressed bg | Text | Border |
|------|--------|-----------|----------|-----------|------|--------|
| Solid | Primary | `Primary/600` | `Primary/700` | `Primary/800` | `White` | — |
| Solid | Danger | `Danger/500` | `Danger/600` | `Danger/700` | `White` | — |
| Solid | Neutral | `Grey/200`? | `Grey/300`? | `Grey/400`? | `Grey/700`? | — |
| Outline | Primary | transparent | transparent | `Primary/50`? | `Primary/600` | `Grey/300` |
| Outline | Danger | transparent | transparent | `Danger/50`? | `Danger/500` | `Grey/300` |
| Outline | Neutral | transparent | transparent | `Grey/50`? | `Grey/700` | `Grey/300` |
| Faded | Primary | `Primary/50` | `Primary/100` | `Primary/200`? | `Primary/600` | — |
| Faded | Danger | `Danger/50` | `Danger/100` | `Danger/200`? | `Danger/500` | — |
| Faded | Neutral | `Grey/50` | `Grey/100` | `Grey/200`? | `Grey/700` | — |
| Any | Any | `Grey/100` (disabled) | — | — | `Grey/400` (disabled) | — |

> ⚠️ Solid/Neutral, Outline/*, Faded/Neutral pressed states are inferred — confirm with `get_design_context` on those nodes before dev.

### Missing component-tier tokens (require DS team approval)

| Token needed | Value | Category |
|---|---|---|
| `component.button.height.small` | 32px | Dimension |
| `component.button.height.regular` | 40px | Dimension |
| `component.button.height.large` | 56px | Dimension |
| `component.button.padding-x.small` | **12px** ✅ | Spacing |
| `component.button.padding-x.regular` | **18px** ✅ | Spacing |
| `component.button.padding-x.large` | **20px** ✅ | Spacing |
| `component.button.padding-y.small` | **8px** ✅ | Spacing |
| `component.button.padding-y.regular` | **12px** ✅ | Spacing |
| `component.button.padding-y.large` | **14px** ✅ | Spacing |
| `component.button.radius` | **5px** ✅ | Border radius |
| `component.button.gap` | **6px** ✅ | Spacing |
| `component.button.icon-size.small` | **14px** ✅ | Dimension |
| `component.button.icon-size.regular` | **16px** ✅ | Dimension |
| `component.button.icon-size.large` | **20px** ✅ | Dimension |
| `color.action.primary-hover` | `Primary/700` #1D4ED8 | Color |
| `color.action.primary-pressed` | `Primary/800` #1E40AF | Color |
| `color.action.primary-faded` | `Primary/50` #EFF6FF | Color |
| `color.feedback.error-hover` | `Danger/600` #DC2626 | Color |
| `color.feedback.error-pressed` | `Danger/700` #B91C1C | Color |
| `color.surface.disabled` | `Grey/100` #F3F4F6 | Color |

## Acceptance Criteria

### Must Have

- [ ] AC-1: GIVEN `type="solid" colour="primary"` WHEN rendered THEN bg=`--color-action-primary` text=`--color-surface-default`
- [ ] AC-2: GIVEN `type="solid" colour="danger"` WHEN rendered THEN bg=`--color-feedback-error` text=white
- [ ] AC-3: GIVEN `type="outline"` WHEN rendered THEN transparent bg, `--color-border-default` border, coloured text per `colour` prop
- [ ] AC-4: GIVEN `type="faded" colour="primary"` WHEN rendered THEN bg=`Primary/50`, text=`--color-action-primary`
- [ ] AC-5: GIVEN `disabled={true}` WHEN rendered THEN native `disabled` attr set, bg=`--color-surface-disabled`, text=`--color-text-disabled`, cursor=not-allowed
- [ ] AC-6: GIVEN `disabled={true}` WHEN clicked THEN onClick is NOT fired
- [ ] AC-7: GIVEN any button WHEN hovered THEN background shifts one shade darker (type-dependent)
- [ ] AC-8: GIVEN any button WHEN focused via keyboard THEN visible focus ring rendered (`:focus-visible`)
- [ ] AC-9: GIVEN `loading={true}` WHEN rendered THEN spinner visible, label hidden, click suppressed, `aria-busy="true"` set
- [ ] AC-10: GIVEN `leadingIcon` prop WHEN rendered THEN icon appears before label with 6px gap
- [ ] AC-11: GIVEN `trailingIcon` prop WHEN rendered THEN icon appears after label with 6px gap
- [ ] AC-12: GIVEN `fullWidth={true}` WHEN rendered THEN button is `width: 100%`
- [ ] AC-13: GIVEN no `buttonType` prop WHEN rendered THEN native `type="button"` is set (no accidental form submit)
- [ ] AC-14: GIVEN `size="small"` WHEN rendered THEN height=32px; `size="regular"` → 40px; `size="large"` → 56px

### Edge Cases

| Case | Expected Behavior |
|------|-------------------|
| Long label text | Single-line; text truncates with ellipsis; button does not expand beyond container |
| No children | Not supported; TypeScript enforces `children: ReactNode` (required) |
| Both icons + long label | Flex layout; icons stay pinned, label truncates |
| Disabled | `Grey/100` bg, `Grey/400` text, removed from tab order (native `disabled`) |
| Loading | Spinner replaces label (same space, no layout shift); button height fixed |
| Rapid clicks | No built-in debounce — caller's responsibility |
| `colour` + `type` mismatch | All 9 combinations are valid; no invalid state |

## Accessibility

- **Keyboard:** `Tab` to focus, `Enter` or `Space` to activate
- **Screen reader:** Announces `children` as label; `aria-busy="true"` on loading state; consider visually hidden `<span>` "Chargement..." for VoiceOver/NVDA if spinner has no label
- **ARIA:**
  - Native `<button>` — no `role` needed
  - Native `disabled` attr — removes from tab order, suppresses events. Add `aria-disabled="true"` too for belt-and-suspenders (redundant but harmless, WCAG-recommended)
  - `aria-busy="true"` when `loading={true}`
- **Focus ring:** `:focus-visible` only — `box-shadow: 0 0 0 3px Primary/300` (or Bridge semantic equivalent) — **never** `outline: none` without alternative. Verify ≥ 3:1 contrast vs background
- **Touch target:**
  - Large (56px) ✅ WCAG compliant
  - Regular (40px) ⚠️ borderline — add `min-height: 44px` on mobile breakpoint
  - Small (32px) ❌ — requires 6px top/bottom padding wrapper on mobile, or restrict to desktop only
- **Contrast:**
  - `White` text on `Primary/600` #2563EB: ~4.6:1 ✅ WCAG AA
  - `White` text on `Danger/500` #EF4444: ~3.9:1 ⚠️ fails 4.5:1 — use `Danger/600` #DC2626 as default or flag to design
  - `Grey/400` #9CA3AF on `Grey/100` #F3F4F6 (disabled): ~1.9:1 ❌ — acceptable for disabled per WCAG (exception for non-interactive state)
  - `Primary/600` #2563EB text on white (Outline/Faded): ~4.6:1 ✅
- **Motion:** `prefers-reduced-motion: reduce` → disable loading spinner animation (use static icon instead)

## Decisions

| Decision | Rationale |
|----------|-----------|
| Native `<button>` | Keyboard, ARIA, form semantics for free |
| `buttonType` for HTML type attr | Avoids naming collision with Figma `type` prop (Solid/Outline/Faded) |
| `type` prop = visual type (Solid/Outline/Faded) | Matches Figma variant naming exactly — Code Connect alignment |
| Native `disabled` + `aria-disabled` | Belt-and-suspenders: native removes from tab order; aria-disabled aids screen readers in non-JS environments |
| No polymorphic `as` prop | Bridge uses router-level navigation; Button is not an anchor |
| Icons as `ReactNode` | Assets from Figma MCP localhost payload — no icon library import |
| `type="button"` default for `buttonType` | Prevents accidental form submit |
| Pressed = `:focus-visible` CSS | CLAUDE.md rule: "Pressed" in Figma = `:focus-visible` in CSS |
| No internal debounce | Caller controls interaction; Button stays a pure primitive |
| BEM: `.button`, `.button--solid-primary`, `.button--large` | Matches Bridge CSS convention |

## Blockers

| Blocker | Type | Status | Owner |
|---------|------|--------|-------|
| `type` prop name conflicts with HTML `type` attr — use `type` (visual) + `buttonType` (native) OR rename to `variant` | Decision | OPEN | Author |
| 16 missing component-tier tokens (heights, padding, radius, gap, state colors) | Token | OPEN | DS team |
| Solid/Neutral, Outline/*, Faded/Neutral pressed bg tokens not confirmed from Figma | Context | OPEN | Author — call get_design_context on those nodes |
| Small/Large padding-x and padding-y values inferred, not confirmed | Context | **RESOLVED** — Small: 12px H / 8px V; Large: 20px H / 14px V | — |
| Danger/500 on White = 3.9:1 contrast (< 4.5:1) — design decision needed | Accessibility | OPEN | Design + DS team |
| Spinner atom not yet implemented — `loading` state blocked | Dependency | OPEN | DS team |
| Focus ring token not yet defined (currently reuses Input/Focus pattern — should be semantic `--shadow-focus-default`) | Token | OPEN | DS team |

**Rule:** All blockers must be RESOLVED before running `/component dev`.

## Recommendations

| Priority | Recommendation | Rationale |
|----------|---------------|-----------|
| ~~Must~~ | ~~Confirm Small/Large padding via get_design_context on 729:17575 + 729:17607~~ | ✅ Resolved — all dimensions confirmed |
| Must | Decide `type` vs `variant` prop name before implementing | Rename costs 0 in spec, costs refactor if changed post-dev |
| Must | Confirm Danger/500 contrast decision with design team | 3.9:1 < WCAG AA minimum 4.5:1 |
| Should | Create Spinner atom before Button loading state | Avoid orphaned feature |
| Should | Define semantic focus token `--shadow-focus-default` | Decouples Button focus ring from Input/Focus |
| Should | Add touch-target wrapper utility for Small/Regular on mobile | Consistent with Input spec recommendation |
| Could | Add `iconOnly` variant with mandatory `aria-label` prop | Common pattern — defer until icon assets inventoried |

## Notes

<!-- Empty at creation. Filled during dev. -->

---

**Changes from v2 (2026-03-29):**
- Confirmed Small dimensions: h=32px, px=12px, py=8px, icon=14px, type=`Caption/Semi Bold` (12px)
- Confirmed Large dimensions: h=56px, px=20px, py=14px, icon=20px, type=`Paragraph 03/Semi Bold` (18px)
- Icon size and typography now documented as scaling per size tier
- Resolved Context blocker: Small/Large padding confirmed from Figma nodes 729:17575 + 729:17607
- Updated missing tokens table: all spacing/radius values now confirmed (✅), only color state tokens remain missing

**Changes from v1 (2026-03-28):**
- Corrected variant API: split into `type` (Solid/Outline/Faded) + `colour` (Primary/Danger/Neutral) — confirmed from Figma
- Corrected size naming: `Regular` (not `Default`) — confirmed from Figma
- Added `Faded` type — present in Figma, missing from v1
- Added `Neutral` colour — present in Figma, missing from v1
- Corrected primary button token: `Primary/600` (#2563EB), not `Primary/500` — confirmed from Figma
- Added complete state matrix for all type × colour combinations
- Confirmed: border-radius=5px, gap=6px, padding Regular=18/12px, icon-size=16px
- Resolved Context blocker: visual states now confirmed from Figma screenshot
- Added contrast analysis: Danger/500 on White = 3.9:1 (new OPEN blocker)
- Clarified `disabled` HTML attr + `aria-disabled` both recommended (per WCAG)
- Added `prefers-reduced-motion` requirement for loading spinner
