# Transactions & explainability

> Concept — not a product commitment · 06 · Banking

**The job.** Make an automated movement as understandable as one the client made themselves.

**Why it exists.** Automation is only trusted if it can be audited casually — in the moment, on the phone, without support.

## Screens to design

- List: Smart Liquidity movements distinct from ordinary spending, with a plain inline label.
- Detail: amount and status, "Why this happened", the before/after balances, and a link to edit the rule that caused it.

## States to cover

`Booked` · `Pending settlement (T+2)` · `Failed / declined` · `Smart movement — allocation · surplus · cover · with FX · with credit`

## Data to use (no placeholders)

| | |
|---|---|
| Example | Auto Cover · from Save Easy, + CHF 13'260.00 |
| Before → after | CHF 165'880.50 → CHF 179'140.50 |
| Reason | shortfall, source chosen, amount rule applied |

## Rules the design must respect

- Four questions answered every time: what happened, why, where the money went, what it changed.
- A borrowed amount is labelled as borrowing, with its rate — never as a transfer.
- Pending cash is never shown as spendable.
- The rule that caused the movement is one tap away.

## Copy, in tone

- "Why this happened"
- "Edit the rule that caused this"

## Done when

- [ ] Someone who has never opened the settings understands an automated movement from its detail alone.
