---
name: information-architecture
description: >-
  Designs or audits information architecture: content inventory, organisation schemes, labelling,
  navigation model per platform, sitemap or app map, and validation with card sorting and tree
  testing. Use when asked to structure navigation, a menu, a sitemap or app map, rename sections,
  plan a card sort or tree test, or fix "users cannot find X". Do not use for visual layout or
  component design.
license: MIT
metadata:
  version: "1.0.0"
  domain: ux
  status: beta
  trust: internal
  sources: "NNG,APPLE-HIG,M3"
  platforms: "any"
  last-reviewed: "2026-11-17"
---

# Information architecture

Structure and labels decide whether people find things. Test them with users, not with the org chart.

## When to use

- Designing navigation for a new product or major section.
- Merging products or features that duplicate entry points.
- Diagnosing findability problems from analytics, search logs or support tickets.

## Inputs

- Content and features inventory (or access to the product to build one).
- Users' top tasks and vocabulary (research, search logs, tickets).
- Platform targets and existing navigation.

## Workflow

1. **Inventory** content and features: name, type, owner, usage, task served.
2. **Identify top tasks** and the words users use for them (search logs and research beat internal names).
3. **Choose organisation schemes:** by task, audience, topic or object; avoid organising by department.
4. **Draft the structure** as a tree (depth and breadth balanced; keep frequent tasks shallow).
5. **Label:** short, specific, mutually exclusive, in user vocabulary; avoid "More", "Misc", internal codes.
6. **Map to platform navigation:**
   - iOS and iPadOS: tab bar for top-level peers (iPhone shows a More tab beyond five tabs),
     sidebar on iPad and Mac where appropriate; navigation stacks for hierarchy (`APPLE-HIG`).
   - Android: navigation bar for three to five top destinations on compact windows, navigation
     rail on medium and expanded windows (`M3`).
   - Web: global navigation, local navigation, breadcrumbs, search.
7. **Validate:** open card sort to learn mental models, tree test to measure findability of the
   proposed tree (success rate, directness, first click per task). Set success thresholds first.
8. **Iterate** and document the final map with rationale.

## Outputs

Inventory table, top tasks with user vocabulary, proposed tree (Markdown nested list or Mermaid),
label glossary, platform navigation mapping, validation plan or results, open issues.

## Edge cases

- **Hundreds of items:** use faceted navigation and search, not deeper trees.
- **Regulated content** (legal documents, disclosures): must stay reachable from predictable
  places; flag before moving.
- **Multilingual products:** test labels in each language; translated labels can collide.
- **No users available:** analyse search logs and tickets, label the tree `[Assumption]`, plan a tree test.

## Acceptance criteria

- [ ] Structure is based on top tasks and user vocabulary with sources.
- [ ] No label is an internal code or department name.
- [ ] Platform navigation follows Apple and Material conventions for each target.
- [ ] A tree test plan or result with pre-set success thresholds exists.

## Sources

- Nielsen Norman Group, information architecture, card sorting and tree testing: https://www.nngroup.com/
- Apple Human Interface Guidelines, tab bars and sidebars: https://developer.apple.com/design/human-interface-guidelines/
- Material Design 3, navigation components: https://m3.material.io/
