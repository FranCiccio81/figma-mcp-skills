# Auto Cover

> Concept — not a product commitment · 05 · Smart Liquidity

**The job.** Stop a payment failing when the money is simply sitting in another Swissquote product.

**Why it exists.** The mirror of allocation. Money goes out when it is spare and comes back when it is needed — which is what makes clients comfortable letting it leave in the first place.

## Screens to design

- Status: on/off, health, capacity split into own cash and credit, limits used this month.
- Funding order: the client's sources with what each can actually contribute right now.
- Edit rules: cover amount (exact or + buffer), limits, trading reserve, Lombard consent.
- Recent covers, and the failure state with its two manual routes.

## States to cover

`Off` · `Ready` · `Limited` · `Credit only` · `Unavailable` · `Covered — one source / several / with FX / with Lombard` · `Full cover impossible` · `Limit reached` · `Source unavailable` · `Paused`

## Data to use (no placeholders)

| | |
|---|---|
| Capacity, own cash | CHF 32'260 (Save Easy 24'000 + Trading 8'260) |
| Credit | Off by default |
| Cover amount | Exact shortfall, or + CHF 1'000 buffer |
| Limits | 25'000 per payment · 40'000 per month |
| Trading reserve | CHF 10'000 kept for trading |

## Rules the design must respect

- Opt-in only. Off until the client turns it on.
- Own cash before credit, always. Lombard is last, needs separate consent, and carries its own per-cover and monthly ceilings.
- All or nothing: if the authorised sources cannot cover the whole shortfall, nothing moves. A partial transfer solves nothing.
- It never sells investments — put that on the screen, not in a footnote.
- Product conditions are respected and shown: open orders, penalty-free limits, market hours.

## Copy, in tone

- "A payment bigger than your balance shouldn't fail when the cash is just sitting elsewhere."
- "Half a transfer solves nothing."
- "Never touched. We don't sell your investments to pay a bill."

## Done when

- [ ] The client can predict what would happen before it happens.
- [ ] A credit-funded cover looks and reads differently from a cash-funded one.
- [ ] Turning it off keeps the configuration.
