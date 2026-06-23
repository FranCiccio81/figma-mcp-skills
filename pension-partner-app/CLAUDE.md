# CLAUDE.md — Pension Partner

Brief for Claude Code. Read this first; it's how to pick up where we left off.

## What this is
A browser prototype: a Swiss client uploads a **tax return** (required) and **pension/LPP/3a
certificate** (optional). Claude reads them by **vision/OCR**, the user **confirms the figures**,
and a **deterministic Swiss 3-pillar engine** builds a retirement portrait (readiness score,
scenarios, action plan) in the Swissquote Bridge 2.0 design. BYOK (the user's own Anthropic key).

## Run it
The JSX is compiled in-browser by Babel, which *fetches* the component files — so `file://`
won't work. Serve the folder:
```bash
npx serve .            # or:  python3 -m http.server 8000
```
Then open the URL, paste an `sk-ant-…` key (remembered) **or** click "Explore demo — no key".

## Golden rule (don't break this)
**The model extracts and narrates; the maths is deterministic code.** Claude only reads
figures and writes prose. Every number in the portrait comes from `live-engine.js` / `pp-engine.js`,
never from the model. Keep that separation — it's what makes the tool trustworthy.

## Architecture
- **Contract:** the engine produces one `persona` object; the components render it. Keep this boundary and the two sides stay independent.
- **Pipeline (`window.PP_LIVE`):** `readFile` (pdf.js) → `extract(text, prior, file)` (AI, cite-or-null + native vision) → `build(figures)` (Swiss maths) → `enrich(persona)` (AI advisories/insights). `validate()` runs inside `extract` and sets `_checks` / `_flags`.
- **AI gateway (`window.ppAI`):** `completeJSON`, `completeJSONWithDocs` (vision), `connect/disconnect`, `needsKey`. Two modes: integrated (inside Claude) and BYOK.

## Load order (critical — in `index.html`)
vendor (react, react-dom, babel) → `lib_dc6bb704` → **`swiss-params-2025.js`** → `pp-data` →
`pp-data-v2` → `pp-engine` → `ppai` → `pp-confidence` → `pp-catalog` → `live-engine` →
JSX components → `app-shell.js` (mounts last). `swiss-params` must precede `pp-engine`; `live-engine` is last of the engine scripts.

## Where things live
- **Front-end / design:** `index.html` (inline CSS = Bridge 2.0 tokens), `ui-*.js`, the named screen modules (`scenes.js`, `dashboard-living.js`, `readiness-app-v2.js`, `ai-widgets.js`, `ai-assistant.js`, `product-recs.js`, `advisor-glance.js`, `convo-onboard.js`, `dev-tweaks.js`), `app-shell.js`.
- **Engine / logic:** `pp-*.js`, `ppai.js`, `live-engine.js`, `swiss-params-2025.js`.
- **Don't edit:** `assets/js/vendor/*` (pre-minified React/ReactDOM/Babel).

## The four files carrying recent work
- `ppai.js` — BYOK + saved key (localStorage) + native vision (document/image blocks).
- `live-engine.js` — cite-or-null extraction, `validate()` reconciliation/bounds, corrected Swiss maths.
- `ui-upload.js` — vision on upload + confirm-figures edits wired into the build (authoritative).
- `app-shell.js` — saved-key UI, "Explore demo — no key", Forget key.

## Guardrails
- **Cite-or-null:** extraction must return a verbatim source per figure or null; unsourced numbers are flagged, not trusted.
- **Reconciliation:** `validate()` self-checks the document (gross − deductions = taxable, ICC + IFD = total tax, gross − debts = net wealth, bounds, effective-rate). Surface `_flags` to the user.
- **Confirmations win:** a user-confirmed figure is locked; the model must not overwrite it.
- **Swiss params are versioned:** all constants in `swiss-params-2025.js`. Verify against OFAS/ESTV each tax year; bump `year`. (2025: AHV max 30'240/yr, 3a cap 7'258.)
- **Prototype, not production:** BYOK key is browser-side. For customer-facing, move it behind a backend proxy. Keep FINMA / revDSG disclaimers. Not financial/tax advice.

## Good next tasks
- ✅ Done — reconciliation banner on the confirm screen (`ReconBanner` in `ui-upload.js`): reads `_checks`/`_flags`, shows cross-check ✓ / N need review ⚠ / N don't reconcile.
- ✅ Verified — mobile layout already reflows from the same engine via the `.pp-mobile` responsive CSS + viewport toggle (`window.__ppSetMobile`). No horizontal overflow at 390px.
- ✅ Done — the old `comp_*.js` files are renamed to what each screen is (`scenes.js`, `dashboard-living.js`, `readiness-app-v2.js`, `ai-widgets.js`, `ai-assistant.js`, `product-recs.js`, `advisor-glance.js`, `convo-onboard.js`, `dev-tweaks.js`). Load order in `index.html` is unchanged — files cross-reference via `window` globals, not filenames.

## Asset wiring (don't re-break)
The images are bundled as hashed files under `assets/img/`. `index.html` defines
`window.__resources` mapping them to the names the components expect
(`heroRetire` → `464c4b28.png`, `brandSwissquote` → `1584b969.png`, `brandYuh` → `424ee148.png`).
Without this map the hero + brand logos 404.

## Test
Serve → key or demo → upload a tax return (+ certificate) → confirm figures → portrait renders.
Specimen check: gross ≈ CHF 388'500, canton Vaud; `validate()` should pass all reconciliations.
