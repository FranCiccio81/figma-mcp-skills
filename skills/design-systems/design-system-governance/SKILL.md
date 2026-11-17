---
name: design-system-governance
description: >-
  Sets up and runs design system operations: contribution model and intake, decision
  rights, review checklist, semantic versioning and release process, deprecation and
  migration, documentation standards, adoption and health metrics. Use when the user
  defines how teams contribute to a design system, plans a release or breaking change,
  writes a changelog or migration guide, or measures design system adoption.
metadata:
  domain: design-systems
  version: "1.0.0"
  status: beta
  scope: universal
  trust: authored
  last-reviewed: "2026-11-17"
---

# Design system governance

## When to use

* Contribution process, ownership, review gates, release and versioning, deprecations, documentation, adoption reporting.

## Inputs

* Team structure (central team, federated contributors), consuming products, release tooling, current pain points.

## Procedure

1. **Model.** Choose and document: centralized, federated or hybrid. State decision rights: who approves new components, token changes, breaking changes.
2. **Intake.** A request template: problem, use cases with links, existing alternatives considered, urgency. Triage outcomes: use existing, extend, add to system, keep local.
3. **Contribution stages:** proposal → API review (`component-api-design`) → design (Figma) → implementation → accessibility review (`accessibility-audit`) → documentation → release. Each stage has a checklist and an owner.
4. **Versioning.** Semantic Versioning for code packages and libraries: patch for fixes, minor for backward-compatible additions, major for breaking changes. Token renames and visual changes that alter layout are treated as breaking unless aliased.
5. **Release.** Changelog entries written for consumers (what changed, why, action required), release notes, Figma library publish notes aligned with code versions.
6. **Deprecation.** Mark as deprecated (code warnings, Figma description, `$deprecated` on tokens), provide the replacement and a migration guide, announce a removal version or date, measure remaining usage before removal.
7. **Documentation standard** per component: purpose, when to use and not use, anatomy, variants, states, accessibility, content guidelines, code and design examples, changelog.
8. **Health metrics:** adoption (share of UI built with system components), detached Figma instances, hard-coded values in code, time from request to release, open accessibility issues. Report trends, not single snapshots.

## Output

Governance document (model, decision rights, intake template, stage checklists), versioning and release policy, deprecation policy with migration guide template, documentation template, metrics definitions.

## Edge cases

* Urgent product need versus system quality: allow a local implementation with a tracked follow-up to upstream it.
* Federated contributions of uneven quality: the review checklist is the gate, regardless of author seniority.
* Figma and code release cadences differ: version both and keep a compatibility table.

## Acceptance criteria

* Every change type maps to a version increment rule.
* Every deprecation names its replacement and removal version.
* Decision rights are explicit for components, tokens and breaking changes.

## Sources

* Semantic Versioning: https://semver.org/
* Carbon Design System, contribution model (comparative reference): https://carbondesignsystem.com/
* Polaris (comparative reference): https://polaris.shopify.com/
* Design Tokens Format Module, `$deprecated`: https://www.designtokens.org/tr/2025.10/format/
