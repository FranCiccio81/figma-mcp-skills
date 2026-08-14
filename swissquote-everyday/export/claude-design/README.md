# Swissquote Everyday — Claude Design export

> Concept — not a product commitment.

The prototype as four flat files. No build step, no server, no network calls.

| File | What it is |
|---|---|
| `index.html` | Entry point. Loads the styles, then the app. |
| `tokens.css` | **Start here to restyle.** Every colour, type size, spacing, radius, shadow and motion value. Loaded last, so your edits win. |
| `app.css` | Component styles (BEM classes) and the utility layer. |
| `app.js` | The app: React, the Smart Liquidity engine, and every screen. |

## Run it

Open `index.html` — double-clicking works, because nothing is fetched at
runtime. In Claude Design, drop the folder in and it serves itself.

## Restyle it

Everything visual resolves to a custom property in `tokens.css`. Change
`--color-action-accent` and every accent in the app follows; change
`--radius-lg` and every card does. To apply the real Bridge export, replace the
values in that one file.

## Change the behaviour

`app.js` is unminified and keeps its original function names, so the engine is
readable — search for `attemptAutoCover`, `computeForecast` or
`runAllocation`. For real editing, work in the TypeScript source one level up
(`src/`) and re-run `npm run export`.

## What's inside

Four connected features: **AI Budgeting** predicts the liquidity needed before
the next salary; **Smart Salary Allocation** puts the surplus to work;
**Everyday Buying Power** shows accessible cash with credit kept separate; and
**Auto Cover** brings cash back when a payment needs it. The **Simulate** panel
beside the phone advances time and forces the edge cases.
