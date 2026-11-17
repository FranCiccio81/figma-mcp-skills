---
name: bridge-product-manager
description: >-
  Helps product managers write and review requirements for Swissquote and PostFinance
  features so that they fit Bridge 2.0: design principles turned into requirements,
  financial-risk patterns (review and confirm, fees before commitment, step-up
  authentication), accessibility floor and targets, platform and theme scope, component
  availability as an effort and risk signal, copy and formats, and Bridge acceptance
  criteria. Use when a PM drafts or reviews a PRD, feature spec, user stories or
  release scope for a Swissquote or PostFinance product.
metadata:
  domain: bridge
  version: "1.0.0"
  status: beta
  scope: project
  trust: project-specific
  last-reviewed: "2026-11-17"
---

# Bridge for product managers

Use with `product-requirements` (PRD structure and evidence rules). This skill adds what Bridge and the Swissquote context require. Tokens, principles and formats live in `references/bridge-foundations.md`.

## When to use

* Drafting or reviewing a PRD, feature spec, user stories or acceptance criteria for a Swissquote or PostFinance product.
* Scoping a release: platforms, themes, components available, design system dependencies.

## Inputs

* Problem, evidence, goals (see `product-requirements`), target platforms (iPhone, Android phone, tablets, foldables, web), products (Swissquote, PostFinance white label).

## Procedure

1. **Translate the Bridge principles into requirements** (foundations section 10). Examples:
   * Finance for all: plain words, progressive complexity, nothing critical hidden.
   * Design for trust: risks, fees and steps shown before commitment; AI features identifiable, explainable and controllable; a human confirms financial decisions.
   * Design for everyone: WCAG 2.2 AA as the floor; AAA aimed at trade confirmation, authentication and fee disclosure.
2. **Financial-risk requirements** for orders, payments and transfers (non-negotiable unless compliance decides otherwise):
   * A review step shows amount, fees, account and timing before confirmation; the confirm button uses the verb of the action.
   * Step-up authentication happens after the review.
   * No optimistic success for orders and payments.
   * Regulatory and risk messages are never transient (no toast).
   * Destructive actions name the object and the consequence and keep a safe action.
3. **Scope platforms and themes explicitly.** List which of iPhone, Android phone, tablet, foldable and web are in scope, and whether PostFinance ships it (PF themes, PF brand font). Phone-only scope still needs a defined behaviour on large windows if the app runs there.
4. **Check component availability early** with design: on web the component status (stable, ready, work in progress, planned); on mobile the origin (`[Native]`, `[Mobile]`, native as is). Planned or missing components mean a design system dependency: add it to risks with an owner, or accept a composed interim solution reported as `[gap]`.
5. **Content and data.** Copy written in English first, then localised (EN, FR, DE, IT and more); budget 30 to 40 percent text expansion; amounts, dates and identifiers in Bridge formats (`bridge-content-and-formats`). Name orders in labels ("Buy 20 NESN").
6. **States as requirements.** Loading, empty, error, offline, market closed, insufficient funds, session timeout: each with expected behaviour and copy owner.
7. **Acceptance criteria.** Add the Bridge set to each story:
   ```
   Given the feature in SQ Light and SQ Dark (and PF if shipped)
   Then all text and controls meet WCAG 2.2 AA, and AAA where the story covers
        trade confirmation, authentication or fee disclosure
   And every colour signal (up/down, buy/sell, status) has a non-colour cue
   And amounts and dates follow the Bridge formats
   And the screen works at the largest supported text size
   And fees, risks and consequences are visible before any financial commitment
   ```
8. **Definition of ready for design and development:** platforms and themes listed, risk patterns identified, component gaps known with owners, copy owner named, analytics events defined without personal data (`product-metrics`).

## Output

PRD or spec sections (or review comments) covering: Bridge principles applied, financial-risk requirements, platform and theme scope, component availability and gaps, content and formats, states, Bridge acceptance criteria, design system dependencies and owners.

## Edge cases

* A stakeholder asks for green Buy buttons or brand orange on product actions: refuse with the Bridge rule (Buy blue, Sell red, product actions in dark ink) and offer the allowed alternative.
* Marketing moments inside the logged-in product (offer, onboarding): brand orange is allowed there; say where exactly.
* Deadline pressure on a planned component: accept a composed interim solution only if accessibility and risk patterns are intact, and plan the switch.
* Legal or regulatory interpretation: list as a requirement to confirm with compliance; do not decide it in the PRD.

## Acceptance criteria

* The PRD lists platforms and themes in scope.
* Every money-moving flow has the review, fees and step-up requirements.
* Bridge acceptance criteria are attached to stories with UI.
* Component gaps and design system dependencies have owners.

## Sources

* WCAG 2.2: https://www.w3.org/TR/WCAG22/
* Nielsen Norman Group (requirements and research practice): https://www.nngroup.com/
* Apple Human Interface Guidelines: https://developer.apple.com/design/human-interface-guidelines/
* Android design guidance: https://developer.android.com/design/ui/mobile
