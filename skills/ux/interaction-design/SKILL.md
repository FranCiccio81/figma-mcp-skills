---
name: interaction-design
description: >-
  Designs task flows and interactions: user flow with entry points and exits, screen
  states (empty, loading, error, success, partial), feedback and transitions, input
  and validation behavior, and the right prototype fidelity to test it. Use when the
  user designs or reviews a flow (onboarding, checkout, sign-up, settings), defines
  component or screen states, plans microinteractions, or asks what to prototype.
metadata:
  domain: ux
  version: "1.0.0"
  status: beta
  scope: universal
  trust: authored
  last-reviewed: "2026-11-17"
---

# Interaction design and prototyping

## When to use

* Designing a flow end to end, or reviewing one for gaps.
* Defining states and behaviors before visual design or implementation.
* Deciding what and how to prototype.

## Inputs

* User goal and scenario, requirements (`product-requirements`), platform.
* Constraints: data availability, latency, legal steps (for example identity verification in finance).

## Procedure

1. **Flow.** Entry points, steps, decisions, exits (success, abandon, error), and re-entry (user returns later). Draw it as a Mermaid flowchart.
2. **Reduce work.** Remove steps, ask only for what is needed now, prefill what is known, defer optional input. Do not ask users to re-enter information already provided in the same process.
3. **States per screen:** first use (empty), loading (with expected duration behavior), partial data, error (recoverable and not), success, offline, permission denied.
4. **Feedback.** Every action gets timely feedback; long operations show progress; destructive actions are confirmable or undoable.
5. **Input and validation.** Validate at the right time (not on every keystroke for most fields), explain how to fix errors next to the field, preserve input on error.
6. **Motion.** Purposeful transitions that explain change; respect reduced-motion settings; never convey information only through motion.
7. **Platform conventions:** navigation, back behavior, gestures and system components per `apple-hig-review` or `material3-compose`.
8. **Prototype fidelity:** paper or low-fi for flow and concept, mid-fi for task tests, high-fi only for visual or motion questions. Prototype the riskiest part first.

## Output

Flow diagram, state matrix (screen × state with behavior and copy reference), interaction notes (feedback, validation, motion), prototype plan (question, fidelity, tool, what is faked).

## Edge cases

* Regulated steps (consent, disclosures, identity checks): keep them understandable and accessible; do not hide them to "optimize conversion".
* Multi-device continuity: define what is saved and where the user resumes.
* Gestures without visible alternatives: always provide a visible control.

## Acceptance criteria

* Every screen in the flow has its states defined.
* Every error state explains recovery.
* Back and exit behavior are defined at each step.
* Reduced motion and assistive technology behavior are covered.

## Sources

* Nielsen Norman Group, interaction design and prototyping: https://www.nngroup.com/
* Apple Human Interface Guidelines: https://developer.apple.com/design/human-interface-guidelines/
* Material Design 3: https://m3.material.io/
* WCAG 2.2 (redundant entry, error handling): https://www.w3.org/TR/WCAG22/
