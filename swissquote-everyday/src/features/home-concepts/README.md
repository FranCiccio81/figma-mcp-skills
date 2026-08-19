# Swissquote Mobile — Home redesign, two concepts

> Concept — not a product commitment.

Two Home screens built as **different product hypotheses**, not two skins of
the same layout. Both keep the five-tab navigation (Home · Trade · Bank ·
Plan · Search), reuse the existing design system and engine, and add no
third-party dependencies. The rest of the app is untouched.

## Switching between them

Both live behind a development-only switch in the **Simulate** rig beside the
phone: `Home concept → A · Universe-first / B · Smart Today`. Production
navigation is unchanged — the switch is prototype scaffolding, and neither
variant is reachable from the product surface.

The same rig forces every state each concept has to survive:

| Chip | What it does |
|---|---|
| Multi-product | The default client: trades, banks and saves. |
| Trade only | Client with a trading account and nothing else. |
| Bank only | Client who only banks. |
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

## Comparing them

They differ on one question: **should Home be stable or should it be
smart?** A tells the client where things are; B tells them what to do about
it. Both use the same data, so any difference in the test comes from the
hypothesis rather than from the numbers.

Worth measuring across both: time to the day's actual task, first-tap
location, self-reported confidence in the numbers, and — since both carry an
AI surface — whether clients can tell what the assistant did and did not do.
