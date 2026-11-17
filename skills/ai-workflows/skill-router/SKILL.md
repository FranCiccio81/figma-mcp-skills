---
name: skill-router
description: >-
  Selects which skills of this library apply to a request, based on intent, platform
  (Apple, Android, web), regulated domain and the project's design system, and states
  the precedence order to apply when their guidance conflicts. Use when starting any
  multi-step design, product or implementation request that spans several disciplines,
  or when the user asks which skills or guidelines should drive the work.
metadata:
  domain: ai-workflows
  version: "1.0.0"
  status: beta
  scope: universal
  trust: authored
  last-reviewed: "2026-11-17"
---

# Skill router

## When to use

* Requests that combine product, UX, design system, platform and engineering work, for example "design and implement an accessible banking onboarding flow for iOS".
* When two skills disagree and a justified resolution is needed.
* Not needed for single-discipline requests that obviously map to one skill.

## Inputs

* The user request.
* Context when known: project design system in use, Figma MCP availability, deployment targets.

## Procedure

1. Run the deterministic router (standard library only, no network):
   `python3 scripts/route.py "<request>" [--project-ds <skill-name>] [--figma | --no-figma]`
   If scripts cannot run, apply [references/routing-table.json](references/routing-table.json) by hand with the same rules.
2. Read the result: detected platforms, regulated domains, selected skills ordered by precedence, excluded skills with reasons, notes.
3. Confirm gaps with the user before loading skills: unknown platform for an implementation request; applicable law in a regulated domain; which design system is authoritative.
4. Load only the selected skills, in precedence order. Do not load platform skills for platforms that were not requested.
5. When guidance conflicts, resolve with this order and explain the resolution in the output:
   1. Safety and applicable legal requirements
   2. Project-specific constraints and validated requirements
   3. Official platform guidance (Apple HIG, Android and Material)
   4. Established project design system
   5. Relevant reusable skills
   6. Community best practices
6. Record the routing decision at the top of the work output so reviewers can see why each skill was used.

## Output

A short routing note: platforms, selected skills with reason and precedence, excluded skills, open questions, and any conflict resolved with the rule applied.

## Edge cases

* Several platforms: route each platform separately; never translate iOS patterns directly to Android or the reverse.
* Project design system conflicts with platform guidance (for example a custom bottom bar that hides the system back affordance): platform guidance wins unless the project has a validated, documented exception.
* Design system conflicts with accessibility: accessibility wins (level 1 when legally required, otherwise it is still a quality bar the design system must meet).
* Keyword routing is a starting point; add or drop a skill when the request clearly needs it and say why.

## Acceptance criteria

* For the banking iOS example the router selects product requirements, interaction design, Apple HIG, SwiftUI (including testing), Apple and WCAG accessibility, and the project design system when declared, and excludes Android and web implementation skills.
* Every selected skill has a reason; every exclusion has a reason.
* Router tests pass: `python3 -m unittest discover -s tools/tests` from the repository root.

## Sources

* Agent Skills specification (progressive disclosure, activation): https://github.com/agentskills/agentskills
* Apple Human Interface Guidelines: https://developer.apple.com/design/human-interface-guidelines/
* Android design guidance: https://developer.android.com/design/ui/mobile
