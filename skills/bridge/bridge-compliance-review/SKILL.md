---
name: bridge-compliance-review
description: >-
  Reviews a Figma frame, a handoff spec or code against Bridge 2.0 and reports
  deviations by severity: component origin and status, detached instances, unbound
  values, tokens (exact names checked by a script against the colour token index),
  colour roles, states, themes, accessibility, data formats and financial-risk patterns.
  Use when a designer, developer or product manager asks whether a Swissquote or
  PostFinance screen, spec or pull request follows Bridge, before handoff, before merge,
  or during a design QA.
metadata:
  domain: bridge
  version: "1.0.0"
  status: beta
  scope: project
  trust: project-specific
  last-reviewed: "2026-11-17"
---

# Bridge compliance review

Rules come from the platform skills (`bridge-ios`, `bridge-android`, `bridge-tablet`, `bridge-foldables`, `bridge-web`) and `references/bridge-foundations.md`. Method for design versus code differences: `figma-design-code-drift`.

## When to use

* Before handoff (designer self-check), before merge (code review), in design QA, or when a PM checks a spec.

## Inputs

* One of: Figma link or selection, handoff spec, code diff or files. The platform and themes in scope.
* Figma MCP availability. Without it, Figma-side checks (binding, detachment) are reported as Not verified.

## Procedure

1. **Token names (mechanical).** Run the checker on every text artefact (spec, code, exported Figma context):
   `python3 scripts/check_tokens.py <files...>` (or `-` for stdin). It reports colour token names that the exact-name index does not allow, including the classic mistakes (`text/status/...`, `trade/buy/primary-bg`, `badge/<status>/bg`). Unknown names are Blocking: a developer would search for a token that does not exist.
2. **Values.** No raw hex, no primitive (`color/orange/500`, `numbers/n-4`), no opacity used as a tint. In Figma: every fill, stroke, radius, padding and gap bound to a variable; text uses text styles.
3. **Components.** Right origin on mobile (`[Native]` implemented as a system component, `[Mobile]` as a custom Bridge view, native as is untouched); web component status known (work in progress flagged, planned composed and marked `[gap]`); no detached instance; no look-alike rebuilt in code.
4. **Colour roles.** Product actions in `action/product/*`; brand orange only in brand contexts; Buy blue and Sell red only for orders; one primary action per view; up and down with a non-colour cue.
5. **Structure per platform.** Mobile: tab bar with Home, Trade, Bank, Plan in that order; no custom tab bar, sheet or alert; Liquid Glass only on the navigation layer (iOS). Web: breakpoints Large, Medium, Small defined; reflow at 320.
6. **States and themes.** All interactive states; loading, empty, error, offline for data screens; light and dark checked; PF modes if shipped in PostFinance.
7. **Accessibility.** Apply `bridge-accessibility` (risky token pairs, targets, focus ring, text scaling, screen-reader labels).
8. **Content and formats.** Apply `bridge-content-and-formats` (labels name the action, amounts `CHF 1,234.50`, IBAN blocks, dates).
9. **Financial-risk patterns.** Review step with amount, fees, account and timing before commitment; step-up after review; no optimistic success for orders and payments; regulatory messages never transient; destructive confirmations name the object and keep a safe action.
10. **Rate findings.** Blocking (wrong or non-existent token, accessibility failure, missing risk step, wrong origin), Major (hierarchy, roles, missing states or themes), Minor (copy polish, spacing scale chosen by number instead of intent).

## Output

```
Scope: <artefact, platform, themes, tools available>
Token check: <n unknown names> (script output attached)
Findings:
| ID | Location | Rule (skill and section) | Finding | Severity | Fix |
Not verified: <items that need Figma or a device>
Gaps to report: <with the bridge-design-system template>
```

## Edge cases

* Names from other collections (`05mobile`, `Android`, sizes, typography) are outside the checker's scope: verify them in Figma; the script only checks colour tokens.
* The Android collection contains a known typo (`icon/neutral/subtled`): code must use the name as it exists; report the typo, do not rename locally.
* A spec cites a token family on purpose ("`color/control/field/*`, leaf to read in Figma"): accepted, not a finding.

## Acceptance criteria

* The token checker ran and its result is included.
* Every finding cites the rule and its skill, with a fix.
* Items that could not be verified are listed.

## Sources

* WCAG 2.2: https://www.w3.org/TR/WCAG22/
* Figma MCP server tools: https://developers.figma.com/docs/figma-mcp-server/tools-and-prompts
* Apple Human Interface Guidelines: https://developer.apple.com/design/human-interface-guidelines/
* Material Design 3: https://m3.material.io/
