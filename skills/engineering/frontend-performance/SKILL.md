---
name: frontend-performance
description: >-
  Diagnoses and improves web frontend performance with measurement first: Core Web
  Vitals (LCP, INP, CLS) from field and lab data, loading strategy, JavaScript and
  rendering costs, images and fonts, caching, and performance budgets in CI. Use when
  the user reports a slow page or app, asks to improve Core Web Vitals or Lighthouse
  scores, reduce bundle size, or set performance budgets.
metadata:
  domain: engineering
  version: "1.0.0"
  status: beta
  scope: universal
  trust: authored
  last-reviewed: "2026-11-17"
---

# Frontend performance

## When to use

* Slow load, sluggish interactions, layout shifts, large bundles, performance regressions.

## Inputs

* URL or build, framework, hosting and CDN, field data (real-user monitoring or CrUX) if available, target devices and networks.

## Procedure

1. **Measure before changing.** Field data first (what users experience), then lab data (Lighthouse, browser performance panel) to diagnose. Record baselines; never claim improvements without before and after numbers.
2. **Core Web Vitals.** Assess at the 75th percentile: LCP good at 2.5 s or less, INP good at 200 ms or less, CLS good at 0.1 or less.
3. **LCP:** identify the LCP element; make it discoverable early (no lazy loading for it, preload or priority hints when appropriate), optimize server response, image format and size, render-blocking CSS and fonts.
4. **INP:** find long tasks on interaction; split work, defer non-urgent updates, reduce hydration and third-party script cost, avoid layout thrashing.
5. **CLS:** reserve space for images, ads and embeds; avoid inserting content above existing content; use font-display strategies and size-adjusted fallbacks.
6. **JavaScript budget:** route-level code splitting, remove unused dependencies, analyze the bundle, prefer platform features over libraries.
7. **Assets and caching:** responsive images, modern formats, compression, long-lived cache with content hashes, CDN.
8. **Guard:** performance budgets and Lighthouse or bundle-size checks in CI; real-user monitoring alerts.

## Output

Diagnosis (metric, value, element or script responsible, evidence), prioritized fixes with expected impact and effort, before and after measurements, budget configuration.

## Edge cases

* Lab and field disagree: trust field data for user impact, use lab to reproduce.
* Third-party scripts (analytics, chat, tag managers): measure their cost, load them later, or remove with stakeholder agreement.
* Accessibility must not regress (for example removing focus styles or alt text for size).

## Acceptance criteria

* Every claimed improvement has before and after numbers under the same conditions.
* Fixes are prioritized by measured impact.
* A regression guard exists in CI or monitoring.

## Sources

* web.dev, Core Web Vitals and thresholds: https://web.dev/
* MDN Web Docs, performance: https://developer.mozilla.org/
