---
name: bridge-design-system
description: >-
  Entry point to the Bridge 2.0 design system of Swissquote and PostFinance: what
  Bridge is, the rules that hold on every platform (two token levels, themes,
  component origins, principles), which Bridge skill to use for each platform and role
  (designer, developer, product manager), and how to report gaps or contribute. Use
  this skill when a request mentions Bridge, Swissquote or PostFinance design system,
  Bridge tokens or components, or when it is unclear which Bridge skill applies.
compatibility: Swissquote and PostFinance products only.
metadata:
  domain: bridge
  version: "3.0.0"
  status: beta
  scope: project
  trust: project-specific
  last-reviewed: "2026-11-17"
---

# Bridge 2.0 design system (entry point)

Read `references/bridge-foundations.md` for tokens, values, formats and principles. This skill routes the work and holds the rules shared by every Bridge skill.

## When to use

* Any Swissquote or PostFinance design, code or product task where Bridge applies.
* To choose the right Bridge skill, to resolve a conflict between sources, to report a gap.

## Inputs

* The request, the platform(s), the role of the person asking, the product (Swissquote or PostFinance white label).
* Figma MCP availability: live Figma variables and component descriptions beat the bundled snapshot.

## Procedure

1. **Pick the skills.**

   | Task | Platform skill | Role skill |
   |---|---|---|
   | iPhone | `bridge-ios` | |
   | Android phone | `bridge-android` | |
   | iPad, Android tablet, large or resizable windows | `bridge-tablet` (+ the phone skill) | |
   | Foldables (iPhone Duo, Android foldables) | `bridge-foldables` (+ tablet and phone skills) | |
   | Web (eBanking, trading, back office, marketing) | `bridge-web` | |
   | Designing in Figma, preparing handoff | the platform skill | `bridge-designer-workflow` |
   | Implementing, reviewing code | the platform skill | `bridge-developer-workflow` |
   | Writing a PRD, spec, acceptance criteria | | `bridge-product-manager` |
   | Copy, amounts, dates, IBAN, localisation | | `bridge-content-and-formats` |
   | Accessibility of a Bridge screen | the platform skill | `bridge-accessibility` |
   | Checking a Figma frame, spec or code against Bridge | the platform skill | `bridge-compliance-review` |

2. **Apply the rules that hold everywhere** (details in the foundations):
   * Two token levels: primitives (never used in designs or code) and semantic tokens (the only ones a screen or component uses). There is no component tier, by decision, except the named exceptions (badge heights, drawer and modal widths). The 4-tier model of the March 2026 guide is superseded.
   * Tokens only: no raw hex, no primitive, no opacity to fake a tint (solid tint tokens exist; alpha only for scrims and shadows).
   * Token names are decided by design; code keeps the same segments. Check exact names in foundations section 12 or in Figma; when unsure, name the family and write "leaf to read in Figma".
   * Six colour modes: SQ, Default and PF, each light and dark. Every screen is designed and checked in light and dark; PF modes when the screen ships in PostFinance.
   * Component origin on mobile: `[Native]` (system component themed by Bridge), `[Mobile]` (custom Bridge), or native as is. On the web, the Bridge component and its status (stable, ready, work in progress, planned) decide.
   * Product actions use `action/product/*` (dark ink); orange `action/brand/*` only for marketing, welcome, onboarding and offers; Buy blue, Sell red, only for orders; up green and down red, never colour alone.
   * WCAG 2.2 AA is the floor; AAA is aimed at trade confirmation, authentication and fee disclosure.
3. **Resolve conflicts** with this order: safety and legal requirements; validated product constraints; platform behaviour (Apple HIG, Android and Material); Bridge appearance and components; generic reusable skills. On mobile, the platform wins on behaviour and Bridge wins on appearance.
4. **Report gaps instead of inventing.** No component for a concept: compose from documented components, name the frame `[gap]`, report it. Open governance questions (foundations section 11) are flagged in the output, never decided silently.

## Contribution and gap report

Use this template when something is missing or contradictory:

```
Gap: <component, token, pattern or rule>
Where seen: <Figma file and node, or code path, or skill section>
Need: <the user task that requires it, with the screen>
Workaround used: <composition, closest token family>
Proposal: <optional>
Impact if not solved: <accessibility, consistency, effort>
```

Send it to the Design System Governance through the team's usual channel. Known open items to watch: heading weight (Bold in styles, 600 in variables), gutter variable at 0, motion values, buttons on inverse surfaces, iOS sidebar width (320 or 300), tab bar description listing old sections, token typo `icon/neutral/subtled`, property name `chnageIcon` on destructive buttons.

## Output

The list of Bridge skills to apply, the rules relevant to the task, and any gap or conflict with its resolution.

## Edge cases

* Older Bridge material (the March 2026 guide in [references/legacy-guide.md](references/legacy-guide.md), the root file `rules/bridge-design-system-rules.md`, the old "SQ Component" kit, libraries marked "Don't use - Old DS") conflicts with Bridge 2.0: Bridge 2.0 wins; report the conflict.
* A request outside Swissquote and PostFinance products: do not apply Bridge; use the generic skills.
* The snapshot in the foundations is dated (12 November 2026): when Figma is reachable, read live variables first.

## Acceptance criteria

* The right platform and role skills are named for the task.
* No rule is stated from the superseded 4-tier model.
* Gaps and governance questions are reported with the template, not guessed.

## Sources

* Bridge 2.0 Figma libraries (Foundations, Components Library, Mobile library 2.0), through the Figma MCP: https://developers.figma.com/docs/figma-mcp-server/tools-and-prompts
* Design Tokens Format Module 2025.10 (token exchange format): https://www.designtokens.org/tr/2025.10/format/
* WCAG 2.2: https://www.w3.org/TR/WCAG22/
