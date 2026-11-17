---
name: information-architecture
description: >-
  Designs or audits information architecture: content inventory, user mental models,
  grouping and labeling, navigation structure and sitemap, validated with card sorting
  and tree testing. Use when the user asks to organize content or features, design
  navigation or a sitemap, rename menu items, plan a card sort or tree test, or fix
  findability problems.
metadata:
  domain: ux
  version: "1.0.0"
  status: beta
  scope: universal
  trust: authored
  last-reviewed: "2026-11-17"
---

# Information architecture

## When to use

* New product or redesign navigation; app tab structure; settings organization.
* "Users can't find X"; menu labels debated internally.

## Inputs

* Content and feature inventory (or the means to build one).
* User tasks ranked by frequency and importance.
* Platform: navigation patterns differ (iOS tab bar, Android navigation bar or rail, web header and side nav).

## Procedure

1. **Inventory** content and features: name, purpose, audience, frequency of use, owner.
2. **Understand mental models:** open card sort (how users group and name) when the domain is new to you; review search logs and support questions.
3. **Draft the structure:** top-level categories reflect user tasks, not the org chart. Keep labels in users' words; avoid internal jargon and clever names.
4. **Choose navigation patterns** fitting the platform and the number of top-level destinations (see `apple-hig-review`, `material3-compose`).
5. **Validate** with a tree test on the most important tasks: measure success and directness; iterate labels and placement where paths fail.
6. **Document:** sitemap, labeling rules, where new content goes (governance), URL or route conventions.

## Output

Inventory table, proposed structure (indented tree or Mermaid), labeling glossary, tree-test plan or results (task, success, directness, problem paths), recommendations.

## Edge cases

* Items that belong in several places: one canonical home plus cross-links; avoid duplicated destinations.
* Very small products: a flat structure may be best; do not invent hierarchy.
* Multilingual products: test labels per language; translations change label length and meaning.

## Acceptance criteria

* Categories map to user tasks with evidence (sort, tree test, logs) or are labeled assumptions.
* Every top task has a findable path in the proposed structure.
* Navigation pattern matches the platform conventions.

## Sources

* Nielsen Norman Group, information architecture, card sorting, tree testing: https://www.nngroup.com/
* U.S. Web Design System, navigation components: https://designsystem.digital.gov/
