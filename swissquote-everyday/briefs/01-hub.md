# Everyday — the hub

> Concept — not a product commitment · 01 · Banking

**The job.** Make one balance, its context and today's decisions legible in five seconds.

**Why it exists.** This is where the client decides whether they need to do anything at all. Most days the honest answer is no — the screen has to earn that trust without hiding anything.

## Screens to design

- Bank tab, Overview: section chips, balance, Buying Power strip, Smart Liquidity card, AI Budgeting teaser, quick actions (Pay · Scan QR-bill · Move money · Card), 5 recent movements, Account details entry.
- Account details sheet: IBAN (masked, show/copy), holder, deposit protection, statements.

## States to cover

`Healthy` · `Approaching minimum` · `Cover executed` · `Cover failed` · `Approval pending` · `Unusual salary` · `Rules paused` · `Margin call (interruptive)`

## Data to use (no placeholders)

| | |
|---|---|
| Everyday balance | CHF 165'880.50 |
| Own accessible cash | CHF 225'646 |
| Lombard available | CHF 118'600 (credit) |
| Keep until next salary | CHF 3'850 |
| Next salary | 25 August · CHF 21'000 |

## Rules the design must respect

- The big number is money in the account right now. Nothing is added to it — not credit, not other products.
- The IBAN does not belong in the header. It lives in Account details.
- Deposit protection is disclosed where the balance is explained.
- Anything needing a decision appears above the fold, with its action attached.

## Copy, in tone

- "Your salary lands. The rest goes to work."
- "Yours, right now."
- "Auto Cover is on. Short on a payment? We bring your cash back."

## Done when

- [ ] A reviewer can say what Everyday is, from this screen alone.
- [ ] Own money and borrowed money are distinguishable without reading a caption.
- [ ] Every automation can be paused within two taps from here.
