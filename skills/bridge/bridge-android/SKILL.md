---
name: bridge-android
description: >-
  Design, review or build Swissquote Android phone screens with the Bridge 2.0 design system and Material 3 Expressive. Use this skill for any Swissquote or PostFinance Android work: phone mockups in Figma, Jetpack Compose screens, Material theme mapping, design critique, handoff specs, component choice (native vs custom Bridge), trade tickets, banking flows, font scaling, TalkBack, edge to edge, predictive back. Trigger on mentions of Android, Compose, Material, M3, Kotlin, Play Store, "écran Android", even when Bridge is not named. For Android tablets use bridge-tablet, for Android foldables use bridge-foldables.
---

# Bridge on Android (phone)

You help designers and developers produce Swissquote Android screens that behave like a good Material 3 app and look like Swissquote. Material owns structure and behaviour (navigation, sheets, back, motion, window insets). Bridge owns colour, typography, icons, content and the finance specific components. Android is not a port of the iOS design: bars, back navigation, dialogs, radii and heights differ on purpose.

Read `references/bridge-foundations.md` before choosing any colour, size or text style.

## Sources, in order of authority

1. Live Figma files through the Figma MCP when connected: Foundations (`jnTucpT3dDk7LLnbKjXavK`, including the `Android` and `05mobile` collections), Mobile library 2.0 (`ZaE1qygacCTQHZBSC9YEB7`). Each component set has a structured description with an `Android:` line naming the Compose API. Read it before placing the component.
2. This skill and its reference file.
3. Material 3 guidelines and developer.android.com for anything not covered. This file reflects Material 3 Expressive (Compose Material 3 1.4 stable, 1.5 beta). Check the current docs for API status.

## Step 1: pick the origin of each component

| Origin | Name suffix | What it means | In code |
|---|---|---|---|
| Native, Bridge themed | `[Native]` | The Material component, coloured by the Bridge theme. Set `platform=android` | Compose Material 3 component. Never a custom rebuild |
| Custom Bridge | `[Mobile]` | Bridge designs it, same on iOS, Android and web | Custom composable built on Bridge tokens. Identical instance on both platforms |
| Native as is | none | System component with no Bridge styling | System API. Use the Material 3 Design Kit in mockups |

Native, Bridge themed and its Compose API:

| Component | Compose |
|---|---|
| Top app bar | `TopAppBar`, `LargeTopAppBar` (64 and 112 dp) |
| Tab bar | `NavigationBar` or `ShortNavigationBar`; `NavigationSuiteScaffold` for adaptive apps |
| List item | `LazyColumn` + `ListItem` (56 and 72 dp) |
| Switch | `Switch` with `SwitchDefaults.colors` (52 x 32) |
| Text field | `OutlinedTextField` with label, supportingText, isError (56 dp, radius 4) |
| Search | `SearchBar`, `DockedSearchBar` |
| Bottom sheet | `ModalBottomSheet` (radius 28) |
| Segmented control | connected `ButtonGroup` with `ToggleButton`; `SingleChoiceSegmentedButtonRow` still works |
| Menu | `DropdownMenu` (radius 16) |
| Toolbar | `HorizontalFloatingToolbar` or `FlexibleBottomAppBar`; `BottomAppBar` is no longer recommended |
| Full screen modal | `Dialog(usePlatformDefaultWidth = false)` + `TopAppBar` |
| Popover | `TooltipBox` with `RichTooltip` |
| Side navigation | `WideNavigationRail`; the navigation drawer is not used in new screens |
| Side sheet | `SupportingPaneScaffold` or a modal side sheet |
| Text | `MaterialTheme.typography` with Bridge fonts in sp |

Custom Bridge: Buttons (product, brand, destructive, Buy-Sell, link), Badges, Tab Menu (`PrimaryTabRow` themed), Checkbox and Radio, Alert and Toast (`SnackbarHost` with a Bridge styled Snackbar), Tag and Chip (`FilterChip`, `InputChip` themed), Card (`OutlinedCard`, `ElevatedCard` themed), Avatar, Progress, Divider, Accordion, Tooltip, Step indicator, Stepper, Combobox, Chart, Table row (draft), Summary, Empty state, Skeleton, finance and trading blocks.

Native as is: `AlertDialog`, date and time pickers, exposed dropdown menus, Android Sharesheet, photo picker, notifications, widgets (Glance), IME, pull to refresh.

Android only concepts with no Bridge component: FAB and FAB menu. Do not add a FAB to mirror an iOS toolbar; use it only when a screen has one dominant creation action and no bottom button.

If a concept has no component, do not invent one. Use the closest documented component, mark the frame name with `[gap]` and report it.

## Step 2: build the screen structure

- Mockup frame: 412 dp wide is a sound default for a compact window. Compact means width under 600 dp. Content margin 16 dp (`mobile/spacing/screen-margin/compact`). Vertical rhythm 12 between cards, 16 between form fields.
- Edge to edge is the default: content draws behind the status bar and the gesture navigation bar; bars and bottom buttons consume `WindowInsets`. The reference values 40 dp (status) and 24 dp (gesture bar) are for mockups only.
- Top: `Top app bar [Native]` 64 dp, large 112 dp on root screens when a large title helps. Title aligned to the start. Up arrow on pushed screens, close icon on full screen dialogs.
- Root navigation: `Tab bar [Native]` platform=android with Home, Trade, Bank, Plan, same order as iOS, labels always visible, pill active indicator. Check the 64 dp short bar against the 80 dp token before handoff.
- Back: every screen supports the system back gesture and predictive back. Bottom sheets, dialogs and search close on back. Never add an iOS style "Back" text button.
- Lists: `ListItem` 56 dp one line, 72 dp two lines. Navigation rows do not need a chevron on Android unless the Bridge row shows one for consistency inside a card.
- Bottom actions: one primary button, full width, above the gesture bar inset. Buy and Sell sit side by side.
- Elevation uses tonal surfaces and the `mobile/elevation/level0..5` tokens (0, 1, 3, 6, 8, 12 dp). No glass on Android (`mobile/glass/material` is none).

## Step 3: apply Bridge

Theme mapping. The `Android` collection in Foundations maps Bridge to the Material 3 colour roles (`Material3/Theme/primary`, `surface`, `surface-container-*`, `outline`, `error` ...) in four modes: Light, Dark, PF Light, PF Dark. Build the `ColorScheme` from it once and let Material components read it. Key consequences:
- `primary` is neutral ink (#323232 light, #f6f7f9 dark), not orange. Product actions are neutral. Orange appears through Bridge brand tokens only.
- `tertiary` is transparent by design. Do not rely on Material tertiary components.
- Dynamic colour (Material You wallpaper theming) is off. Swissquote colours are fixed.
- `[Mobile]` components read Bridge semantic tokens directly (`color/action/product/*`, `color/control/*`), not the Material scheme.

Colour rules
- Screen background `background/canvas/default`, cards `background/surface/default/base`, dividers `border/subtle`.
- `action/product/*` for product actions, `action/brand/*` for welcome and offers, `action/trade/buy|sell` for orders only, `action/destructive/*` for irreversible actions. One primary button per screen.
- No hover on touch. States are default, pressed, focus, disabled, submitting. Disabled follows `mobile/opacity/disabled-container` 0.12 and `disabled-content` 0.38 on native components.
- Design Light and Dark, and PF modes when the screen ships in the PostFinance app.

Typography. Bridge sizes are kept; each Bridge style is assigned to a Material role so font scale applies. Sizes in sp.

| Bridge style | Material role |
|---|---|
| display/lg | displaySmall |
| heading/2xl | headlineLarge |
| heading/xl | headlineMedium |
| heading/lg | headlineSmall |
| heading/md | titleLarge |
| heading/sm | titleMedium |
| paragraph/lg | bodyLarge |
| paragraph/md | bodyMedium |
| paragraph/sm | bodySmall |
| label/lg | labelLarge |
| label/md | labelMedium |
| label/sm, caption/sm | labelSmall |

Layouts hold at 200 percent font scale (non linear scaling applies above 100 percent): text wraps, rows grow, pairs stack. Figures never truncate. Amounts use tabular figures.

Sizes and shape
- Minimum touch target 48 x 48 dp. A 32 dp button or chip keeps a 48 dp target.
- Mobile button sizes: sm 32, md 40, lg 48. Use lg for the main action.
- Radius: sheets and dialogs 28, menus 16, text fields 4, cards 12, capsules full.

## Step 4: patterns that carry financial risk

- Trade ticket: instrument header, Buy or Sell choice, order type and validity rows, quantity `Stepper [Mobile]`, estimated cost and fees in `Summary [Mobile]`, then `Buttons Buy-Sell [Mobile]` size lg. Label states the order ("Buy 20 NESN").
- Review and confirm: amount, fees, account and timing before commitment; confirm with the verb of the action; biometric or OTP step-up after review (`BiometricPrompt`).
- Destructive: `AlertDialog` with Bridge colours, title naming the object, one sentence of consequence, confirm repeats the verb, dismiss on the left of confirm.
- Short tasks: `ModalBottomSheet`. Multi step tasks: full screen dialog with a top app bar and a close icon. Never stack sheets.
- Feedback: `Toast [Mobile]` rendered as a Bridge Snackbar (4 s, 6 s with action, above the navigation bar). Regulatory and risk messages use `Alert [Mobile]` inline, never a snackbar.
- States: loading (`Skeleton`), empty, error, offline on every data screen.
- Haptics from tokens: `SEGMENT_TICK` on selection, `CONFIRM` on success, `REJECT` on error, `LONG_PRESS` on long press.
- Motion: Material expressive scheme with springs; short duration 150 ms. Honour the system "Remove animations" setting.
- Sensitive screens (balances, card PIN, OTP) set `FLAG_SECURE` where the product requires it; mention it in the handoff.

## Step 5: accessibility on Android

- WCAG 2.2 AA: text 4.5:1, large text and UI parts 3:1. Aim for AAA on trade confirmation, authentication and fee disclosure.
- TalkBack: merge each row into one node with a full sentence (`Modifier.semantics(mergeDescendants = true)`). Icon only buttons need `contentDescription`. Headings use `heading()`. State changes announce through live regions.
- Up and down are never colour only.
- Support font scale to 200 percent, display size changes, high contrast text, colour correction and switch access. Focus order follows reading order; visible focus for keyboards.

## Working in Figma

- Instances from the Mobile library, never detached. Variant values lowercase; booleans start with `show`, text with `edit`, swaps with `pick`. Use slots.
- Set `platform=android` on every `[Native]` instance. `[Mobile]` instances stay identical to iOS.
- To convert an iOS screen: switch `[Native]` instances to android, replace native as is parts with the Material kit, then rework what differs (top app bar title alignment, back, dialog buttons, heights, radii). Do not just reskin.
- Bind fills, strokes, radius and spacing to Foundations variables with the `05mobile` mode set to Android.

## Output formats

Design or spec request: top to bottom structure, each line naming the component, origin, key properties, tokens, then states, accessibility and gaps.

```
Screen: Transfer review (Android, compact, 412 dp)
1. Top app bar [Native] platform=android, title "Review transfer", up arrow
2. Summary [Mobile] rows: From, To, Amount, Fees, Execution date
3. Alert [Mobile] status=info, "Transfers after 16:00 are executed the next business day."
Bottom: Buttons product [Mobile] style=primary size=lg(48), "Confirm transfer", above gesture inset
States: submitting, success (Result), rejected, offline
```

Code request: Jetpack Compose with Material 3 components, a `BridgeTheme` wrapping `MaterialTheme` (colour scheme from the Android collection, typography from the mapping), Bridge composables for `[Mobile]` components, `Scaffold` with insets. No literal colour, no fixed text size in dp.

Review request: findings by severity with the rule broken and the fix, covering origin, tokens, structure, back behaviour, states, accessibility and copy.

## Final check

- Right origin for each component; Material components in code for every `[Native]`.
- No raw hex, no primitive token, no opacity tint, no dynamic colour.
- One primary action; brand orange only where allowed; Buy blue, Sell red.
- 48 dp targets; 200 percent font scale; light and dark.
- Edge to edge with insets; system back and predictive back work everywhere.
- Fees, risks and consequences visible before any financial commitment.
- Loading, empty, error and offline states defined.
- Nothing copied from iOS that Android does differently (glass, back label, sheet radius, switch shape).
