---
name: frontend-performance
description: >-
  Diagnoses and improves web performance from measurements: Core Web Vitals (LCP, INP, CLS) from
  field and lab data, critical rendering path, images and fonts, JavaScript cost and code
  splitting, React rendering, caching, and performance budgets in CI. Use when a page is slow, Core
  Web Vitals fail, a bundle is too large, or when asked for a performance audit or budget. Do not
  use for backend latency tuning.
license: MIT
metadata:
  version: "1.0.0"
  domain: engineering
  status: beta
  trust: internal
  sources: "WEB-DEV,WEB-MDN,REACT-DOCS"
  platforms: "web"
  last-reviewed: "2026-11-17"
---

# Frontend performance

Measure first, change one thing, measure again. Field data from real users decides what matters.

## When to use

- Core Web Vitals regressions or failing thresholds.
- A slow page, interaction or bundle growth.
- Defining performance budgets.

## Inputs

- URLs or routes, field data (CrUX, RUM) if available, lab traces (Lighthouse, DevTools).
- Build output and bundle analysis, framework and hosting details.

## Workflow

1. **Establish the baseline:** field Core Web Vitals at the 75th percentile, split by device and
   page type. Good thresholds: LCP ≤ 2.5 s, INP ≤ 200 ms, CLS ≤ 0.1. Lab data explains, field
   data decides.
2. **Find the bottleneck per metric:**
   - LCP: identify the LCP element; fix server response, render-blocking resources, image
     size and priority (`fetchpriority="high"` on the LCP image, no lazy loading on it).
   - INP: long tasks on interaction, heavy event handlers, large re-renders; break up work,
     defer non-urgent updates, avoid layout thrashing.
   - CLS: reserve space for images, ads and embeds (`width` and `height` or `aspect-ratio`),
     avoid inserting content above existing content, use `font-display` with matched fallback metrics.
3. **JavaScript cost:** analyse the bundle, code-split by route and on interaction, remove unused
   dependencies, avoid shipping polyfills to modern browsers.
4. **Images and fonts:** modern formats, responsive `srcset` and `sizes`, lazy loading below the
   fold, subset and preload critical fonts only.
5. **React rendering:** profile before memoising; fix unnecessary renders caused by unstable
   props or context; virtualise long lists.
6. **Caching and delivery:** HTTP caching headers, CDN, compression, preconnect to critical origins.
7. **Verify** each change with the same measurement method; keep a change log with before and after.
8. **Protect gains:** performance budgets (bundle size, LCP in lab) in CI with clear owners.

## Outputs

An audit with baseline, bottlenecks per metric with evidence (trace, element), prioritised fixes
with expected impact and effort, before and after measurements for applied changes, and budgets.

## Edge cases

- **No field data:** state that lab results may not reflect users; propose RUM collection.
- **Third-party scripts:** measure their cost, load them after interaction or remove them.
- **Authenticated pages:** CrUX may not cover them; use RUM.
- **Micro-optimisations without measurement:** do not apply.

## Acceptance criteria

- [ ] Baseline uses field data at p75 or states its absence.
- [ ] Each recommendation targets a measured bottleneck.
- [ ] Applied changes have before and after numbers from the same method.
- [ ] Budgets are defined for regression protection.

## Sources

- web.dev, Core Web Vitals and performance guides: https://web.dev/
- MDN Web Docs, performance: https://developer.mozilla.org/
- React documentation, rendering performance: https://react.dev/
