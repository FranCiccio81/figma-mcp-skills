---
name: design-system-governance
description: >-
  Sets up or audits how a design system is run: team model, contribution workflow (proposal, review,
  acceptance criteria), versioning and release policy, deprecation, documentation standards,
  quality gates (accessibility, visual regression, token compliance), adoption measurement and
  communication. Use when asked about DS governance, contribution guidelines, RFC process,
  versioning, breaking changes, deprecation policy, DS health or adoption metrics. Do not use to
  build a single component (use component).
license: MIT
metadata:
  version: "1.0.0"
  domain: design-systems
  status: beta
  trust: internal
  sources: "DS-CARBON,DS-USWDS,DS-ATLASSIAN,DS-SPECTRUM,DS-FLUENT2,W3C-WCAG22"
  platforms: "any"
  last-reviewed: "2026-11-17"
---

# Design system governance

Governance answers four questions: who decides, how changes get in, how changes reach products,
and how we know the system is healthy.

## When to use

- Writing contribution guidelines or an RFC process.
- Defining versioning, release and deprecation rules for design and code libraries.
- Auditing DS health or adoption, or preparing a DS roadmap.

## Inputs

- Current team model, consumers (squads, platforms), tooling (Figma libraries, packages, docs site).
- Existing processes, pain points, release history, adoption data if any.
- Constraints: regulated products, release trains, number of platforms.

## Workflow

1. **Describe the operating model:** centralised, federated or hybrid; who are maintainers,
   contributors and consumers; decision rights for tokens, components and patterns.
2. **Define the contribution workflow** with [the contribution template](references/contribution-workflow.md):
   intake, triage (fix, extend, new), proposal or RFC, design and code review, acceptance
   criteria, documentation, release. Set service levels for each step.
3. **Set acceptance criteria for any addition:** proven need in at least two products or a
   documented exception, accessibility (WCAG 2.2 AA), tokens only, all states, responsive and
   platform behaviour, docs with usage and do/don't, tests and visual baselines, Figma and code parity.
4. **Version and release:** Semantic Versioning for packages and libraries (breaking change,
   feature, fix), changelog with migration notes, release cadence, Figma library publish aligned
   with code releases.
5. **Deprecate safely:** mark, communicate, provide replacement and codemod or search pattern,
   keep for a defined number of releases, measure remaining usage, then remove.
6. **Quality gates in CI:** linting for hardcoded values, accessibility checks, visual regression,
   API change detection.
7. **Measure health and adoption:** coverage of components in products, detached instances in
   Figma, hardcoded values in code, time to contribution, satisfaction of consumers.
8. **Communicate:** release notes, office hours, roadmap, decision log.

## Outputs

Governance document (operating model, RACI, contribution workflow diagram, acceptance criteria,
versioning and deprecation policy, quality gates, metrics, communication plan) or an audit with
findings and recommendations.

## Edge cases

- **Single maintainer:** keep the process light, but keep the acceptance criteria.
- **Product team forks a component:** treat it as a signal; triage into the system or document the exception with an expiry.
- **Figma and code release out of sync:** make the code version the source of truth and tag Figma releases with it.
- **Regulated products:** require sign-off for components that carry legal content or risk disclosures.

## Acceptance criteria

- [ ] Decision rights are explicit for tokens, components and patterns.
- [ ] The contribution workflow has steps, owners and service levels.
- [ ] Versioning follows SemVer with migration notes for breaking changes.
- [ ] Deprecation has a timeline and a replacement path.
- [ ] Health metrics are defined with data sources.

## Sources

- Carbon Design System, contribution and governance: https://carbondesignsystem.com/
- U.S. Web Design System, contribution and maturity: https://designsystem.digital.gov/
- Atlassian Design System, contribution: https://atlassian.design/
- Adobe Spectrum and Microsoft Fluent 2 (comparison only): https://spectrum.adobe.com/ and https://fluent2.microsoft.design/
- W3C WCAG 2.2: https://www.w3.org/WAI/standards-guidelines/wcag/
