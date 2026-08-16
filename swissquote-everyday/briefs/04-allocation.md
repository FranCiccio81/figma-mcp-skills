# Smart Salary Allocation

> Concept — not a product commitment · 04 · Smart Liquidity

**The job.** Turn "salary arrived" into "money placed" — inside limits the client set.

**Why it exists.** A standing order moves a fixed amount whether or not it is wise. This moves what is genuinely spare, after protecting what life costs.

## Screens to design

- Plan summary: one sentence, the plan bar, keep + destinations with % and CHF, mode and cap, then Edit · Pause · Skip next.
- Pending approval and unusual-salary cards, with amounts per destination.
- Edit plan: splits, Cash Safety Buffer, execution mode, guardrails.
- Activity: recent runs and the running total put to work.

## States to cover

`Active` · `Waiting for salary` · `Awaiting approval` · `Executed` · `Partially completed` · `No surplus` · `Unusual salary` · `Skipping next` · `Paused` · `Destination unavailable`

## Data to use (no placeholders)

| | |
|---|---|
| Salary | CHF 21'000, 25th of the month |
| Keep | CHF 3'850 (from AI Budgeting) |
| Allocate | ≈ CHF 25'000 — the client's per-salary cap |
| Plan | Save Easy 30 · Invest Easy 40 · Trading 10 · ETF Plan 20 |
| Guardrails | max 25'000/salary · min 500 · ask above ±20% |

## Rules the design must respect

- Allocatable = available balance − protected liquidity, then capped. Never a flat percentage of salary.
- The cap and the minimum are visible where the amounts are shown.
- A salary differing by more than ±20% pauses and asks first, whatever the execution mode.
- A destination that fails keeps its share in Banking. Never redirect investment money to another product.
- Changes apply from the next salary — say it on the edit screen.

## Copy, in tone

- "Keep CHF 3'850. Put ≈ CHF 25'000 to work."
- "Runs on its own · never more than CHF 25'000 a salary"
- "Not this time."

## Done when

- [ ] A reviewer can trace one salary end to end: received → protected → split → placed.
- [ ] Skip and pause are one tap, and neither destroys the setup.
- [ ] Every run explains its own arithmetic.
