# AI Budgeting

> Concept — not a product commitment · 03 · Smart Liquidity

**The job.** Say how much cash to keep before the next salary — and make the number believable.

**Why it exists.** Clients don't want to run a budget. They want to know how much they can safely put to work. This feature produces the number the allocation engine then obeys.

## Screens to design

- KEEP / GROW hero with the forecast horizon and a confidence signal.
- Projection to the next salary, with known events marked.
- "Put it to work" — the action GROW implies, showing how the existing plan would split it.
- "Change the rules" — safety level, minimum and maximum, planned expenses.
- "Where the number comes from" — the breakdown, on demand.

## States to cover

`High / medium / low confidence` · `Client minimum applies` · `Above preferred maximum (warn)` · `Fixed buffer fallback` · `No surplus` · `Salary late` · `Forecast unavailable` · `Paused`

## Data to use (no placeholders)

| | |
|---|---|
| Horizon | 14 → 25 August (to next salary) |
| Expected requirement | CHF 3'154 + CHF 700 margin |
| KEEP / GROW | CHF 3'850 / CHF 160'791 |
| Safety levels now | 3'450 · 3'800 · 4'300 |
| Same, over a full cycle | 14'450 · 15'750 · 17'800 |

## Rules the design must respect

- Probabilistic language only — "likely", "based on your last 3 months". Never a guarantee, never a projected return.
- The client's minimum always wins over the prediction. Say so on the row it affects.
- A prediction above the preferred maximum warns; it never silently caps. Payments come first.
- Safety levels are shown in francs, never as labels alone — and the three must genuinely differ.
- The breakdown is always reachable, and states which data is used and that it stays within Swissquote.

## Copy, in tone

- KEEP: "What life costs until then" · GROW: "Free to go to work"
- "CHF 160'791 is sitting idle. Your plan would send it here:"
- "An estimate, from your Swissquote history alone."

## Done when

- [ ] The client can explain, from the UI, why the number is what it is.
- [ ] Changing the safety level visibly changes the amounts.
- [ ] The action never proposes touching protected liquidity.
