---
name: bridge-ios
description: >-
  Design, review or build Swissquote iPhone screens with the Bridge 2.0 design system, Apple HIG and iOS 27 Liquid Glass. Use this skill for any Swissquote or PostFinance iOS work: iPhone mockups in Figma, SwiftUI or UIKit screens, design critique, handoff specs, component choice (native vs custom Bridge), trade tickets, banking flows, Dynamic Type, VoiceOver, dark mode. Trigger on mentions of iOS, iPhone, SwiftUI, HIG, Liquid Glass, App Store, "app Apple", "écran iPhone", even when Bridge is not named. For iPad use bridge-tablet, for iPhone Duo use bridge-foldables.
---

# Bridge on iOS (iPhone)

You help designers and developers produce Swissquote iPhone screens that feel native to iOS and unmistakably Swissquote. The platform owns structure and behaviour (navigation, sheets, gestures, materials). Bridge owns colour, typography, icons, content and the finance specific components. When the two conflict, the platform wins on behaviour and Bridge wins on appearance.

Read `references/bridge-foundations.md` before choosing any colour, size or text style. It holds the token grammar, values and the data format rules.

## Sources, in order of authority

1. Live Figma files through the Figma MCP when connected: Foundations (`jnTucpT3dDk7LLnbKjXavK`), Mobile library 2.0 (`ZaE1qygacCTQHZBSC9YEB7`), web Components Library (`IL9AFNRoFqsJBPwjYlP3lT`). Every mobile component set has a structured description (Purpose, Use when, Do not use, iOS, Android, Accessibility, Properties, Tokens). Read it before placing the component.
2. This skill and its reference file.
3. Apple Human Interface Guidelines for anything not covered. Check the current HIG online for OS specifics; iOS changes every year and this file reflects iOS 27.

## Step 1: pick the origin of each component

Every concept has one of three origins. Choosing the wrong one is the most common mistake.

| Origin | Name suffix | What it means | In code |
|---|---|---|---|
| Native, Bridge themed | `[Native]` | The system component, tinted with Bridge tokens. Set `platform=ios` | SwiftUI or UIKit system component. Never a custom rebuild |
| Custom Bridge | `[Mobile]` | Bridge designs it because iOS has none or because it must match web and Android | Custom SwiftUI view built on Bridge tokens |
| Native as is | none | System component with no Bridge styling | System API. Use the Apple iOS kit in mockups |

Native, Bridge themed: Top app bar, Tab bar, List item, Switch, Text field, Search, Bottom sheet, Segmented control, Slider, Menu, Toolbar, Split button, Full screen modal, Popover, Text area, Password field, OTP entry, File upload, Text, Side navigation, Side sheet.

Custom Bridge: Buttons (product, brand, destructive, Buy-Sell, link), Badges, Tab Menu, Checkbox and Radio, Alert and Toast, Tag and Chip, Card, Avatar, Progress and Gauge, Divider, Button group, Accordion, Tooltip, Step indicator, Stepper, Rating, Combobox, Chart, Table row (draft), Summary, Empty state, Skeleton, finance and trading blocks.

Native as is: alert dialog (`.alert`), action sheet (`confirmationDialog`), pickers, date and time pickers, context menu, share sheet, notifications, widgets, keyboard, pull to refresh.

Why native first: only system containers receive Liquid Glass, size class adaptation, Dynamic Type, VoiceOver behaviour and future OS changes for free. A custom tab bar or sheet loses all of it and breaks on iPad and iPhone Duo.

If a concept has no component, do not invent one. Use the closest documented component, mark the frame name with `[gap]` and report it.

## Step 2: build the screen structure

- Frame: 402 pt wide for iPhone mockups. Content margin 16 (`mobile/spacing/screen-margin/compact`). Vertical rhythm 12 between cards, 16 between form fields.
- Top: `Top app bar [Native]` (NavigationStack toolbar). Standard height 44, large title 96. Large titles on root screens, inline titles on pushed screens.
- Root navigation: `Tab bar [Native]` with the four sections Home, Trade, Bank, Plan, in that order, with labels always visible. SwiftUI `TabView` with `Tab` items. Search uses `Tab(role: .search)` when a global search exists. The selected item is orange (`color/text/product/primary`). Tab bar and bottom toolbar never appear together.
- Liquid Glass belongs to the navigation layer only: bars, tab bar, sheets, menus, floating toolbars. Content (cards, rows, charts) stays on opaque Bridge surfaces. Glass has a defined edge and no drop shadow. Test every screen across the system transparency setting, from clear to tinted, and with Reduce Transparency on: the fallback surface is `mobile/glass/fallback/surface`.
- Lists: `List item [Native]` rows, 44 pt for one line and 60 for two lines, chevron for navigation, one trailing control at most, swipe actions for secondary actions.
- Bottom actions: one primary button, full width, above the home indicator inside the safe area (`safeAreaInset(edge: .bottom)`). Two actions stack vertically with the primary on top, or sit side by side for Buy and Sell.
- Respect safe areas and the Dynamic Island. The reference tokens 62 (top) and 34 (bottom) are for mockups only; code reads safe area insets.

## Step 3: apply Bridge

Colour
- Screen background `background/canvas/default`, cards and rows `background/surface/default/base`, dividers `border/subtle`.
- Buttons inside the product use `action/product/*` (dark ink). Orange `action/brand/*` is for welcome, offers and account opening. `action/trade/buy|sell` only for orders. `action/destructive/*` only for irreversible actions.
- One primary button per screen.
- No hover on touch: design default, pressed, focus, disabled and submitting. Pressed uses the `-pressed` tokens.
- Design light and dark (SQ Light and SQ Dark modes), and PF modes when the screen ships in the PostFinance app.

Typography
- Use Bridge text styles through the `Text [Native]` mapping so Dynamic Type works: `Font.custom(_:size:relativeTo:)`. Never fix sizes in code.

| Bridge style | iOS text style it scales with |
|---|---|
| display/lg, heading/2xl | largeTitle |
| heading/xl | title1 |
| heading/lg | title2 |
| heading/md | title3 |
| heading/sm | headline |
| paragraph/lg | body |
| label/lg | callout |
| paragraph/md, label/md | subheadline |
| paragraph/sm | footnote |
| label/sm | caption1 |
| caption/sm | caption2 |

- Layouts hold up to the largest accessibility size (scale cap 3.1): text wraps, rows grow, horizontal pairs stack. Figures never truncate; labels may.
- Amounts and quotes use `.monospacedDigit()`.

Sizes and shape
- Minimum hit area 44 x 44 pt for everything interactive, including chips and icon buttons. A 32 pt button keeps a 44 pt hit area.
- Mobile button sizes: sm 32, md 40, lg 48. Use lg for the main action of a screen.
- Radius: sheets and dialogs 34, menus 26, text fields 12, cards 12 (`radius/xl`), capsules full.

## Step 4: patterns that carry financial risk

- Trade ticket: instrument header, Buy or Sell segmented choice, order type and validity as list rows, quantity with `Stepper [Mobile]`, estimated cost and fees in a `Summary [Mobile]`, then `Buttons Buy-Sell [Mobile]` size lg full width. Label states the order ("Buy 20 NESN").
- Review and confirm: every order, payment or transfer shows amount, fees, account and timing before commitment. Confirmation uses the verb of the action. Step-up authentication (Face ID, OTP) happens after review.
- Destructive or irreversible: native `.alert` with the destructive role, title naming the object, one sentence of consequence, the safe action always present.
- Short tasks: `Bottom sheet [Native]` with `.presentationDetents([.medium, .large])`. Multi step tasks: `Full screen modal [Native]` (`.fullScreenCover` with its own NavigationStack). Never stack sheets.
- Feedback: `Toast [Mobile]` for confirmations (4 s, 6 s with an action, above the tab bar), `Alert [Mobile]` inline for messages that must be read. Regulatory and risk messages never go in a toast.
- Legal consent: `Legal sheet [Mobile]` with a sticky footer and an explicit checkbox.
- States: every data screen defines loading (`Skeleton`), empty (`Empty state`), error and offline.
- Haptics from the mobile tokens: `.selection` on pickers and segments, `.success` on a confirmed order, `.error` on a rejected one. No haptic for decoration.
- Motion: system transitions and springs (response 0.35). Honour Reduce Motion.

27 documented patterns exist in the Mobile library (Trade ticket, Review and confirm, Sign in and step-up, Multi-step form, System states, Search filter and sort, Portfolio overview, Instrument detail, Watchlists, Orders and positions, Card management and more). Start from the pattern when one matches.

## Step 5: accessibility on iOS

- WCAG 2.2 AA: text 4.5:1, large text and UI parts 3:1. Aim for AAA on trade confirmation, authentication and fee disclosure.
- VoiceOver: one element per row with a combined label ("Nestlé, 20 shares, CHF 1,690.00, up 0.8 percent"). Icon only buttons carry a label. Headings are marked as headers. Toasts are announced without moving focus.
- Up and down are never colour only: sign, arrow or word.
- Support Dynamic Type, Bold Text, Increase Contrast, Reduce Motion, Reduce Transparency, Differentiate Without Colour.
- Sheets move focus to the title on open and back to the trigger on close.

## Working in Figma

- Use instances from the Mobile library, never detach. Variant values are lowercase, booleans start with `show`, text properties with `edit`, instance swaps with `pick`. Fill containers through slots (Card, Bottom sheet, List item trailing).
- Bind every fill, stroke, radius and spacing to Foundations variables. Text uses Foundations text styles.
- Set `platform=ios` on every `[Native]` instance.
- Copy in English, sentence case, amounts as `CHF 1,234.50`.

## Output formats

Design or spec request: give the screen as a top to bottom structure, each line naming the component, its origin, the key properties and tokens.

```
Screen: Trade ticket, Nestlé (iPhone, 402 pt)
1. Top app bar [Native] platform=ios type=standard, title "Buy NESN", leading close
2. Segmented control [Native] segments=2 (Buy | Sell)
3. List item [Native] lines=one, title "Order type", value "Market", chevron
...
Bottom: Buttons Buy-Sell [Mobile] type=buy size=lg(48), full width, in safe area
States: loading, market closed, insufficient funds, submitting, success, rejected
Accessibility: ...
Open questions and gaps: ...
```

Code request: SwiftUI with system containers, a `ButtonStyle` per Bridge button family, colours and sizes read from the Bridge token layer. No literal hex, no fixed font size.

Review request: list findings by severity with the rule broken and the fix, covering origin, tokens, structure, states, accessibility and copy.

## Final check

- Each component has the right origin and `[Native]` ones are system components in code.
- No raw hex, no primitive token, no opacity tint.
- One primary action; brand orange only where allowed; Buy blue, Sell red.
- 44 pt hit areas; Dynamic Type to the largest size; light and dark.
- Fees, risks and consequences visible before any financial commitment.
- Loading, empty, error and offline states defined.
- Glass only on the navigation layer; no custom tab bar, sheet or alert.
