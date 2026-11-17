---
name: bridge-developer-workflow
description: >-
  Guides developers implementing or reviewing Swissquote and PostFinance interfaces
  with Bridge 2.0 on web (React), iOS (SwiftUI) and Android (Compose): consuming
  semantic tokens per theme, mapping component origins to code, using Code Connect and
  Storybook first, central formatters for amounts and dates, states, tests and a pull
  request checklist. Use when a developer builds a Bridge screen or component,
  translates a Figma handoff to code, wires themes, or reviews a pull request against
  Bridge.
metadata:
  domain: bridge
  version: "1.0.0"
  status: beta
  scope: project
  trust: project-specific
  last-reviewed: "2026-11-17"
---

# Bridge for developers

Platform rules live in `bridge-web`, `bridge-ios`, `bridge-android`, `bridge-tablet`, `bridge-foldables`. Tokens and formats live in `references/bridge-foundations.md`. This skill covers how Bridge reaches the codebase.

## When to use

* Implementing a Bridge screen or component; converting a Figma handoff; wiring themes; reviewing a Bridge pull request.
* Generic engineering practice (tests, performance, security) comes from the engineering skills; this skill adds the Bridge rules.

## Inputs

* The handoff (Figma Section marked Ready for dev, spec), the repository and its Bridge package or token layer, Code Connect and Storybook availability.

## Procedure

1. **Reuse before building.** Look for the coded Bridge component (Code Connect mapping, Storybook, package exports). Use its props. Rebuilding a look-alike is a defect. For Figma input follow `figma-design-to-code`; MCP output (React + Tailwind) is a description, never code to paste.
2. **Component origin decides the code.**
   * Web: Bridge React components (built on Radix UI primitives). Keep the primitive's behaviour (focus, roles, keyboard); style only with tokens. Component status: stable and ready are used as is; work in progress is used and flagged; planned is composed and reported.
   * iOS and Android: `[Native]` means the system component themed with Bridge tokens, never a custom rebuild; `[Mobile]` is a custom Bridge view or composable; native-as-is uses the system API untouched.
3. **Tokens.**
   * Only semantic tokens in product code; no primitive, no hex, no opacity tint (alpha tokens only for scrims and shadows).
   * Keep the design names: `color/text/neutral/default` becomes `--color-text-neutral-default` in CSS or `Color.Text.Neutral.default` in Swift or Kotlin. Do not rename to "fix" a name; a typo in a token (for example `icon/neutral/subtled`) is reported to the Governance, not corrected locally.
   * Unsure a leaf exists: check foundations section 12 or Figma. Never ship a guessed token name.
   * Mobile sizes, radii, motion and haptics come from the `05mobile` collection per platform (iOS or Android mode).
4. **Themes.** Web: one set of CSS custom properties per theme (SQ, PF, Default; light and dark), switched at the root; honour `prefers-color-scheme` unless the user chose a theme. iOS and Android: theme objects generated from the same tokens; dark is its own value set, never computed.
5. **Typography.** Bridge text styles mapped to platform text styles so text scales (Dynamic Type, font scale); no fixed font size. Amounts use tabular numerals (`font-variant-numeric: tabular-nums`, `.monospacedDigit()`, or the numeric family).
6. **Formats.** Implement one shared formatter per platform for amounts, large numbers, dates, times, IBAN and phone, following `bridge-content-and-formats` (currency code before the amount, two decimals, period as decimal separator in every language). Do not call locale formatting directly in components: the Bridge rule differs from several locale defaults.
7. **States and behaviour.** Default, hover (web), pressed, focus visible, disabled, loading or submitting, error, empty, offline. Submitting buttons keep their width. No optimistic updates for orders and payments. Step-up authentication after the review screen.
8. **Accessibility in code.** Names, roles, states; keyboard on web; VoiceOver and TalkBack grouping on mobile; focus ring from `border/focus` and the focus effect; contrast verified in dark. See `bridge-accessibility`.
9. **Tests.** Behaviour tests by role and name (`frontend-testing`), previews or stories for each state in light and dark (and PF where relevant), large text, RTL if supported, visual regression where the project has it (`visual-regression-qa`).
10. **Pull request checklist** (paste in the PR):
    ```
    [ ] Bridge component reused (link to Code Connect or Storybook), nothing rebuilt
    [ ] Only semantic tokens; no hex, primitive or opacity tint; names checked
    [ ] Light and dark verified; PF verified if shipped in PostFinance
    [ ] States: hover/pressed/focus/disabled/loading/error/empty
    [ ] Text scales; amounts tabular; formats from the shared formatter
    [ ] Keyboard and screen reader path tested
    [ ] Fees, risks and consequences shown before any financial commitment
    [ ] Gaps reported with the bridge-design-system template
    ```

## Output

Code in the repository's structure, tests and stories or previews, and a PR description with the checklist and any gap reports.

## Edge cases

* Design uses a value with no token: implement with the closest semantic family, add a code comment with the gap report reference, never hard-code silently.
* Handoff conflicts with the platform (custom tab bar, custom alert): implement the platform behaviour, keep the Bridge appearance, and tell the designer.
* Generated or AI-written code: same bar; verify every API and token name exists.

## Acceptance criteria

* A token-name check (`bridge-compliance-review` script) reports no unknown token in the diff.
* No component is rebuilt when a Bridge one exists.
* The PR checklist is complete and true.

## Sources

* Figma MCP server and Code Connect: https://developers.figma.com/docs/figma-mcp-server/tools-and-prompts
* Radix UI primitives: https://www.radix-ui.com/primitives
* SwiftUI: https://developer.apple.com/documentation/swiftui/
* Jetpack Compose: https://developer.android.com/develop/ui/compose
* WAI-ARIA Authoring Practices: https://www.w3.org/WAI/ARIA/apg/
