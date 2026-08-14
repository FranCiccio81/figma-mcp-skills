# Swissquote Everyday — interactive concept prototype

> **Concept — not a product commitment.** Every screen carries the label.

High-fidelity, *demonstrable* prototype of **Swissquote Everyday / Smart Liquidity**,
built from the product spec ("Swissquote Everyday — Product Spec & Build Prompt",
Block B). React + TypeScript + Vite; Tailwind for layout only; every colour, type,
spacing, radius and motion value resolves to a Bridge-token custom property.

## Run it

```bash
npm install
npm run dev        # → http://localhost:5173
npm run build      # typecheck + production build
npm run export     # → export/ (see below)
```

## Export it

`npm run export` produces two ready-to-hand-over artefacts. Both are fully
self-contained: no build step, no server, no network calls at runtime.

| Output | Use it for |
|---|---|
| `export/swissquote-everyday.html` | One file. Double-click to open, email it, drop it anywhere. |
| `export/claude-design/` | **Claude Design.** Four flat files — `index.html`, `tokens.css`, `app.css`, `app.js` — that the tool can open, serve and edit. |

In the Claude Design folder, `tokens.css` is loaded *after* `app.css`, so it is
the single place to restyle the prototype: change `--color-action-accent` and
every accent follows; change `--radius-lg` and every card does. Swapping in the
real Bridge DTCG export is an edit to that one file. `app.js` is unminified with
original function names kept, so the engine stays readable (`computeForecast`,
`attemptAutoCover`, `runAllocation`).

For real iteration, edit the TypeScript in `src/` and re-run `npm run export`.

The **Simulate** rig next to the phone advances time. The full acceptance loop
(§11): press **To salary + allocation**, then keep pressing **+1 day** — salary
lands, the allocation fires (visible in Transactions with its explanation),
spending draws the balance down until **Auto Cover** fires, and its transaction
appears with rule, reason, and balance before/after, linking back to the rule
editor. The failure-state chips (market closed, salary late/missing, irregular
income, sources exhausted) and **Force margin call** force each §6 edge case.

## File structure

```
src/
  styles/
    tokens.css              ← THE ONLY FILE WITH RAW VALUES — swap for the real
                              Bridge DTCG export in one edit. 4-tier structure
                              (core primitives → semantic aliases).
    app.css                 BEM component styles, tokens only; Tailwind = layout.
  lib/format.ts             Swiss formatting (CHF 8'400.00), sim calendar, PRNG.
  data/mockLedger.ts        Wealthy demo profile (evolved from §10 on request:
                            salary 21'000, Everyday 165'880.50 incl. a day-0
                            annual bonus, card ≈5'500/month) + 90 days of
                            deterministic synthetic history.
  state/
    types.ts                Domain model shared by engine, data and UI.
    liquidityEngine.ts      The real state machine (§6): allocation, Auto Cover
                            waterfall, guardrails, T+2 settlement, failures.
    forecast.ts             30-day forecast COMPUTED from the ledger at call
                            time — recurring detection, one-off exclusion,
                            spend variance → buffer range + explainability.
    store.tsx               React context; in-memory only (no *Storage).
  components/               New components declared by the concept (§7):
    BuyingPowerBar.tsx        segmented bar, hard own-funds/credit break
    LiquidityForecastChart.tsx  line + uncertainty band + event markers
    AutomationStatusCard.tsx  plain-language state, pause one tap away
    SourceWaterfallList.tsx   ordered sources, Lombard pinned last
    MarginCallModal.tsx       interruptive, never a toast
    ui.tsx                    shared atoms (Toggle, Sheet, StatusPill…)
  features/                 One folder per P0 screen:
    home/  buying-power/  allocation/  budgeting/  auto-cover/  transactions/
  sim/SimulatePanel.tsx     Prototype rig, outside the phone frame.
```

## Liquidity engine — state transitions (§6)

| From | Event | To |
|---|---|---|
| Healthy | balance < minimum + 500 | Approaching minimum |
| Approaching minimum | debit would breach minimum → waterfall draws instantly (Save Easy / Trading cash / FX) | Auto Cover executed |
| Approaching minimum | waterfall draws via Invest Easy sale (T+2, cash pending, never spendable early) | Auto Cover pending |
| Auto Cover pending | settlement day reached, cash credited | Auto Cover executed → Healthy |
| Approaching minimum | every source unavailable/exhausted | Auto Cover failed (sticky until balance ≥ minimum; two manual routes offered) |
| any | client pauses automations (one tap) | Rules paused |
| Rules paused | client resumes | re-derived from balance |

Orthogonal to the state: salary recognition schedules **Smart Salary Allocation**
for income + 1 business day; if salary is early/late/missing the allocation
*waits, it does not guess*. Guardrails (top-up increment CHF 400, monthly cap,
cooldown) are enforced in the engine and displayed on the Auto Cover screen.
Market closed skips Trading cash and says why. A margin call is an interruptive
`alertdialog`, not a toast.

## Design & compliance decisions

- **Credit is never balance** (§9.1): the Buying Power bar has a structural
  divider; the Lombard segment is hatched, listed apart, and the only summed
  figure is *own funds*. Segment hues are a CVD-validated categorical set
  (dataviz six-checks validator, all pass) **plus** per-segment patterns and
  text labels — never colour alone.
- **Probabilistic language everywhere** the forecast appears; the buffer is a
  range; the override slider shows its consequence live.
- **No dark patterns**: Auto Cover off by default in the product (pre-enabled in
  the demo only so §10's "Recent Auto Cover" exists); Lombard needs a separate
  opt-in behind an explicit risk acknowledgement; pause/skip are one tap.
- **A11y**: WCAG 2.1 AA contrast on tokens, 44pt touch targets, `aria-live`
  balance announcements, `prefers-reduced-motion` zeroes all motion durations,
  chart values always available as text. The one orchestrated motion moment is
  the Buying Power bar filling segment by segment on first load.
- Layout holds from 320px (verified: zero horizontal overflow).

## Spec findings (governance notes, §7 "flag, don't invent")

1. **§10 own-funds total**: the stated `22'517.00` does not equal the sum of its
   own parts (3'840.50 + 574.10 + 842.30 + 12'400 + 4'260 = **21'916.90**). The
   engine computes the true sum; a hardcoded figure would drift after one
   simulated day. To confirm against the source data.
2. **§10 internal consistency**: "Everyday CHF 3'840.50" and "balance had hit
   480.00" on the same day are reconciled with a same-day expense reimbursement
   of CHF 2'960.50 (Employer SA) after the Auto Cover top-up — also a nice demo
   of *why* Auto Cover exists (timing gaps the forecast cannot know).
3. **Bridge token export not attached**: `tokens.css` marks every value standing
   in for an unknown Bridge primitive with `⟨PLACEHOLDER⟩`; the file is the
   single swap point.
4. The forecast is computed from the synthetic ledger, never hardcoded — at
   the current wealthy calibration it lands at CHF 11'400 (range
   10'000–13'500); turning on "Irregular income (Marc)" widens the band and
   the copy says so. (The original §10 calibration reproduced CHF 4'150.)
5. Salary trigger threshold (CHF 2'000), FX spread (0.95%), Lombard rate
   (4.25%), esisuisse line — all rendered with `⟨TO CONFIRM⟩` per the brief.

P1/P2 scope (onboarding, card hub, benefits, payments) is not built, matching
the brief's P0 cut. `pending settlement` rows, failed direct debits, declined
cards, market-closed skips and the margin call are rendered states, not text.
