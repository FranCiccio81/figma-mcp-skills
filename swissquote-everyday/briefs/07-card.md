# Card

> Concept — not a product commitment · 07 · Banking

**The job.** Block, limit and check the card in seconds.

**Why it exists.** Card management is a panic-moment feature. The primary action has to be obvious and reversible.

## Screens to design

- Card hero with the state visible on the card itself.
- Block / unblock as the primary action.
- Limits: monthly spend, contactless without PIN, online payments toggle.
- Details masked by default, with show then copy. Link across to Pay for the wallets. Replace card.

## States to cover

`Active` · `Blocked` · `Online payments off` · `Details revealed` · `Replacement ordered`

## Data to use (no placeholders)

| | |
|---|---|
| Card | Elite card •••• 1234, Swiss Debit Mastercard |
| Monthly limit | CHF 10'000 against ≈ CHF 6'048 typical spend |
| Contactless | CHF 100 per payment without PIN |

## Rules the design must respect

- Blocking is one tap, instantly reversible, and states its real consequence.
- Card state must be visible everywhere the card appears, not only here.
- Sensitive details masked by default.
- Wallets live in Pay — this screen links to them rather than duplicating them.

## Copy, in tone

- "Blocked instantly. Payments already authorised may still land."
- "Off means online payments are declined. Your card still works in shops."

## Done when

- [ ] Blocking takes one tap and the state is unmistakable across the app.
