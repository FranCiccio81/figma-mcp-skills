# Foundations

> Concept — not a product commitment

_The rules that apply to all eight briefs. Read once; every other page assumes them._

## The loop

**SEE** what liquidity exists (Buying Power) → **PROTECT** what life costs (AI Budgeting) → **GROW** the rest (Smart Salary Allocation) → **COVER** the account when a payment needs it (Auto Cover).

Each feature answers one question. Never let a screen answer two.

## Who

Léa Baumann, 34, Lausanne. Senior product manager, salary CHF 21'000 net on the 25th. About CHF 970'000 with Swissquote across trading, Invest Easy, Save Easy, 3a and cash. High digital literacy, moderate financial literacy, no appetite for a monthly admin ritual.

## Canvas & system

Mobile first: 390 × 844 reference, must hold at 320. 8pt grid, 4pt for icon and inline spacing.

Bridge Design System is the source of truth. Semantic tokens only — no raw hex in a design. If a token is missing, flag it as a governance finding rather than inventing a value.

Inter, Bridge type scale. Tabular figures wherever amounts align.

## Numbers

Swiss convention throughout: `CHF 8'400.00` — currency code first, apostrophe thousands separator.

Round only where it aids reading (headline figures may drop decimals); never round in a way that changes a total.

## Tone of voice

**Straight to the point** — less words, more action. "Your salary lands. The rest goes to work."

**Impertinence** — the truth, even if it disrupts. "A payment bigger than your balance shouldn't fail when the cash is just sitting elsewhere."

**Frankness** — say it how it is. "Capacity to borrow. Not money you own."

Impertinence is for feature intros and empty states. Never on a risk disclosure, an error, or a regulatory line — there, plain and precise wins.

## Accessibility

WCAG 2.1 AA. 4.5:1 text, 3:1 non-text and focus. Touch targets ≥ 44 × 44pt.

Never encode meaning by colour alone — pair with label, pattern or icon.

Balance changes announced to screen readers. `prefers-reduced-motion` respected. Chart values always available as text.

## Motion

One orchestrated moment in the whole product: the Buying Power bar filling segment by segment on first load. Everything else is quiet.

## Non-negotiables everywhere

Credit is never presented as balance, in any total, on any screen.

Automation is execution of a client instruction — never advice. Never recommend a product, a weighting, or a moment to invest.

Every automation can be paused in one tap and skipped without being rebuilt.

Every automated movement explains itself: what happened, why, where the money went, what it changed.

Every screen carries the concept label. Unverified facts are marked ⟨TO CONFIRM⟩.

---

Interactive prototype: open export/swissquote-everyday.html, or the Claude Design folder beside it.
