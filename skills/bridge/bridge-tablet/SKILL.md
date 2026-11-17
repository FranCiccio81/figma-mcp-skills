---
name: bridge-tablet
description: >-
  Design, review or build Swissquote tablet and large screen layouts (iPad with iPadOS 27 windowing, Android tablets) with the Bridge 2.0 design system. Use this skill whenever a Swissquote or PostFinance screen must work on iPad, an Android tablet, a resizable window, split screen, landscape, or with keyboard and pointer: adapting phone screens to tablet, list detail and multi pane layouts, sidebar and navigation rail, form sheets, reading width. Trigger on mentions of tablet, tablette, iPad, iPadOS, large screen, regular width, medium or expanded window, NavigationSplitView, navigation rail, split view, multitasking, even when Bridge is not named.
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

# Bridge on tablets and large screens

You adapt Swissquote app screens to large windows. A tablet screen is neither a stretched phone nor the web app. The goal is to show more of the same product at once (list and detail, content and supporting pane) with the same destinations, the same components and the same hierarchy as on the phone.

Read `references/bridge-foundations.md` for tokens. The platform rules of `bridge-ios` and `bridge-android` still apply (origins, theme, typography mapping, accessibility). This skill adds what changes with width.

## When to use

* Swissquote or PostFinance screens on iPad, Android tablets, resizable windows, split screen, keyboard and pointer.
* Not for phone-only work (`bridge-ios`, `bridge-android`) or the web app (`bridge-web`).

## Inputs

* The phone design or spec of the screen, target platforms, the window size classes to support.
* Whether the Figma MCP is connected.

## Edge cases

* Figma MCP not connected: use `references/bridge-foundations.md` as a snapshot, mark every value taken from it as "snapshot, verify in Figma", never invent a token leaf (name the family instead).
* No Bridge component for the concept: compose from documented components, name the frame with `[gap]` and report it (`bridge-design-system`, contribution section).
* The task depends on an open governance question (foundations section 11): flag it in the output instead of choosing silently.
* Screen for PostFinance: check PF Light and PF Dark modes, the brand font switches with the theme.
* Never decide layout from the device model or orientation: use the window size class.
* A screen that gains nothing from width: constrain reading width (`size/reading-width/max-regular`) rather than stretching.

## Core rule: adapt to the window, never to the device

Decide layout from the size class of the app window. A tablet in split screen is a compact window; an iPad window can be resized freely in iPadOS 27; an Android app can run in a desktop window. Device model checks and orientation checks give wrong answers.

| Platform | Class | Window width | Layout family |
|---|---|---|---|
| iOS, iPadOS | compact | iPhone, narrow iPad window | Phone layout |
| iOS, iPadOS | regular | iPad, wide window | Sidebar, multi pane |
| Android | compact | under 600 dp | Phone layout |
| Android | medium | 600 to 839 dp | Rail, one pane (two when content is simple) |
| Android | expanded | 840 to 1199 dp | Rail or expanded rail, two panes |
| Android | large | 1200 to 1599 dp | Expanded rail, two or three panes |
| Android | extra large | 1600 dp and more | Same, with max widths |

Height matters too: a compact height window (landscape phone, short split) cannot afford large titles, tall bars or tall bottom sheets.

## Step 1: navigation

Same destinations and same order as the phone: Home, Trade, Bank, Plan. The selected destination survives every resize.

| | Compact | Larger |
|---|---|---|
| iPadOS | Tab bar | `Side navigation [Native]` platform=ios type=sidebar. SwiftUI `TabView` with `.tabViewStyle(.sidebarAdaptable)`: tabs at the top in compact windows, glass sidebar to the window edge in regular windows, collapsible by the user. `TabSection` for groups |
| Android | Navigation bar | `Side navigation [Native]` platform=android. Rail 96 dp with icon and label from medium; expanded rail 220 to 360 dp with labels beside icons on expanded and larger; a modal expanded rail on medium. `NavigationSuiteScaffold` switches automatically. No navigation drawer in new screens |

Use the system container on each platform. A hand built sidebar loses the automatic switch.

Widths from tokens: sidebar `mobile/size/sidebar/width` (320), rail collapsed 96, rail expanded 220.

## Step 2: choose a canonical layout per screen

| Layout | Use for | iPadOS | Android |
|---|---|---|---|
| List detail | Accounts and transactions, watchlist and instrument, orders, documents, inbox, settings | `NavigationSplitView` | `ListDetailPaneScaffold` (`NavigableListDetailPaneScaffold`) |
| Supporting pane | Instrument chart with order book or news, trade ticket beside the instrument, filters beside results | `.inspector` or a trailing column | `SupportingPaneScaffold` |
| Feed or grid | Markets browse, themes, product tiles, dashboards of cards | `LazyVGrid` with adaptive columns | `LazyVerticalGrid(GridCells.Adaptive)` |
| Single pane with a width cap | Forms, onboarding, legal text, articles | Centered column | Centered column |

Pane sizes from tokens: list pane `mobile/size/list-pane/width-regular` (380 iOS, 360 Android); reading and form column capped at `mobile/size/reading-width/max-regular` (680); screen margin `mobile/spacing/screen-margin/regular` (20 iOS, 24 Android). The detail pane takes the rest.

Layout rules
- Each pane scrolls on its own and has its own title. The list pane keeps the selected row highlighted (`background/surface/selected/base`).
- On the way down to compact, list detail collapses to a stack: the list first, the detail pushed. Selection and scroll position are preserved both ways.
- Never leave the detail pane empty on first load: select the first item or show an `Empty state [Mobile]` that explains what to pick.
- Text lines stay between about 45 and 90 characters. A full width paragraph or form on a 1200 dp window is a defect: cap the column.
- Cards reflow by adding columns, not by growing. Keep card content and padding identical to the phone.
- Grid reference from Foundations: 8 columns, gutter 24, margin 32 for tablet mockups (grid style `Layout/Grid-layout-tablet`).

## Step 3: presentations change with width

| Phone | Tablet |
|---|---|
| `Bottom sheet [Native]` for filters or details | `Side sheet [Native]` (iPadOS `.inspector` or `.sheet` with `.presentationSizing(.form)`; Android supporting pane or modal side sheet). Same content |
| `Full screen modal [Native]` | Form sheet centered, width `mobile/size/form-sheet/width-regular` (540 iOS, 560 Android), scrim behind. Stay full screen only for long multi step flows |
| Menu anchored to a button | Same, as a popover near the trigger |
| Action sheet from the bottom | Popover anchored to the trigger on iPadOS |
| Alert dialog | Same, centered, never stretched |
| Toast | Bottom, aligned to the content pane, max width about 480, not full width |
| Sticky full width bottom button | Button sized to its column or placed in the pane footer or toolbar. No 1000 pt wide buttons |
| Search | iPadOS `.searchable` in the toolbar or sidebar; Android docked search bar 360 dp wide in the top app bar |

Trade ticket on tablet: instrument detail in the main pane, ticket in a supporting pane or form sheet, so the chart and price stay visible while the order is built. Review and confirm stays a distinct step.

## Step 4: input and ergonomics

- Touch targets stay 44 pt and 48 dp. Larger screens do not justify smaller controls or web density.
- Pointer and trackpad: hover feedback exists on tablets with a pointer. iPadOS applies system hover effects to native controls; custom Bridge controls add a hover state with the `-hover` tokens. Keep pressed as the primary feedback.
- Keyboard: full tab order, visible focus ring (`border/focus`), Return submits, Escape closes sheets, shortcuts for frequent actions (search, new order) listed in the iPadOS shortcut overlay. Arrow keys move the list selection in list detail.
- Reach: in landscape, hands hold the lower corners. Keep frequent actions near the leading and trailing edges or in the navigation and toolbar, not in the top center.
- Drag and drop, multiple windows and Stage Manager are welcome where they serve a task (for example dragging an instrument to a watchlist) but are optional.
- Rotation and resize never lose state: form input, scroll position, selected item, open sheet.

## Step 5: iPadOS and Android specifics

iPadOS 27
- Windows resize freely. Test narrow widths; they fall back to compact and must show the phone layout with a tab bar.
- Liquid Glass sidebar extends to the window edge; content scrolls under bars. Glass stays on the navigation layer.
- Window controls occupy the top leading corner in windowed mode: keep toolbar items clear of them by using system toolbars.
- Dynamic Type applies as on iPhone; multi column layouts drop to fewer columns at accessibility sizes.

Android tablets
- Support every orientation and free form resizing. Apps on large screens are expected to be resizable and not locked to portrait.
- Use the Compose Material 3 adaptive library (`currentWindowAdaptiveInfo()`, the pane scaffolds, `NavigationSuiteScaffold`).
- Two panes from expanded. In medium, keep one pane unless both are simple.
- Taskbar and system bars: draw edge to edge and consume insets.

## Working in Figma

- Every component page of the Mobile library has a `[Platforms]` frame with a large screens column and, when the layout changes by device, a `[Layouts]` frame with iPhone, iPad, Android phone, Android tablet and foldable mockups. Every pattern page has a `[Large screens]` frame. Start from these.
- Build one frame per size class boundary, not per device: Android at 600, 840 and 1200 dp wide; iPad in a regular full screen frame and in one narrow window frame that proves the compact fallback. Use the Apple and Material kits for device frames.
- Use auto layout with min and max widths bound to the tokens above so the frame resizes like the app.
- Name frames `Screen / platform / size class` (for example `Orders / android / expanded`).

## Output format

```
Screen: Orders and positions (tablet)
Size classes covered: iPadOS regular + compact fallback; Android medium, expanded
Navigation: sidebar (iPadOS regular), rail 96 dp (medium), expanded rail (expanded)
Layout: list detail. List pane 380 / 360, detail fills, reading cap 680 in detail text
Pane 1 (list): Tab Menu [Mobile] Positions | Orders, Table row [Mobile] rows, selected row highlighted
Pane 2 (detail): Instrument header, Chart [Mobile], Summary [Mobile], actions in pane footer
Presentations: filters in Side sheet [Native]; trade ticket as form sheet 540 / 560
Collapse to compact: list first, detail pushed, selection kept
Input: keyboard order, shortcuts, hover states
States, accessibility, gaps
```

For code, give the adaptive container first (`NavigationSplitView`, `ListDetailPaneScaffold`), then the panes as the same composables or views used on the phone.

## Final check

- Layout decided by window size class; no device or orientation check.
- Same four destinations; system sidebar or rail; selection persists.
- A canonical layout is named for every screen; no stretched phone layout.
- Text and forms capped at 680; buttons sized to their column.
- Bottom sheets and full screen modals translated to side sheets and form sheets where appropriate.
- Compact fallback works for narrow windows and split screen.
- Keyboard, pointer, rotation and resize handled without state loss.
- Touch targets unchanged; tokens only; light and dark.

## Sources

* Apple Human Interface Guidelines: https://developer.apple.com/design/human-interface-guidelines/
* Android window size classes: https://developer.android.com/develop/ui/compose/layouts/adaptive/use-window-size-classes
* Adaptive apps: https://developer.android.com/develop/adaptive-apps
