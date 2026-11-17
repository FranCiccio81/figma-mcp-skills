---
name: skill-router
description: >-
  Selects the smallest set of skills for a request from its intent (product, UX, design system,
  implementation, quality) and its platform context (iOS, iPadOS, macOS, watchOS, visionOS,
  Android, web), orders them, excludes skills for platforms that are not targeted, and applies an
  explicit precedence order when guidance conflicts. Use when starting a multi-step design or
  product engineering request, when several skills could apply, or when the user asks which skills
  or workflow to use. Do not use for single, obvious tasks where one skill clearly applies.
license: MIT
metadata:
  version: "1.0.0"
  domain: ai-workflows
  status: beta
  trust: internal
  sources: "SPEC-AGENTSKILLS"
  platforms: "any"
  last-reviewed: "2026-11-17"
---

# Skill router

Activate what the request needs, nothing more. Loading Android guidance for an iOS task wastes
context and invites wrong advice.

## When to use

- Requests that span phases ("design and implement", "from Figma to production", "audit and fix").
- Requests that name a platform, or several.
- When the user asks which skills to use.

## Inputs

- The user request and any attached artifacts (Figma links, code, documents).
- Project context: `CLAUDE.md`, `rules/`, design system docs, detected stack (Xcode project,
  Gradle, package.json).

## Workflow

1. **Load project context first:** read the project's `CLAUDE.md` and rules. They outrank every
   reusable skill (precedence level 2).
2. **Detect platforms** from the request and the repository (an `.xcodeproj` suggests Apple; a
   Gradle Android module suggests Android; a `package.json` with React suggests web). If none is
   detectable and the task is platform-specific, ask.
3. **Detect intents** with [references/routing-rules.md](references/routing-rules.md).
   The deterministic helper `scripts/route.py` applies the same table:
   `python3 scripts/route.py "Design and implement an accessible banking onboarding flow for iOS"`.
4. **Build the plan:** order skills by phase: context (Figma), product, UX, design system,
   platform design, implementation, quality. Each skill gets one line explaining why it is included.
5. **Exclude** skills for non-targeted platforms and unrelated domains, and say so briefly.
6. **Apply precedence** when skills disagree:
   1. Safety and applicable legal requirements
   2. Project-specific constraints and validated requirements
   3. Official platform guidance
   4. The project's established design system
   5. Relevant reusable skills
   6. Community best practices
   State the conflict, the rule that wins and why.
7. **Re-route** when the task changes (for example a review turns into implementation).

## Outputs

A short routing plan:

```
Project context: CLAUDE.md, rules/bridge-design-system-rules.md
Platforms: ios
1. product-requirements: new flow needs scope and success indicators
2. interaction-design-spec: onboarding flow states and transitions
3. apple-hig-review: iOS conventions
4. swiftui-implementation: implementation
5. apple-accessibility: "accessible" requirement, VoiceOver and Dynamic Type
Excluded: android skills (platform not targeted), web engineering skills
```

## Edge cases

- **Cross-platform request** ("iOS and Android"): include both platform branches, share product and UX skills once.
- **Conflict between design system and platform guidance:** the project's validated constraint wins over official guidance only if it does not break legal or accessibility requirements; flag it.
- **Unknown platform for an implementation task:** ask before routing.
- **Skill missing for a need:** say so and continue with general expertise, clearly labelled.

## Acceptance criteria

- [ ] Project rules are loaded before reusable skills.
- [ ] No skill for an untargeted platform is activated.
- [ ] Each selected skill has a reason.
- [ ] Conflicts are explained with the precedence rule applied.

## Sources

- Agent Skills specification, progressive disclosure: https://agentskills.io/specification
