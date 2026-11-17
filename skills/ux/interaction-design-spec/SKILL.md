---
name: interaction-design-spec
description: >-
  Specifies interaction behaviour for a flow or component: state inventory, transitions and
  triggers, feedback and response times, motion with reduced-motion alternatives, gestures with
  single-pointer alternatives, focus and keyboard behaviour, and the right prototype fidelity to
  validate it. Use when asked to define interactions, states, transitions, micro-interactions,
  animation specs or a prototype plan. Do not use for visual token mapping (use figma-token-mapping)
  or for a full handoff document (use figma-implementation-spec, which can include this output).
license: MIT
metadata:
  version: "1.0.0"
  domain: ux
  status: beta
  trust: internal
  sources: "NNG,W3C-WCAG22,W3C-APG,APPLE-HIG,M3"
  platforms: "any"
  last-reviewed: "2026-11-17"
---

# Interaction design specification

Most implementation bugs in UI come from states nobody designed. Enumerate them before building.

## When to use

- Before handoff of any interactive component or flow.
- When a prototype exists but behaviour is ambiguous.
- When defining motion or gestures.

## Inputs

- Designs (Figma frames, prototype), user goals, platform targets.
- Design system patterns already available.
- Data dependencies (network calls, validation rules).

## Workflow

1. **List states** for each interactive element and view: default, hover (pointer only), focus,
   pressed, selected, disabled, read-only, loading, skeleton, empty, error, success, offline,
   partial data, permission denied. Mark which apply.
2. **Define transitions** as a table: from state, trigger (user, system, time), to state, feedback,
   duration. Use a Mermaid `stateDiagram-v2` for complex components.
3. **Feedback timing:** immediate acknowledgement for direct manipulation (about 0.1 s), progress
   indicator when a wait exceeds about 1 s, determinate progress and a way to continue elsewhere
   for long operations (about 10 s and more).
4. **Motion:** purpose for each animation (orientation, feedback, continuity), duration and easing
   via tokens, and the reduced-motion alternative (`prefers-reduced-motion`, iOS Reduce Motion,
   Android remove animations). Nothing flashes more than three times per second (WCAG 2.3.1).
5. **Gestures:** every path-based or multi-point gesture has a single-pointer alternative (WCAG
   2.5.1); dragging has a non-drag alternative (WCAG 2.5.7); respect platform system gestures
   (iOS edge swipe back, Android predictive back).
6. **Keyboard and focus:** tab order, keys per pattern following the WAI-ARIA Authoring Practices,
   focus placement after open, close, delete and errors, focus never hidden (WCAG 2.4.11).
7. **Data and errors:** validation timing (on blur or on submit), retries, idempotency for money movements, optimistic UI rules.
8. **Choose prototype fidelity** for validation: paper or wireframe for flow, interactive
   prototype for timing and gestures, coded prototype for complex input.

## Outputs

State inventory table, transition table or state diagram, timing and motion spec referencing
tokens, gesture and keyboard map, focus management rules, error and data rules, prototype plan,
open questions.

## Edge cases

- **Figma variant named "Pressed" or "Active":** check whether it shows a press state (`:active`)
  or a focus ring (`:focus-visible`); both often need to exist separately.
- **Hover-only affordances:** must have a touch and keyboard equivalent.
- **Double submission on slow networks:** disable or debounce and show progress.
- **Timeouts** (session expiry): warn and allow extension (WCAG 2.2.1).

## Acceptance criteria

- [ ] Every interactive element has its applicable states listed.
- [ ] Each transition has a trigger and feedback.
- [ ] Every animation has a reduced-motion alternative.
- [ ] Every gesture has a single-pointer and non-drag alternative where required.
- [ ] Focus behaviour is defined for open, close, error and delete.

## Sources

- Nielsen Norman Group, response time limits and microinteractions: https://www.nngroup.com/
- W3C WCAG 2.2: https://www.w3.org/WAI/standards-guidelines/wcag/
- WAI-ARIA Authoring Practices Guide: https://www.w3.org/WAI/ARIA/apg/
- Apple Human Interface Guidelines, gestures and motion: https://developer.apple.com/design/human-interface-guidelines/
- Material Design 3, motion and states: https://m3.material.io/
