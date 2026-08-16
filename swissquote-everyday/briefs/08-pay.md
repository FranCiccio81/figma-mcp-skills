# Pay

> Concept — not a product commitment · 08 · Banking

**The job.** One place for every way money leaves Everyday.

**Why it exists.** Clients think in "how do I pay this?", not in payment rails. Group by their question, not by the back office.

## Screens to design

- Send money: standard, instant, QR-bill scan, standing orders, eBill.
- Card & phone: debit card with live state, Apple Pay, Google Pay, TWINT.
- Other currencies: EUR and USD balances, Auto FX, with the conversion cost stated.

## States to cover

`Card active / blocked` · `Wallet added / not added` · `Auto FX on / off` · `Not enough balance → route to liquidity, never a dead end`

## Data to use (no placeholders)

| | |
|---|---|
| Standing orders | 2 active · CHF 5'339/month |
| eBill | 2 due · CHF 980/month |
| Wallets | EUR 8'612 · USD 12'050 |
| FX spread | ≈ 0.95% ⟨TO CONFIRM⟩ |

## Rules the design must respect

- Conversion cost is shown before the payment, never after.
- A shortfall offers the liquidity that exists elsewhere — it does not simply refuse.
- Counts and totals shown here must match the real ledger.

## Copy, in tone

- "You see it before you pay, not after."
- "There in seconds. Any day, any hour."

## Done when

- [ ] Any payment method is reachable in one tap from the hub.
