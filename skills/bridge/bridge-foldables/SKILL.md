---
name: bridge-foldables
description: >-
  Design, review or build Swissquote layouts for foldable phones (Apple iPhone Duo on iOS 27.1, Android foldables such as Galaxy Z Fold, Pixel Fold and flip devices) with the Bridge 2.0 design system. Use this skill whenever a Swissquote or PostFinance screen must work on a folding device: outer and inner display, fold and hinge, poses and postures (book, table, tabletop), continuity when unfolding, vertical bars, reserved regions, arrangement views, two pane layouts around the fold. Trigger on mentions of foldable, pliable, pliant, iPhone Duo, Fold, Flip, hinge, charnière, inner display, outer display, cover screen, dual screen, even when Bridge is not named.
---

# Bridge on foldables

A foldable is one device with two window sizes and a set of physical positions. The same Swissquote task must continue without loss when the user opens or closes the device, and nothing important may sit on the fold. Most of the work is already done if the screen adapts by size class as described in `bridge-tablet`. This skill adds what is specific to folding: the two displays, the fold, the poses and continuity.

Read `references/bridge-foundations.md` for tokens. Platform rules come from `bridge-ios` and `bridge-android`; multi pane layouts come from `bridge-tablet`.

Foldable guidance is recent and moving, especially for iPhone Duo (announced September 2026, iOS 27.1). Before final specs or code, check the current Apple HIG page "Designing for iPhone Duo" and the Android large screen and foldable documentation. Treat API names below as accurate at the time of writing and verify their availability.

## The mental model

| | Folded | Unfolded |
|---|---|---|
| iPhone Duo | Outer display: compact width, wider and shorter than a regular iPhone | Inner display: regular width |
| Android book style foldable | Cover display: compact width | Inner display: medium in portrait, usually expanded in landscape |
| Android flip | Small cover screen (widgets, glanceable only) | Regular phone, compact width, can be half folded |

Design for the size class, never for the device model or the orientation. Orientation is unreliable on these devices. Use no fixed widths and no breakpoints tied to a specific screen; rely on layout margins, safe area insets and window insets.

Two layouts are the foundation: the phone layout (compact) and the tablet layout (regular, medium, expanded). No layout per pose. A pose rearranges the same controls and hierarchy; it never removes features.

## Step 1: outer display (folded)

- It is the phone screen: tab bar, single column, the `bridge-ios` or `bridge-android` rules.
- iPhone Duo outer display: the system can move the tab bar, toolbar items, back button and status area into a vertical strip on the side to save height. This happens only for system bars from `TabView`, `NavigationStack` and `.toolbar`. A custom bar stays horizontal and wastes the height. Top toolbar items go to the top of the strip, bottom items to the bottom; wide items (text buttons, segmented controls) remain in the horizontal bar. Keep toolbar items few and give them a visibility priority so the right ones move to the overflow menu first.
- The Mobile library has `Tab bar [Native]` with `orientation=vertical` for these mockups.
- The outer display is shorter: check that the primary action and key figure (price, balance) fit without scrolling on trade and payment screens. Prefer inline titles to large titles.
- Flip cover screens are out of scope for full flows. At most, offer glanceable widgets (balance hidden by default, watchlist) with the native widget APIs.

## Step 2: inner display (unfolded)

The inner display must never look like a stretched phone.
- Navigation becomes side navigation: iPhone Duo sidebar or vertical tab bar through `TabView` with `.sidebarAdaptable`; Android rail through `NavigationSuiteScaffold`. Same destinations: Home, Trade, Bank, Plan.
- Use the canonical layouts of `bridge-tablet`: list detail, supporting pane, grid, capped single column. The inner display is closer to a small tablet than to a large phone, so panes are narrow: on iPhone Duo the inner split region is `mobile/size/split-view/inner-display-region` (334) per side. Prefer two panes; three never fit.
- Choose per screen between a sidebar with content (information dense screens such as portfolio and markets) and a split view that keeps the outer display hierarchy (list on one side, detail on the other).

## Step 3: the fold

Treat the fold as a zone where nothing interactive or essential is placed when the device is partly folded.

iPhone Duo
- The fold is a reserved region: active with a width when the device is partially folded, inactive with no width when flat. Layouts based on safe area insets and layout margins receive the offset automatically. Reading the region directly requires the iOS 27.1 SDK.
- `ArrangementView` (SwiftUI) and `UIArrangementViewController` (UIKit), new in 27.1, hold a primary and a secondary view and place their divider on the fold: a split in the book pose, an overlay otherwise. Navigation containers stay outside the arrangement.
- Keep an even number of columns whenever a division region exists, active or not, so no column straddles the fold. Grids go 2 or 4 columns on the inner display, never 3.
- Other reserved regions are the front cameras. System layout guides handle them.

Android
- Read `FoldingFeature` from Jetpack WindowManager (`WindowInfoTracker`): `state` (FLAT, HALF_OPENED), `orientation` (VERTICAL, HORIZONTAL), `isSeparating`, `occlusionType`.
- When `isSeparating` is true, treat the two sides as two panes that end at the hinge. The pane scaffolds of the Material 3 adaptive library do this (`ListDetailPaneScaffold`, `SupportingPaneScaffold`).
- Never place text, a control, a chart crosshair or a dialog across the hinge. Dialogs and sheets sit on one side. Full bleed charts and backgrounds may span a seamless fold when FLAT.
- Some devices have a physical hinge that hides pixels (`occlusionType` FULL): content under it is lost.

Bridge consequences
- A two pane layout puts its divider (`border/subtle`) on the fold with the pane padding (`padding/lg` 16) on each side.
- Amount fields, Buy and Sell buttons, OTP entry, sliders and signatures never cross the fold.
- Tables and order books stay inside one pane; do not let a row run across both.

## Step 4: poses and postures

| Position | Apple name | Android name | What to do |
|---|---|---|---|
| Flat open | Flat | FLAT | Tablet layout, fold ignored |
| Half open, fold vertical | Book pose | Book posture (HALF_OPENED, VERTICAL) | Two panes, one each side. Alerts, menus and primary actions favour the trailing side near the thumb |
| Half open, fold horizontal, device propped | Table pose | Tabletop posture (HALF_OPENED, HORIZONTAL) | Glanceable content on the upper half, touch controls on the lower half |
| Closed | Outer display | Cover display | Phone layout |

Swissquote uses that serve a real need:
- Table or tabletop: live chart or quote on the upper half; trade ticket, quantity stepper and Buy and Sell on the lower half. Video identification or a call with an advisor on top, controls below.
- Book: watchlist on the leading side, instrument on the trailing side; transaction list and transaction detail; document list and document.
- Scrolling content is exempt from pose specific rearrangement: a long list or article just scrolls across.

Pose layouts are an enhancement. A screen that only implements compact and regular layouts correctly is acceptable. A screen that breaks in a pose is not.

## Step 5: continuity

Folding and unfolding are a window resize in the middle of a task. On a banking and trading app, losing state there costs trust.
- Preserve: the destination, the navigation stack, the selected item, scroll position, text typed in fields, the open sheet or dialog, the chart period and zoom, and the step of a multi step flow.
- A trade ticket being filled on the outer display continues on the inner display with the same values; the instrument detail may appear beside it. An order is never submitted, cancelled or duplicated by a fold event.
- Step-up authentication in progress (OTP, biometrics) survives the change. Sessions do not reset.
- Going from two panes to one: show the pane the user last interacted with (the detail when an item is open), with back leading to the list.
- Streaming quotes keep updating during and after the transition; no full reload, no skeleton flash when data is already present.
- Android: the app continues on the other display (configuration change handled, state in `ViewModel` and `rememberSaveable`). iOS: state lives in the scene and navigation path. Avoid replaying entrance animations on unfold unless they carry meaning.
- Privacy: when the device is propped in table pose the screen is visible to others. Respect the hide balances setting and do not reveal masked values on a pose change.

## Step 6: ergonomics and accessibility

- Unfolded devices are held with two hands at the lower edges. Put frequent actions within reach of both thumbs: side navigation, pane footers, lower half. Avoid a single critical control in the top center.
- Touch targets remain 44 pt and 48 dp. Leave at least the pane padding between any target and the fold.
- Dynamic Type and font scale apply; at accessibility sizes a two pane inner layout may fall back to one pane.
- VoiceOver and TalkBack order follows panes: leading pane fully, then trailing pane. Announce nothing on a fold event except when content changed.
- Test light and dark, clear to tinted glass on iOS, and both hands.

## Working in Figma

- Mobile library `[Layouts]` frames include foldable mockups (iPhone Duo inner on iOS 27.1, Android foldable medium). Pattern pages have `[Large screens]` frames. Start from them.
- Use Apple Design Resources for iPhone Duo device frames and sizes. Apple has not published them in the HIG size table at the time of writing, so do not hard code a point size in a spec; describe the size class.
- For each screen deliver at least: outer compact, inner flat, and inner half folded with the fold drawn as a guide. Add a table or book frame only when the screen has a pose specific layout.
- Name frames `Screen / platform / display / pose` (for example `Trade ticket / ios / inner / table`).
- Draw the fold as a guide layer named `fold`, never as part of a component.

## Output format

```
Screen: Instrument detail (foldable)
Outer (compact): phone layout, inline title, chart, key figures, Buy | Sell pinned
Inner flat (regular / medium or expanded): supporting pane. Main: chart + key figures. Supporting: order book or news
Fold: divider on the fold, 16 padding each side, even column count, no control across
Book: watchlist leading, instrument trailing; actions trailing
Table / tabletop: chart upper half; ticket and Buy | Sell lower half
Continuity: instrument, chart period, ticket values, scroll kept on fold and unfold
iOS: TabView sidebarAdaptable, NavigationSplitView or ArrangementView (27.1), system toolbars
Android: NavigationSuiteScaffold, SupportingPaneScaffold, FoldingFeature for tabletop
States, accessibility, gaps, items to verify against current platform docs
```

## Final check

- Compact layout for the outer display and tablet layout for the inner display exist and switch by size class.
- System bars and navigation containers are used so vertical bars and rails appear without custom code.
- Nothing essential or interactive on the fold; even columns; panes end at the fold.
- Poses rearrange, never remove. Table or tabletop layout only where it helps.
- Folding and unfolding lose no state and trigger no financial action.
- No device model check, no fixed width, no orientation check.
- Platform facts verified against the current HIG and Android documentation.
