# Swissquote Mobile — Home redesign, four concepts

> Concept — not a product commitment.

Four Home screens built as **different product hypotheses**, not skins of
the same layout. All keep the five-tab navigation (Home · Trade · Bank ·
Plan · Search), reuse the existing design system and engine, and add no
third-party dependencies. The rest of the app is untouched.

## Switching between them

All four live behind a development-only switch in the **Simulate** rig beside
the phone: `Home concept → A · Universe-first / B · Smart Today / C · Good to
see you / D · The dashboard`. Production navigation is unchanged — the switch
is prototype scaffolding, and no variant is reachable from the product
surface.

The same rig forces every state each concept has to survive:

| Chip | What it does |
|---|---|
| Multi-product | The default client: trades, banks and saves. |
| Trade only | Client with a trading account and nothing else — Bank and Plan keep their slot and become "Discover". |
| Bank only | Client who only banks; Trade and Plan stay discoverable. |
| Nothing today | No activity — the empty state, on purpose. |
| Loading | Positions not back yet: skeleton, no layout jump. |
| AI unavailable | The service fails; the deterministic fallback takes over. |
| Balances hidden | The privacy toggle, masking **every** figure on the screen. |

## What is shared

| File | Role |
|---|---|
| `homeData.ts` | The **data adapter**. One shape, consumed by both variants and nothing else. Every mocked value is marked `BACKEND:` with the capability the real implementation needs. |
| `ai.ts` | The **AI seam**: `HomeAiService` + a mock, a deliberately failing mock, and a deterministic fallback. No model, no network. |
| `useHomeAi.ts` | React binding — loading / ready / unavailable, with the fallback wired into the error path. |
| `shared.tsx` | Balance masking, the visibility toggle, skeletons, the AI label. |
| `actions.tsx` | The money actions, and the rule for which ones a client sees. |
| `charts.tsx` | The three charts Variant D plots, in plain SVG on the project's tokens. |
| `WealthAnalysis.tsx` | Variant D's AI tile: three levels of disclosure over findings the adapter computes. |
| `DashboardRows.tsx` | Variant D's metric rows, monitor cards and their sheet, the open-order strip, and the preset switch. |
| `AskAnything.tsx` | The open field on Variant D — the pull half of the assistant. Hands off, never answers inline. |
| `BENCHMARK.md` | Two benchmarks: how banking apps open (C, with the FCA line it does not cross) and what the best analytical dashboards show (D). |

Rules the mock enforces, and a real service would have to keep:

1. **Grounded** — a statement always names the record it came from, and the
   figure comes from the adapter, never from the generator.
2. **Never transactional** — the service returns words and suggested
   questions. Every money movement stays behind the app's normal explicit
   confirmation, initiated by the client.
3. **Degradable** — when it fails, the client loses the phrasing, not the
   information.

---

## Variant A — Universe-first

**Shape.** Greeting · total wealth with today's movement · three universe
cards (value, purpose, one signal, Open →) · four fixed quick actions · one
removable AI insight.

**Hypothesis.** Clients hold three mental accounts — *what I trade*, *what I
bank with*, *what I'm building* — and Home's job is to show the state of each
and get out of the way. If the screen is the same every morning, it stops
being something to read and becomes something to navigate.

**Strength.** Predictable and learnable. Nothing is ranked by a model, so
nothing moves between sessions: the Bank card is always second, and muscle
memory works. It scales cleanly as products are added, it is honest about
what the client owns, and it is the cheapest of the two to build and to
govern — no prioritisation logic to defend to compliance.

**Risk.** It is a directory. For a client whose accounts are quiet it says
very little beyond four numbers, and it puts the work of noticing on them —
the thing that actually needs attention today is three taps away inside a
universe. The single insight card is the only place the app can be
proactive, and it is below the fold.

**What to test.**
- Can clients state, without scrolling, what each space is for and what it is
  worth? Time to correct answer.
- With something wrong in Bank (Auto Cover failed), how long until they find
  it — and do they find it at all before being prompted?
- Does the insight card get read, or dismissed? Dismissal rate over a week is
  the honest measure of whether it earns its space.
- After five sessions, do clients navigate straight to a universe without
  reading the labels? That is the predictability claim, measured.

---

## Variant B — Smart Today

**Shape.** Compact wealth strip · Today (≤3 prioritised cards, each with a
CTA and "why you're seeing this") · the same three spaces in fixed order ·
contextual actions (Top up 3a appears only while allowance remains) · Ask
Swissquote with prompts drawn from what is actually going on.

**Hypothesis.** Clients open the app with a question — *is anything wrong,
and is there anything I should do?* Home should answer it before showing
anything else. Up to three prioritised items lead the screen; the spaces sit
underneath in a fixed order so there is always a floor that does not move.

Priority is a **product rule**, not a model output: needs you › changed ›
opportunity › good to know, with never more than two of a kind up front so
the third slot always brings something different.

**Strength.** It does the noticing. An Auto Cover failure, a bonus that
landed, 3a allowance about to expire — all surface on open, with the
decision one tap away and "why you're seeing this" attached to every card.
It is where a genuinely useful assistant would live, and it makes the
liquidity engine's work visible instead of buried in a transaction list.

**Risk.** The screen changes shape daily, so it is harder to learn and easier
to distrust — a wrong or trivial item at the top costs more than a whole
quiet Home. It invites feed-creep: three slots become five, and the balance
gets pushed further down. And it puts the bank in the position of appearing
to advise; the copy has to stay on the right side of "here is what changed"
versus "here is what you should do".

**What to test.**
- Is the top item the one clients would have chosen themselves? Show three
  cards, ask which matters most, compare to our ranking.
- Trust: after a week, do clients believe the list, or do they scroll past it
  to the balances? Watch first-tap location over sessions.
- Does "why you're seeing this" get opened — and does opening it increase or
  decrease confidence?
- Does the empty state read as reassuring ("nothing needs you") or as broken?
- Regulatory read of the opportunity cards: does any of it land as investment
  advice rather than an observation about the client's own money?

---

## Variant C — Good to see you

**Shape.** A warm full-bleed hero (greeting, one consolidated number,
today's movement, two actions) · a dismissible moment when something is
finished · "your last 30 days" in three figures plus a habit streak · goals
with real progress · the three spaces as compact tiles, same order · one
friendly AI line with a way to ask.

**Hypothesis.** People do not open a banking app to read a report; they open
it to feel in control. If Home greets you by name, shows one confident
number and then talks about momentum — what you put to work, what you are
working towards, how long you have kept it up — the relationship stops being
transactional. Derived from what the market actually does at the moment of
opening: see `BENCHMARK.md`.

**Strength.** It is the only one of the three that makes the client feel
*good*, and the mechanics behind that are evidence-backed — progress
visualisation and streaks are among the few engagement devices with real
measured effect on saving behaviour. It also flatters what Swissquote
already built: the salary allocation running quietly every month is exactly
the kind of habit worth reflecting back. And every celebrated thing is
saving, contributing or keeping a habit — never trading.

**Risk.** Warmth in a bank is a short step from patronising, and the tone
does not survive translation to every client: a private-banking client with
CHF 970k may find "months running" trivialising. Momentum framing can also
crowd out the thing that actually needs attention today — C has no priority
mechanism, so a failed payment sits below a streak. And the FCA's evidence
is a permanent constraint on how far this direction can be pushed: the same
devices that make saving stick make trading dangerous.

**What to test.**
- Does the greeting read as warm or as filler? Ask clients to describe the
  first screen in their own words, before prompting.
- Does the streak change behaviour — do clients keep the allocation on
  longer than in A or B? That is the only claim worth the risk.
- Segment the tone: does it hold for a CHF 20k client and a CHF 1m client,
  or does it need to soften as balances rise?
- Comprehension: with a warm hero above them, can clients still find Trade,
  Bank and Plan as fast as in A? Compare first-tap times directly.
- Regulatory read of the celebration and streak copy, and a check that
  nothing on the screen rewards trading.

---

## Variant D — The dashboard

**Shape.** Three sticky rings (Liquidity · Day move · Exposure) · total
wealth with the change over the selected range · a **wealth-analysis tile**,
closed by default · an **ask field** · two monitors (Risk · Market) · the
**open-order strip** · **My dashboard** — metric rows with baselines, under
an Everyday / Trader preset switch · a wealth trend chart with 1W / 1M / 3M
chips, crosshair and tooltip · allocation as one stacked bar under a row of
**chips that are also the navigation** · the cash-flow triad (in / out / net)
over a per-month diverging column chart · three ratios · a table view of the
same numbers.

**Push and pull.** The tile decides what stands out; the ask field lets the
client raise what the tile did not. Neither answers on Home — the field hands
the question to the assistant surface with the text prefilled, because an
answer rendered here would have nowhere to show its sources. Two openers
only, drawn from what is on this screen: a suggested question about a product
the client does not hold is worse than no suggestion.

**Colour means one thing.** Trade, Bank and Plan wear the same hue in the
allocation chips, the stacked bar and the dashboard rails, with Crypto as a
fourth marker inside Trade. Validated as a set — worst adjacent CVD ΔE 9.5,
normal-vision 30.6, all ≥ 3:1 on white — and never the only cue: every chip,
rail and segment is also named. The hue is carried by a capsule beside or
above the label rather than as a filled pill behind white text, which none of
the four can support at AA on label-sized type.

**The wealth-analysis tile.** Three levels, each earning the space it takes:

1. *Closed* — one line: how many things stand out, and what the first one is
   about, with **no figure in it**. Enough to be worth opening; nothing given
   away to someone reading over a shoulder.
2. *Open* — up to three findings, ranked by what the client could actually do
   about them (cash held above the forecast › an allowance with a date on it ›
   structural observations), each with its action beside it.
3. *The figures* — per finding, the arithmetic: balance, minus authorised card
   payments, minus the forecast need, equals what is left over.

The findings are computed in the adapter from the same numbers the charts
plot. The service re-words them and writes the summary line; it cannot add a
finding, drop one, reorder them, or move money. When it is unavailable the
same findings appear in the app's own words, and the tile says so. Every
action opens a screen where the client decides — the copy observes, it does
not recommend.

**Hypothesis.** A client with roughly a million francs across five products
does not want to be greeted, told what to do, or congratulated. They want
the position: what it is worth, how it got there, how it is split, and
whether the month was net positive. Benchmarked on Empower's net-worth
trajectory, Fidelity Full View, Monarch's dashboard composition and
Copilot's cash-flow triad — see `BENCHMARK.md`.

**Strength.** It is the only variant that answers *how did I get here*, and
the only one where the analysis is also the navigation — the allocation rows
open Trade, Bank and Plan, so density costs no taps. It suits Swissquote's
actual client base better than a warm hero does, it makes the Plan
concentration (60%) visible in a way no list of balances would, and every
chart is honest about its own limits.

**Risk.** It is the densest of the four and the least welcoming: a client
who only wants to pay a bill scrolls past a tile, a metric list and three
charts. The Everyday / Trader presets are also an admission that one
dashboard cannot serve both — if the test shows clients never switch, the
right answer is two products, not one screen with a toggle. The
analysis tile also carries the concept's sharpest regulatory edge — "CHF
160'791 is doing nothing" is one careless rewrite away from advice, which is
why the findings are computed rather than generated and why every one of
them ends with the client deciding. It rewards
financial literacy, which is a way of saying it excludes people without it.
It is also the most expensive to build honestly — the wealth line here is
reconstructed from cash movements, and doing it properly needs a daily
valuation service that does not exist yet.

**What to test.**
- Can clients read the trend correctly — including that it does not contain
  market performance? Ask them what the line shows.
- Does the allocation bar change any intention? "Plan is 60% of your wealth"
  is the kind of fact that should move a decision, or it does not belong.
- Do the ratios mean anything to them, or are they adviser vocabulary?
  "Months of cover" especially.
- Compare with A directly on time-to-Bank: does the density cost navigation
  speed, or does the allocation row absorb it?
- Does anyone open the table view — and who?
- The tile specifically: what share of clients open it, how many go a level
  deeper into the figures, and does seeing the arithmetic increase or reduce
  their trust in the finding?
- The ask field: do clients type, tap an opener, or ignore it? If they only
  ever tap the openers, the field is a menu wearing a text input, and two
  prompt chips would be the honest version.
- The order strip: does "CHF 3'368 held" answer the question clients actually
  have about their available cash, or do they still go looking for it in
  Buying Power?

---

## Comparing them

They differ on one question each. **A: should Home be stable?** — it tells
the client where things are. **B: should Home be smart?** — it tells them
what to do about it. **C: should Home be warm?** — it tells them how they
are doing. **D: should Home be analytical?** — it tells them how they got
here. All four read the same adapter, so any difference in a test comes from
the hypothesis rather than from the numbers.

A useful pairing for research: A and D are both "no personalisation", so
they isolate density; B and C are both proactive, so they isolate tone.

Worth measuring across all four: time to the day's actual task, first-tap
location, self-reported confidence in the numbers, and — for the three that
carry an AI surface — whether clients can tell what the assistant did and
did not do. (D's AI is the most restrained of the four: computed findings,
re-worded — so it is the cleanest test of whether phrasing alone adds value.)
