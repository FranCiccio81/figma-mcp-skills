---
name: accessibility-audit
description: >-
  Audits web interfaces and designs for accessibility against WCAG 2.2 (level AA by default) in five
  layers: automated scan, keyboard, screen reader, visual (contrast, zoom, reflow, text spacing,
  motion) and cognitive and flow review, then reports issues with success criterion, user impact,
  severity, evidence and fix. Includes a contrast calculator. Use when asked for an accessibility
  or WCAG audit, a contrast check, a VPAT-style review or an accessibility release gate for web or
  Figma designs. For native apps, use apple-accessibility or android-accessibility, which this
  skill can coordinate.
license: MIT
metadata:
  version: "1.0.0"
  domain: quality
  status: beta
  trust: official-derived
  sources: "W3C-WCAG22,W3C-WAI,W3C-APG"
  platforms: "web"
  last-reviewed: "2026-11-17"
---

# Accessibility audit (WCAG 2.2)

Automated tools find a minority of accessibility problems. An audit combines tools, manual
testing and judgement, and states what was not tested.

## When to use

- Before release of a feature or page, or as a periodic audit.
- Reviewing Figma designs before development (visual and structural checks only).
- Answering "does this pass WCAG?" for a component or a colour pair.

## Inputs

- Scope: URLs, flows, components or Figma frames; target level (AA by default; the project may require more).
- Environment: browsers and assistive technologies available.
- Legal context if relevant: in the EU the European Accessibility Act applies from 28 June 2025
  and EN 301 549 currently references WCAG 2.1 AA; in Switzerland public bodies follow eCH-0059.
  Confirm current obligations with the legal team rather than relying on this summary.

## Workflow

1. **Define scope and sample:** pages and flows, states (errors, dialogs, menus), breakpoints.
2. **Automated layer:** run axe or an equivalent on each page and state; record rule, element, count.
3. **Keyboard layer:** everything reachable and operable with keyboard; logical order; visible
   focus; no traps; focus not obscured by sticky headers (2.4.11); skip links.
4. **Screen reader layer:** test critical flows with at least one desktop pairing (NVDA with
   Firefox or Chrome, or VoiceOver with Safari) and one mobile pairing (VoiceOver iOS or
   TalkBack); check names, roles, states, headings, landmarks, announcements of dynamic changes.
5. **Visual layer:** contrast (text 4.5:1, large text 3:1, UI components and focus indicators
   3:1) computed with `scripts/contrast.py`; reflow at 320 CSS px; zoom 200 %; text spacing
   (1.4.12); no information by color alone; motion and reduced motion; target size 24 × 24 CSS px
   minimum (2.5.8) with its exceptions.
6. **Cognitive and flow layer:** clear labels and instructions, error identification and
   suggestions, no redundant entry (3.3.7), accessible authentication without cognitive tests
   (3.3.8), consistent help (3.2.6), time limits adjustable.
7. **Classify each issue:** success criterion and level, affected users, severity (blocker:
   prevents task completion; critical: severe difficulty; major; minor), evidence (URL, selector,
   screenshot), reproduction steps, recommended fix with code where possible.
8. **Report** using [references/report-template.md](references/report-template.md) and the
   criteria list in [references/wcag22-aa-checklist.md](references/wcag22-aa-checklist.md).
   State limitations: what was not tested and with which tools.

## Outputs

Audit report: scope, method, tools and AT versions, summary by severity and by principle,
issues table, conformance per success criterion (supports, partially supports, does not support,
not applicable, not tested), recommendations and re-test plan.

## Edge cases

- **Figma-only audit:** only visual, structure and content criteria can be assessed; mark the
  rest "not tested" and annotate expected semantics for developers.
- **Third-party widgets:** report separately with vendor responsibility.
- **Project rule stricter than WCAG** (for example 44 px targets): report against both.
- **Disputed issues:** explain the interpretation and cite the W3C Understanding document.

## Acceptance criteria

- [ ] Scope, level, tools and AT versions are stated.
- [ ] All five layers were performed or explicitly excluded.
- [ ] Every issue has SC, severity, evidence and fix.
- [ ] Contrast values are computed, not estimated.
- [ ] Conformance statuses include "not tested" where applicable.

## Sources

- W3C WCAG 2.2 and Understanding documents: https://www.w3.org/WAI/standards-guidelines/wcag/
- W3C WAI evaluation resources: https://www.w3.org/WAI/
- WAI-ARIA Authoring Practices Guide: https://www.w3.org/WAI/ARIA/apg/
