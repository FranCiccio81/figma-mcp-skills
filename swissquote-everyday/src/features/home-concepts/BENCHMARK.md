# Benchmarks — how banking apps welcome you (C), and how the good dashboards work (D)

> Concept — not a product commitment. Desk research, August 2026. Sources at
> the end; where a claim comes from a vendor blog rather than primary
> research it is marked as such.

Variant C was asked to be the friendly, engaging Home. This is what the
market actually does at the moment of opening, what the evidence says works,
and — the part that shaped C most — what a regulated bank with a trading tab
must not copy.

## 1. What the opening screen looks like

| Pattern | Who | What it does |
|---|---|---|
| **One confident hero balance** | Most 2026 neobank layouts | Balance dominates the top, often on a gradient card, with the two primary actions (transfer, add money) directly under it in thumb reach. Consolidated net worth is the recommended treatment for multi-product/investment relationships — which is Swissquote's case. |
| **Deliberately few actions** | Monzo | The home screen is kept to about five actions. Reported as discipline, not limitation. |
| **Stable action positions** | General practice | Quick actions stay in the same place so muscle memory forms — the same argument Variant A makes for whole cards. |
| **Progressive disclosure** | N26 | Simple view by default, detail one tap away. |
| **Personalised ordering** | Revolut | Widgets reorder by usage — a frequent crypto trader sees that widget rise. |
| **Personalised recommendations on Home** | Nubank | Data-driven reminders and product suggestions placed on the home screen itself; profile avatars users can choose. |
| **Emotional labelling of money** | Monzo Pots | Named pots, user-chosen images, a progress bar, and a celebration when the goal is reached. Labelling and separating money creates loss aversion that works *for* the client: spending from a named pot feels like losing progress. |
| **Rewards for use** | Yuh (Swissquote/PostFinance) | Swissqoin: a token earned per trade and per card payment, with daily caps, redeemable for cash. Closest thing to an in-family precedent for "engaging". |

## 2. What the evidence says about engagement mechanics

Vendor-reported figures, so treat the magnitudes as directional:

- Progress visualisation: users shown it saved ~23% more in a 2025
  multi-institution experiment; gamified money apps report ~22% better
  saving habits.
- Streaks: reported engagement lifts up to ~48%; the motivation is loss
  aversion — people protect a streak they already have.
- Behavioural reward systems: 18–35% engagement lift versus non-gamified
  peers (Deloitte, 2024, as cited).

## 3. The line C does not cross

The FCA's own experiment with 9,000+ consumers, on an app it built itself,
found that engagement mechanics change behaviour in ways that hurt clients:

- points and prize draws: **+12% trades, +6% share of trades in risky
  investments**;
- push notifications: **+11% trades, +8% riskier**;
- effects strongest on young people, those with low financial literacy, and
  women;
- named problem features: in-app points and badges, leaderboards ranking
  clients, celebratory messages after a trade, frequent market-movement
  pushes, red/green flashing price lists;
- some app users showed behaviour resembling problem gambling.

Swissquote's Home sits directly above a Trade tab. Every one of those
mechanics is therefore off the table, whatever the engagement numbers say.

## 4. What this means for Variant C

Six rules, each traceable to the rows above:

1. **Open with a hero, not a list.** One warm greeting, one consolidated
   number, one day-change, two actions. (Hero balance pattern; Monzo's
   discipline.)
2. **Celebrate saving, contributing and habits — never trading.** The
   "months running" streak counts the salary allocation the client set up,
   not activity the bank benefits from. Nothing on this screen counts
   trades. (FCA.)
3. **No points, no badges, no leaderboards, no prize draws.** Not in a
   softer form either. (FCA; and the reason C does not follow the Swissqoin
   precedent.)
4. **Goals must be measurable and real.** The 3a allowance is set by law;
   the safety net is six months of *this client's own* spending, computed
   from their ledger and labelled as a rule of thumb. No invented targets.
   (Monzo Pots, minus the invention.)
5. **Warmth costs no navigation.** Trade / Bank / Plan stay one tap away, in
   the same order, at the same place on the screen, every day. (Stable
   positions.)
6. **The client can turn it off.** The celebration is dismissible; balances
   hide; the AI line is labelled and never required to understand the
   screen. (Consumer-duty posture, and consistent with A and B.)

---

# Part two — analytical dashboards, for Variant D

Different question, different field: not "how do apps greet you" but "what
does a good financial dashboard actually put on one screen".

## What the best-in-class dashboards show

| Product | What it does on the main screen |
|---|---|
| **Empower Personal Dashboard** | The reference net-worth chart: wealth trajectory over months and years, with the trend as the headline object rather than a decoration. |
| **Fidelity Full View** | Rated best overall portfolio dashboard; all accounts in one customisable view — investment performance, asset distribution, net worth. Customisation is the differentiator. |
| **Monarch** | Dashboard composition worth copying wholesale: net worth, recent transactions, month-over-month spending, income month-to-date, upcoming bills, investments snapshot, goals, and a link into a month-in-review that carries cash-flow trends and asset/liability breakdowns. |
| **Copilot Money** | The cash-flow triad — income, spending, net income — as the way to answer "how am I doing" in three numbers. The most visually polished consumer finance app of the current crop. |
| **Sharesight** | Reporting as the product: performance, asset allocation, tax — each a defined report rather than a wall of numbers. |

## What that means for Variant D

1. **The trend is the hero, not the balance.** A number tells you where you
   are; a line tells you how you got there. Range chips (1W / 1M / 3M) let
   the client choose the question.
2. **Three numbers for cash flow, then the shape.** Copilot's triad
   (in / out / net) above a per-month chart — the summary answers first, the
   chart explains.
3. **Allocation as one bar plus rows, and the rows are the navigation.**
   Tapping "Plan · 60.0%" opens Plan. The analytical view *is* the menu, so
   the dashboard does not cost the client a tap.
4. **Ratios, not just totals.** Invested share, months of cover, share of
   income put to work — the three things a wealthy client's adviser would
   compute by hand.
5. **Say what the data cannot do.** The wealth line is reconstructed from
   cash movements, so market performance before today is not in it, and the
   chart says so. A partial month is marked as partial rather than compared
   as if it were whole.

## Chart rules D follows

The `dataviz` procedure, in order: form chosen by the data's job, then colour,
then validation, then marks, then the hover layer, then accessibility.

- **Wealth over time** → area + line, one series, so no legend; crosshair and
  tooltip; data-fitted y-domain (forcing zero would flatten the whole story
  into a stripe).
- **Allocation** → one 100% stacked bar, three categorical hues in fixed
  order, 2px surface gaps, and a labelled row per segment.
- **Net by month** → diverging columns around a zero baseline. Cool pole up,
  warm pole down, and **direction** carries the meaning as well as colour.
  Every bar is labelled with its value, because one bonus month dwarfs the
  rest and an honest linear scale would otherwise leave three bars unreadable.
- **Palettes validated, not eyeballed** (`validate_palette.js`): spaces trio
  `#3d7ff5,#ee4d22,#0f9d63` — worst adjacent CVD ΔE 9.8, normal-vision 30.6;
  flow pair `#2a5cc0,#b4438f` — ΔE 8.6 / 22.6; all ≥ 3:1 on white. Direct
  labels throughout as the required secondary encoding.
- **A table view** of the same numbers sits under the charts, and every
  figure masks when balances are hidden.

---

# Part three — the health-dashboard grammar, applied to money

A fitness dashboard (WHOOP) solves a problem banking has too: a person with
a lot of measurements wants a state, not a spreadsheet. Three patterns port
almost unchanged.

| Health pattern | What it does there | The banking equivalent in D |
|---|---|---|
| **Three rings** (sleep / recovery / strain) | One glance answers "how am I today" | **Liquidity / Day move / Exposure** — one per dashboard section, heading the rows it measures. Tried sticky at the top first; it crowded the headline and pointed nowhere |
| **A metric list with baselines** (23 today, 29 usually) | A number is trivia; a number *against its usual* is a judgement | Every dashboard row prints today's figure over what it usually is |
| **Monitors** (Health monitor 5/5 · Stress monitor) | Several checks reduced to one word | **Risk monitor** (5 checks) and **Market** |
| **Customize** | The dashboard is the client's, not the product's | **Everyday / Trader presets** — same account, two depths of the same three sections |
| **Colour-coded categories** (Monzo's spending colours) | Find the group by colour, then the item by label | Each section wears its space's hue — Bank orange, Trade blue, Plan green — the same three used in the allocation bar |

Two things do **not** port, and pretending otherwise would be a design error:

1. **Direction is not sentiment.** A higher recovery score is good; higher
   spending is not. So the arrow shows the move and the colour shows whether
   it is welcome — and since colour never carries meaning alone, the
   accessible name says both ("higher than your usual month").
2. **A score you cannot reconstruct is not acceptable here.** Recovery can be
   a proprietary 0–100. A bank's ring has to be a percentage *of something
   stated*: cover against a six-month rule of thumb, today's move inside a
   ±2% band, invested share of wealth. Every ring names its range.

## What each client wants at a glance

**The everyday banker** — "can I spend, and am I on track?"

| Metric | Baseline it is read against |
|---|---|
| Available to spend | 30-day average balance |
| Fixed costs before salary | the next standing debit, named and dated |
| Spending · 30 days | the client's usual month |
| Recurring, per month | how many standing items |
| Put to work · 30 days | the client's own 3-month rate |
| Held in other currencies | the wallets behind it |

**The expert trader** — "where do I stand, what is at risk, what does it cost?"

| Metric | Baseline it is read against |
|---|---|
| Day P&L | today's percentage move |
| P&L · this period | the period it covers |
| Buying power | cash reserved for open orders |
| Largest position | its weight in the trading account, flagged past 25% |
| Volatility · 30 days | 12–15% typical for diversified equity ⟨TO CONFIRM⟩ |
| Drawdown from peak · 90d | peak-to-trough |
| Orders | open, and filled today |
| Fees · this month | last month |
| Dividends · this year | the next payment, named and dated |
| Lombard drawn | available, limit, and the rate it costs |

**Both**: currency exposure, the risk monitor's five checks (cash buffer,
borrowing, single-position weight, drawdown, payments), and market state
with the next earnings date for a held instrument.

Everything above is either computed from the ledger or marked `BACKEND:` in
the adapter with the capability it would need — positions with live
valuation, risk analytics, the order book, the fee and dividend ledgers, and
exchange calendars.

## Sources

- [Top 15 Banking Apps with Exceptional UX Design (2026) — Wavespace](https://www.wavespace.agency/blog/banking-app-ux)
- [Banking App UI Design: Principles, Best Practices & Examples (2026) — Lollypop](https://lollypop.design/blog/2026/june/banking-app-ui-design/)
- [Banking App UX Design Guide — Orbix](https://www.orbix.studio/blogs/banking-app-ux-design-guide)
- [Banking App Design: Principles, Examples & UX Best Practices (2026) — Purrweb](https://www.purrweb.com/blog/banking-app-design/)
- [N26 App Home Page: A Product Design Case Study](https://www.jonnyczar.com/project/n26)
- [Nubank launches personalized recommendations in the app home screen](https://international.nubank.com.br/consumers/nubank-launches-personalized-recommendations-in-the-app-homescreen/)
- [Monzo — Pots](https://monzo.com/pots) · [Try setting goals for Pots](https://monzo.com/blog/2018/07/19/set-savings-goals)
- [What Monzo can teach us about designing for money habits](https://healthmattersandme.substack.com/p/what-monzo-can-teach-us-about-designing)
- [Yuh — Discover Swissqoin](https://www.yuh.com/en/app/swissqoin/)
- [Yuh: all-in-one finance app backed by Swissquote & PostFinance](https://www.yuh.com/en/about-yuh/)
- [FCA — concerned about problem behaviours linked to trading app design](https://www.fca.org.uk/news/press-releases/fca-concerned-about-problem-behaviours-linked-trading-app-design)
- [FCA issues warning about trading app gamification — Finextra](https://www.finextra.com/newsarticle/41350/fca-issues-warning-about-trading-app-gamification)
- [Gamification in Banking: Strategies, Examples, and Business Impact — Dashdevs](https://dashdevs.com/blog/gamification-in-financial-apps-unlocking-new-opportunities-for-growth-and-engagement/)
- [Gamification in fintech: Financial literacy or just engagement? — 11:FS](https://www.11fs.com/article/gamification-in-fintech-financial-literacy-or-just-engagement)
- [The Best Portfolio Management Apps of 2026 — Forbes Advisor](https://www.forbes.com/advisor/investing/best-investment-managing-apps/)
- [Best Net Worth Tracking Apps and Web Apps 2026](https://webapprater.com/articles/finance/best-net-worth-tracking-apps.html)
- [Top Wealth Management Apps in 2026 — Finder](https://www.finder.com/investments/wealth-management-apps)
- [The best budgeting apps for 2026 — Engadget](https://www.engadget.com/apps/best-budgeting-apps-120036303.html)
- [Copilot Help Center — Cash Flow tab overview](https://help.copilot.money/en/articles/9682232-cash-flow-tab-overview) · [Dashboard tab overview](https://help.copilot.money/en/articles/6045480-dashboard-tab-overview)
- [Monarch — track, budget, plan](https://www.monarch.com/)
- [Copilot vs Monarch — Origin](https://useorigin.com/resources/blog/copilot-vs-monarch-which-is-better-for-your-financial-life)
