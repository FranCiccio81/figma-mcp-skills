# Pension Partner — editable proto (`app/`)

This is your Claude Design prototype, **unbundled into editable source** — your exact
design and flow, with the live engine wired in. Upload a real Swiss tax return and/or
pension certificate, Claude reads them by vision/OCR, the figures are confirmed, and the
deterministic Swiss engine builds the portrait + action plan. Drop this folder into Claude
Design or Claude Code and iterate.

## Run it

The JSX components are compiled in the browser by Babel, which **fetches** them — so a
`file://` double-click won't work. Run a tiny static server from this folder:

```bash
npx serve .         # then open the printed URL
# or
python3 -m http.server 8000   # then open http://localhost:8000
```

Inside Claude Design / Claude Code the project is served for you, so it just runs.
(For a no-server, double-click demo, use the bundled `Pension_Partner__LIVE.html` — same app.)

On first load: paste your Anthropic key (`sk-ant-…`, remembered in this browser) **or** click
**Explore demo — no key** for the offline sample case.

## Structure

```
app/
  index.html                     entry point — inline CSS (your Bridge 2.0 design) + script order
  assets/
    js/
      vendor/                     react, react-dom, babel (pre-minified, don't edit)
      swiss-params-2025.js        ← Swiss constants (verify each tax year)
      pp-data.js / pp-data-v2.js  base data + i18n + readiness data layer
      pp-engine.js                scoring weights, plan score, persona templates
      pp-confidence.js            deterministic data-confidence index
      pp-catalog.js               Swissquote product catalog (cross-sell)
      ppai.js                     ← AI gateway (BYOK + saved key + native vision)
      live-engine.js              ← readFile → extract → build → enrich + validate()
      ui-kit.js                   shared components (incl. ConfirmCorrect)
      ui-upload.js                ← the upload + OCR + confirm-figures flow (incl. reconciliation banner)
      app-shell.js                top-level app, screens, key modal (mounts last)
      dev-tweaks.js               prototype tweaks/dev-control panel
      dashboard-living.js         LivingDashboard + readiness hero & charts
      scenes.js                   welcome / upload / confirm / gapfill / manual scenes + convos
      convo-onboard.js            conversational onboarding flow
      ai-widgets.js               in-chat AI result widgets (gauge, scenarios, plans…)
      product-recs.js             Swissquote catalog cross-sell cards
      advisor-glance.js           advisor "at a glance" summary
      ai-assistant.js             voice/chat AI assistant
      readiness-app-v2.js         V2 readiness experience (ReadinessApp)
    fonts/                        Inter, Roboto Mono, Remix Icon (vendored)
    img/                          icons / illustration
```

The four `←` files are where the upgrades live; everything else is your original code.

## What's wired in (vs the original export)

- **Native vision/OCR** — the actual PDF/image is sent to Claude (`ppai.js` / `live-engine.js`), so scans and phone photos are read, not just text-PDFs.
- **Saved key + no-key demo** — key remembered in localStorage with a Forget option; "Explore demo" runs offline sample data (`app-shell.js`).
- **Cite-or-null extraction** — every figure must come with the verbatim source it was read from, or it's flagged, not trusted (`live-engine.js`).
- **Reconciliation + bounds** — `PP_LIVE.validate()` self-checks the document (gross − deductions = taxable, ICC + IFD = total tax, gross wealth − debts = net wealth, plausibility ranges). Sets `_checks` / `_flags`.
- **Confirm-figures feeds the build** — edits/confirmations on the review screen now flow into the portrait and are authoritative (the model can't overwrite a confirmed value).
- **Corrected Swiss maths** — AHV 2025 = CHF 30,240/yr, in the versioned params module.

## Where to iterate

- **Design / front-end:** `index.html` (inline CSS = your Bridge 2.0 tokens), `ui-*.js`, the named screen modules (`scenes.js`, `dashboard-living.js`, `readiness-app-v2.js`, `ai-*.js`, `product-recs.js`, `advisor-glance.js`, `convo-onboard.js`, `dev-tweaks.js`), `app-shell.js`. Editing these changes the look and flow; the engine is untouched.
- **Engine / logic:** the `pp-*.js`, `ppai.js`, `live-engine.js`, `swiss-params-2025.js`. Editing these changes extraction, scoring, and the Swiss model.

The contract between them: the engine returns a `persona` object; the components render it.
Keep that boundary and the two sides stay independent.

## Notes

- Verify `swiss-params-2025.js` against official sources each tax year.
- This is a prototype: the BYOK key is browser-side. For anything customer-facing, move the
  key behind a backend proxy and keep the FINMA / revDSG disclaimers.
- Illustrative only — not financial, tax, or investment advice.
