/**
 * Designer briefs — single source, two outputs.
 *
 *   briefs/*.md    one file per feature, for the repo and for editing
 *   briefs/index.html  the same content, laid out to read and to print
 *
 * Rule for this document: one page per feature. If a brief needs more, the
 * feature needs splitting, not the page.
 */
import { writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));

const meta = {
  title: 'Swissquote Everyday — designer briefs',
  subtitle: 'Smart Liquidity: four features that make everyday cash and invested wealth behave as one balance sheet.',
  status: 'Concept — not a product commitment',
  prototype: 'Interactive prototype: open export/swissquote-everyday.html, or the Claude Design folder beside it.',
};

/* ------------------------------------------------------------------ */
/* Foundations — read once, applies to every brief                     */
/* ------------------------------------------------------------------ */
const foundations = {
  id: 'foundations',
  eyebrow: '00 · Read first',
  title: 'Foundations',
  job: 'The rules that apply to all eight briefs. Read once; every other page assumes them.',
  blocks: [
    {
      h: 'The loop',
      body: [
        '**SEE** what liquidity exists (Buying Power) → **PROTECT** what life costs (AI Budgeting) → **GROW** the rest (Smart Salary Allocation) → **COVER** the account when a payment needs it (Auto Cover).',
        'Each feature answers one question. Never let a screen answer two.',
      ],
    },
    {
      h: 'Who',
      body: [
        'Léa Baumann, 34, Lausanne. Senior product manager, salary CHF 21\'000 net on the 25th. About CHF 970\'000 with Swissquote across trading, Invest Easy, Save Easy, 3a and cash. High digital literacy, moderate financial literacy, no appetite for a monthly admin ritual.',
      ],
    },
    {
      h: 'Canvas & system',
      body: [
        'Mobile first: 390 × 844 reference, must hold at 320. 8pt grid, 4pt for icon and inline spacing.',
        'Bridge Design System is the source of truth. Semantic tokens only — no raw hex in a design. If a token is missing, flag it as a governance finding rather than inventing a value.',
        'Inter, Bridge type scale. Tabular figures wherever amounts align.',
      ],
    },
    {
      h: 'Numbers',
      body: [
        'Swiss convention throughout: `CHF 8\'400.00` — currency code first, apostrophe thousands separator.',
        'Round only where it aids reading (headline figures may drop decimals); never round in a way that changes a total.',
      ],
    },
    {
      h: 'Tone of voice',
      body: [
        '**Straight to the point** — less words, more action. "Your salary lands. The rest goes to work."',
        '**Impertinence** — the truth, even if it disrupts. "A payment bigger than your balance shouldn\'t fail when the cash is just sitting elsewhere."',
        '**Frankness** — say it how it is. "Capacity to borrow. Not money you own."',
        'Impertinence is for feature intros and empty states. Never on a risk disclosure, an error, or a regulatory line — there, plain and precise wins.',
      ],
    },
    {
      h: 'Accessibility',
      body: [
        'WCAG 2.1 AA. 4.5:1 text, 3:1 non-text and focus. Touch targets ≥ 44 × 44pt.',
        'Never encode meaning by colour alone — pair with label, pattern or icon.',
        'Balance changes announced to screen readers. `prefers-reduced-motion` respected. Chart values always available as text.',
      ],
    },
    {
      h: 'Motion',
      body: [
        'One orchestrated moment in the whole product: the Buying Power bar filling segment by segment on first load. Everything else is quiet.',
      ],
    },
    {
      h: 'Non-negotiables everywhere',
      body: [
        'Credit is never presented as balance, in any total, on any screen.',
        'Automation is execution of a client instruction — never advice. Never recommend a product, a weighting, or a moment to invest.',
        'Every automation can be paused in one tap and skipped without being rebuilt.',
        'Every automated movement explains itself: what happened, why, where the money went, what it changed.',
        'Every screen carries the concept label. Unverified facts are marked ⟨TO CONFIRM⟩.',
      ],
    },
  ],
};

/* ------------------------------------------------------------------ */
/* Feature briefs                                                      */
/* ------------------------------------------------------------------ */
const briefs = [
  {
    id: 'hub',
    eyebrow: '01 · Banking',
    title: 'Everyday — the hub',
    job: 'Make one balance, its context and today\'s decisions legible in five seconds.',
    why: 'This is where the client decides whether they need to do anything at all. Most days the honest answer is no — the screen has to earn that trust without hiding anything.',
    screens: [
      'Bank tab, Overview: section chips, balance, Buying Power strip, Smart Liquidity card, AI Budgeting teaser, quick actions (Pay · Scan QR-bill · Move money · Card), 5 recent movements, Account details entry.',
      'Account details sheet: IBAN (masked, show/copy), holder, deposit protection, statements.',
    ],
    states: ['Healthy', 'Approaching minimum', 'Cover executed', 'Cover failed', 'Approval pending', 'Unusual salary', 'Rules paused', 'Margin call (interruptive)'],
    data: [
      ['Everyday balance', 'CHF 165\'880.50'],
      ['Own accessible cash', 'CHF 225\'646'],
      ['Lombard available', 'CHF 118\'600 (credit)'],
      ['Keep until next salary', 'CHF 3\'850'],
      ['Next salary', '25 August · CHF 21\'000'],
    ],
    rules: [
      'The big number is money in the account right now. Nothing is added to it — not credit, not other products.',
      'The IBAN does not belong in the header. It lives in Account details.',
      'Deposit protection is disclosed where the balance is explained.',
      'Anything needing a decision appears above the fold, with its action attached.',
    ],
    copy: ['"Your salary lands. The rest goes to work."', '"Yours, right now."', '"Auto Cover is on. Short on a payment? We bring your cash back."'],
    done: [
      'A reviewer can say what Everyday is, from this screen alone.',
      'Own money and borrowed money are distinguishable without reading a caption.',
      'Every automation can be paused within two taps from here.',
    ],
  },
  {
    id: 'buying-power',
    eyebrow: '02 · Smart Liquidity',
    title: 'Everyday Buying Power',
    job: 'Answer "how much can I actually use right now?" without ever mixing cash and credit.',
    why: 'A Swissquote client\'s liquidity is scattered across products, so a plain account balance under-reports it. But borrowed capacity is not wealth — and must never look like it.',
    screens: [
      'The strip on the hub — the signature element of the concept.',
      'Detail sheet, in this order: available now → accessible cash → own accessible cash (subtotal) → protected vs flexible → Lombard, separately → maximum, as a secondary figure.',
      'Each source expands: what was deducted, why, and the action it offers (Move to Everyday).',
    ],
    states: ['Cash only', 'Several sources', 'Multi-currency', 'AI Budgeting on', 'Lombard shown / hidden / partly used', 'Source unavailable', 'Reserved for open orders', 'Conditional Save Easy', 'Privacy mode'],
    data: [
      ['Everyday, available now', 'CHF 164\'640 (after CHF 1\'240 authorised card)'],
      ['Trading cash', 'CHF 18\'260 (after CHF 6\'000 open orders)'],
      ['Save Easy', 'CHF 25\'000 penalty-free, of CHF 86\'400'],
      ['Other currencies', '≈ CHF 17\'745 indicative'],
      ['Own accessible cash', 'CHF 225\'646'],
      ['Lombard', 'CHF 118\'600 drawable of a CHF 150\'000 limit'],
    ],
    rules: [
      'Never render one total that includes credit. The own-cash subtotal is always visible on its own.',
      'Reservations are shown where they are deducted, not netted invisibly.',
      'Invested money (Invest Easy, Saving Plan) is listed as explicitly NOT included, with the reason.',
      'Protected liquidity is identified, never silently subtracted — it is still the client\'s money.',
      'Segments must be readable without colour: label, pattern and text amount.',
    ],
    copy: ['"Your money, wherever it sits. Credit kept separate — because it isn\'t yours."', '"Capacity to borrow. Not money you own."', '"Invested money isn\'t cash."'],
    done: [
      'A user can point at what is theirs without reading a caption.',
      'Every source can explain what was held back and why.',
      'Showing Lombard is an explicit choice, and showing it borrows nothing.',
    ],
  },
  {
    id: 'ai-budgeting',
    eyebrow: '03 · Smart Liquidity',
    title: 'AI Budgeting',
    job: 'Say how much cash to keep before the next salary — and make the number believable.',
    why: 'Clients don\'t want to run a budget. They want to know how much they can safely put to work. This feature produces the number the allocation engine then obeys.',
    screens: [
      'KEEP / GROW hero with the forecast horizon and a confidence signal.',
      'Projection to the next salary, with known events marked.',
      '"Put it to work" — the action GROW implies, showing how the existing plan would split it.',
      '"Change the rules" — safety level, minimum and maximum, planned expenses.',
      '"Where the number comes from" — the breakdown, on demand.',
    ],
    states: ['High / medium / low confidence', 'Client minimum applies', 'Above preferred maximum (warn)', 'Fixed buffer fallback', 'No surplus', 'Salary late', 'Forecast unavailable', 'Paused'],
    data: [
      ['Horizon', '14 → 25 August (to next salary)'],
      ['Expected requirement', 'CHF 3\'154 + CHF 700 margin'],
      ['KEEP / GROW', 'CHF 3\'850 / CHF 160\'791'],
      ['Safety levels now', '3\'450 · 3\'800 · 4\'300'],
      ['Same, over a full cycle', '14\'450 · 15\'750 · 17\'800'],
    ],
    rules: [
      'Probabilistic language only — "likely", "based on your last 3 months". Never a guarantee, never a projected return.',
      'The client\'s minimum always wins over the prediction. Say so on the row it affects.',
      'A prediction above the preferred maximum warns; it never silently caps. Payments come first.',
      'Safety levels are shown in francs, never as labels alone — and the three must genuinely differ.',
      'The breakdown is always reachable, and states which data is used and that it stays within Swissquote.',
    ],
    copy: ['KEEP: "What life costs until then" · GROW: "Free to go to work"', '"CHF 160\'791 is sitting idle. Your plan would send it here:"', '"An estimate, from your Swissquote history alone."'],
    done: [
      'The client can explain, from the UI, why the number is what it is.',
      'Changing the safety level visibly changes the amounts.',
      'The action never proposes touching protected liquidity.',
    ],
  },
  {
    id: 'allocation',
    eyebrow: '04 · Smart Liquidity',
    title: 'Smart Salary Allocation',
    job: 'Turn "salary arrived" into "money placed" — inside limits the client set.',
    why: 'A standing order moves a fixed amount whether or not it is wise. This moves what is genuinely spare, after protecting what life costs.',
    screens: [
      'Plan summary: one sentence, the plan bar, keep + destinations with % and CHF, mode and cap, then Edit · Pause · Skip next.',
      'Pending approval and unusual-salary cards, with amounts per destination.',
      'Edit plan: splits, Cash Safety Buffer, execution mode, guardrails.',
      'Activity: recent runs and the running total put to work.',
    ],
    states: ['Active', 'Waiting for salary', 'Awaiting approval', 'Executed', 'Partially completed', 'No surplus', 'Unusual salary', 'Skipping next', 'Paused', 'Destination unavailable'],
    data: [
      ['Salary', 'CHF 21\'000, 25th of the month'],
      ['Keep', 'CHF 3\'850 (from AI Budgeting)'],
      ['Allocate', '≈ CHF 25\'000 — the client\'s per-salary cap'],
      ['Plan', 'Save Easy 30 · Invest Easy 40 · Trading 10 · ETF Plan 20'],
      ['Guardrails', 'max 25\'000/salary · min 500 · ask above ±20%'],
    ],
    rules: [
      'Allocatable = available balance − protected liquidity, then capped. Never a flat percentage of salary.',
      'The cap and the minimum are visible where the amounts are shown.',
      'A salary differing by more than ±20% pauses and asks first, whatever the execution mode.',
      'A destination that fails keeps its share in Banking. Never redirect investment money to another product.',
      'Changes apply from the next salary — say it on the edit screen.',
    ],
    copy: ['"Keep CHF 3\'850. Put ≈ CHF 25\'000 to work."', '"Runs on its own · never more than CHF 25\'000 a salary"', '"Not this time."'],
    done: [
      'A reviewer can trace one salary end to end: received → protected → split → placed.',
      'Skip and pause are one tap, and neither destroys the setup.',
      'Every run explains its own arithmetic.',
    ],
  },
  {
    id: 'auto-cover',
    eyebrow: '05 · Smart Liquidity',
    title: 'Auto Cover',
    job: 'Stop a payment failing when the money is simply sitting in another Swissquote product.',
    why: 'The mirror of allocation. Money goes out when it is spare and comes back when it is needed — which is what makes clients comfortable letting it leave in the first place.',
    screens: [
      'Status: on/off, health, capacity split into own cash and credit, limits used this month.',
      'Funding order: the client\'s sources with what each can actually contribute right now.',
      'Edit rules: cover amount (exact or + buffer), limits, trading reserve, Lombard consent.',
      'Recent covers, and the failure state with its two manual routes.',
    ],
    states: ['Off', 'Ready', 'Limited', 'Credit only', 'Unavailable', 'Covered — one source / several / with FX / with Lombard', 'Full cover impossible', 'Limit reached', 'Source unavailable', 'Paused'],
    data: [
      ['Capacity, own cash', 'CHF 32\'260 (Save Easy 24\'000 + Trading 8\'260)'],
      ['Credit', 'Off by default'],
      ['Cover amount', 'Exact shortfall, or + CHF 1\'000 buffer'],
      ['Limits', '25\'000 per payment · 40\'000 per month'],
      ['Trading reserve', 'CHF 10\'000 kept for trading'],
    ],
    rules: [
      'Opt-in only. Off until the client turns it on.',
      'Own cash before credit, always. Lombard is last, needs separate consent, and carries its own per-cover and monthly ceilings.',
      'All or nothing: if the authorised sources cannot cover the whole shortfall, nothing moves. A partial transfer solves nothing.',
      'It never sells investments — put that on the screen, not in a footnote.',
      'Product conditions are respected and shown: open orders, penalty-free limits, market hours.',
    ],
    copy: ['"A payment bigger than your balance shouldn\'t fail when the cash is just sitting elsewhere."', '"Half a transfer solves nothing."', '"Never touched. We don\'t sell your investments to pay a bill."'],
    done: [
      'The client can predict what would happen before it happens.',
      'A credit-funded cover looks and reads differently from a cash-funded one.',
      'Turning it off keeps the configuration.',
    ],
  },
  {
    id: 'transactions',
    eyebrow: '06 · Banking',
    title: 'Transactions & explainability',
    job: 'Make an automated movement as understandable as one the client made themselves.',
    why: 'Automation is only trusted if it can be audited casually — in the moment, on the phone, without support.',
    screens: [
      'List: Smart Liquidity movements distinct from ordinary spending, with a plain inline label.',
      'Detail: amount and status, "Why this happened", the before/after balances, and a link to edit the rule that caused it.',
    ],
    states: ['Booked', 'Pending settlement (T+2)', 'Failed / declined', 'Smart movement — allocation · surplus · cover · with FX · with credit'],
    data: [
      ['Example', 'Auto Cover · from Save Easy, + CHF 13\'260.00'],
      ['Before → after', 'CHF 165\'880.50 → CHF 179\'140.50'],
      ['Reason', 'shortfall, source chosen, amount rule applied'],
    ],
    rules: [
      'Four questions answered every time: what happened, why, where the money went, what it changed.',
      'A borrowed amount is labelled as borrowing, with its rate — never as a transfer.',
      'Pending cash is never shown as spendable.',
      'The rule that caused the movement is one tap away.',
    ],
    copy: ['"Why this happened"', '"Edit the rule that caused this"'],
    done: [
      'Someone who has never opened the settings understands an automated movement from its detail alone.',
    ],
  },
  {
    id: 'card',
    eyebrow: '07 · Banking',
    title: 'Card',
    job: 'Block, limit and check the card in seconds.',
    why: 'Card management is a panic-moment feature. The primary action has to be obvious and reversible.',
    screens: [
      'Card hero with the state visible on the card itself.',
      'Block / unblock as the primary action.',
      'Limits: monthly spend, contactless without PIN, online payments toggle.',
      'Details masked by default, with show then copy. Link across to Pay for the wallets. Replace card.',
    ],
    states: ['Active', 'Blocked', 'Online payments off', 'Details revealed', 'Replacement ordered'],
    data: [
      ['Card', 'Elite card •••• 1234, Swiss Debit Mastercard'],
      ['Monthly limit', 'CHF 10\'000 against ≈ CHF 6\'048 typical spend'],
      ['Contactless', 'CHF 100 per payment without PIN'],
    ],
    rules: [
      'Blocking is one tap, instantly reversible, and states its real consequence.',
      'Card state must be visible everywhere the card appears, not only here.',
      'Sensitive details masked by default.',
      'Wallets live in Pay — this screen links to them rather than duplicating them.',
    ],
    copy: ['"Blocked instantly. Payments already authorised may still land."', '"Off means online payments are declined. Your card still works in shops."'],
    done: [
      'Blocking takes one tap and the state is unmistakable across the app.',
    ],
  },
  {
    id: 'pay',
    eyebrow: '08 · Banking',
    title: 'Pay',
    job: 'One place for every way money leaves Everyday.',
    why: 'Clients think in "how do I pay this?", not in payment rails. Group by their question, not by the back office.',
    screens: [
      'Send money: standard, instant, QR-bill scan, standing orders, eBill.',
      'Card & phone: debit card with live state, Apple Pay, Google Pay, TWINT.',
      'Other currencies: EUR and USD balances, Auto FX, with the conversion cost stated.',
    ],
    states: ['Card active / blocked', 'Wallet added / not added', 'Auto FX on / off', 'Not enough balance → route to liquidity, never a dead end'],
    data: [
      ['Standing orders', '2 active · CHF 5\'339/month'],
      ['eBill', '2 due · CHF 980/month'],
      ['Wallets', 'EUR 8\'612 · USD 12\'050'],
      ['FX spread', '≈ 0.95% ⟨TO CONFIRM⟩'],
    ],
    rules: [
      'Conversion cost is shown before the payment, never after.',
      'A shortfall offers the liquidity that exists elsewhere — it does not simply refuse.',
      'Counts and totals shown here must match the real ledger.',
    ],
    copy: ['"You see it before you pay, not after."', '"There in seconds. Any day, any hour."'],
    done: [
      'Any payment method is reachable in one tap from the hub.',
    ],
  },
];

/* ------------------------------------------------------------------ */
/* Markdown output                                                     */
/* ------------------------------------------------------------------ */
const mdList = (arr) => arr.map((x) => `- ${x}`).join('\n');
const mdTable = (rows) => ['| | |', '|---|---|', ...rows.map(([k, v]) => `| ${k} | ${v} |`)].join('\n');

writeFileSync(
  join(here, '00-foundations.md'),
  `# ${foundations.title}\n\n> ${meta.status}\n\n_${foundations.job}_\n\n` +
    foundations.blocks.map((b) => `## ${b.h}\n\n${b.body.join('\n\n')}`).join('\n\n') +
    `\n\n---\n\n${meta.prototype}\n`,
);

briefs.forEach((b, i) => {
  const n = String(i + 1).padStart(2, '0');
  writeFileSync(
    join(here, `${n}-${b.id}.md`),
    `# ${b.title}\n\n> ${meta.status} · ${b.eyebrow}\n\n**The job.** ${b.job}\n\n**Why it exists.** ${b.why}\n\n` +
      `## Screens to design\n\n${mdList(b.screens)}\n\n` +
      `## States to cover\n\n${b.states.map((s) => `\`${s}\``).join(' · ')}\n\n` +
      `## Data to use (no placeholders)\n\n${mdTable(b.data)}\n\n` +
      `## Rules the design must respect\n\n${mdList(b.rules)}\n\n` +
      `## Copy, in tone\n\n${mdList(b.copy)}\n\n` +
      `## Done when\n\n${b.done.map((d) => `- [ ] ${d}`).join('\n')}\n`,
  );
});

/* ------------------------------------------------------------------ */
/* HTML output                                                         */
/* ------------------------------------------------------------------ */
const esc = (s) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
const inline = (s) =>
  esc(s)
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/`(.+?)`/g, '<code>$1</code>');

const sheet = (b, i) => `
<section class="sheet" id="${b.id}">
  <header class="sheet__head">
    <p class="eyebrow">${esc(b.eyebrow)}</p>
    <h2>${esc(b.title)}</h2>
    <p class="job">${inline(b.job)}</p>
    <p class="why">${inline(b.why)}</p>
  </header>
  <div class="grid">
    <div class="col">
      <h3>Screens to design</h3>
      <ul class="list">${b.screens.map((s) => `<li>${inline(s)}</li>`).join('')}</ul>
      <h3>Data to use <span class="hint">no placeholders</span></h3>
      <dl class="data">${b.data.map(([k, v]) => `<div><dt>${inline(k)}</dt><dd>${inline(v)}</dd></div>`).join('')}</dl>
      <h3>Copy, in tone</h3>
      <ul class="quotes">${b.copy.map((c) => `<li>${inline(c)}</li>`).join('')}</ul>
    </div>
    <div class="col">
      <h3>States to cover</h3>
      <p class="chips">${b.states.map((s) => `<span class="chip">${esc(s)}</span>`).join('')}</p>
      <h3>Rules the design must respect</h3>
      <ul class="list list--rules">${b.rules.map((r) => `<li>${inline(r)}</li>`).join('')}</ul>
      <h3>Done when</h3>
      <ul class="list list--check">${b.done.map((d) => `<li>${inline(d)}</li>`).join('')}</ul>
    </div>
  </div>
  <p class="sheet__foot"><span>${esc(meta.status)}</span><span>${String(i + 1).padStart(2, '0')} / ${String(briefs.length).padStart(2, '0')}</span></p>
</section>`;

const html = `<title>Smart Liquidity Briefs</title>
<style>
:root{
  --ink:#17181c; --ink-2:#4a4f57; --ink-3:#767c86;
  --paper:#f4f3f1; --card:#ffffff; --line:#e4e2de; --line-2:#f0efec;
  --accent:#ee4d22; --accent-soft:#fdece6;
  --ok:#17864b; --warn:#b25e09;
  --mono:ui-monospace,"SF Mono",Menlo,Consolas,monospace;
  --sans:Inter,-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
  --w:min(1120px,100%);
}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){
  --ink:#f2f1ef; --ink-2:#b9bcc2; --ink-3:#8b9098;
  --paper:#131417; --card:#1b1d21; --line:#2c2f35; --line-2:#232529;
  --accent:#ff6a42; --accent-soft:#33190f;
  --ok:#4ec98a; --warn:#e0994a;
}}
:root[data-theme="dark"]{
  --ink:#f2f1ef; --ink-2:#b9bcc2; --ink-3:#8b9098;
  --paper:#131417; --card:#1b1d21; --line:#2c2f35; --line-2:#232529;
  --accent:#ff6a42; --accent-soft:#33190f;
  --ok:#4ec98a; --warn:#e0994a;
}
*{box-sizing:border-box}
body{margin:0;background:var(--paper);color:var(--ink);font-family:var(--sans);line-height:1.55;
  -webkit-font-smoothing:antialiased}
.wrap{width:var(--w);margin:0 auto;padding:0 24px 96px}

/* Cover */
.cover{padding:88px 0 40px;border-bottom:1px solid var(--line)}
.tag{display:inline-block;font-family:var(--mono);font-size:11px;letter-spacing:.12em;text-transform:uppercase;
  color:var(--accent);background:var(--accent-soft);padding:5px 10px;border-radius:3px}
.cover h1{font-size:clamp(38px,6vw,68px);line-height:1.02;letter-spacing:-.03em;margin:22px 0 0;
  font-weight:800;text-wrap:balance;max-width:15ch}
.cover p.lede{font-size:clamp(17px,2vw,20px);color:var(--ink-2);max-width:58ch;margin:20px 0 0}
.cover .meta{margin-top:28px;font-family:var(--mono);font-size:12px;color:var(--ink-3);line-height:1.9}

/* Loop */
.loop{display:flex;flex-wrap:wrap;gap:10px;margin-top:32px}
.loop b{flex:1 1 180px;background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 16px;
  font-size:13px;font-weight:600;display:block;position:relative}
.loop b span{display:block;font-family:var(--mono);font-size:10px;letter-spacing:.1em;text-transform:uppercase;
  color:var(--accent);margin-bottom:6px;font-weight:700}
.loop b em{display:block;font-style:normal;font-weight:400;color:var(--ink-2);font-size:12.5px;margin-top:3px}

/* Index */
.index{margin:44px 0 0;border-top:1px solid var(--line);padding-top:24px}
.index h2{font-family:var(--mono);font-size:11px;letter-spacing:.12em;text-transform:uppercase;color:var(--ink-3);
  margin:0 0 14px;font-weight:600}
.index ol{list-style:none;margin:0;padding:0;display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:2px}
.index a{display:flex;gap:10px;align-items:baseline;padding:9px 10px;border-radius:7px;text-decoration:none;color:inherit}
.index a:hover{background:var(--card)}
.index a i{font-family:var(--mono);font-style:normal;font-size:11px;color:var(--ink-3)}
.index a span{font-weight:600;font-size:14px}

/* Foundations */
.found{margin-top:56px;background:var(--card);border:1px solid var(--line);border-radius:14px;padding:36px}
.found > h2{font-size:26px;letter-spacing:-.02em;margin:6px 0 6px;font-weight:800}
.found .job{color:var(--ink-2);margin:0 0 26px;max-width:62ch}
.found .cols{columns:2;column-gap:44px}
@media(max-width:760px){.found .cols{columns:1}.found{padding:24px}}
.found section{break-inside:avoid;margin:0 0 22px}
.found h3{font-family:var(--mono);font-size:10.5px;letter-spacing:.11em;text-transform:uppercase;color:var(--accent);
  margin:0 0 7px;font-weight:700}
.found p{margin:0 0 8px;font-size:14px;color:var(--ink-2)}
.found strong{color:var(--ink);font-weight:650}

/* Sheets */
.sheet{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:36px;margin-top:22px;
  position:relative;overflow:hidden}
.sheet::before{content:"";position:absolute;inset:0 0 auto 0;height:3px;background:var(--accent)}
.sheet__head{max-width:70ch}
.eyebrow{font-family:var(--mono);font-size:11px;letter-spacing:.12em;text-transform:uppercase;color:var(--ink-3);margin:0}
.sheet h2{font-size:clamp(24px,3.4vw,34px);letter-spacing:-.025em;margin:8px 0 12px;font-weight:800;text-wrap:balance}
.job{font-size:17px;font-weight:600;margin:0 0 8px;color:var(--ink)}
.why{margin:0;color:var(--ink-2);font-size:14.5px}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:36px;margin-top:30px}
@media(max-width:820px){.grid{grid-template-columns:1fr;gap:26px}.sheet{padding:24px}}
.col h3{font-family:var(--mono);font-size:10.5px;letter-spacing:.11em;text-transform:uppercase;color:var(--accent);
  margin:0 0 9px;font-weight:700}
.col h3 .hint{color:var(--ink-3);text-transform:none;letter-spacing:0;font-weight:400}
.col > * + h3{margin-top:24px}
.list{margin:0;padding:0;list-style:none}
.list li{position:relative;padding:0 0 0 16px;margin:0 0 8px;font-size:14px;color:var(--ink-2)}
.list li::before{content:"";position:absolute;left:0;top:9px;width:5px;height:5px;border-radius:50%;background:var(--line);
  outline:1px solid var(--ink-3);outline-offset:-1px}
.list--rules li::before{background:var(--warn);outline-color:var(--warn)}
.list--check li{padding-left:24px}
.list--check li::before{content:"";left:0;top:3px;width:13px;height:13px;border-radius:3px;background:transparent;
  border:1.5px solid var(--ok);outline:none}
.chips{margin:0;display:flex;flex-wrap:wrap;gap:5px}
.chip{font-family:var(--mono);font-size:11px;border:1px solid var(--line);border-radius:20px;padding:3px 9px;color:var(--ink-2);
  background:var(--paper)}
.data{margin:0;display:grid;gap:1px;background:var(--line-2);border:1px solid var(--line-2);border-radius:8px;overflow:hidden}
.data > div{display:flex;justify-content:space-between;gap:14px;background:var(--card);padding:8px 11px}
.data dt{font-size:13px;color:var(--ink-2);margin:0}
.data dd{margin:0;font-family:var(--mono);font-size:12.5px;font-weight:600;text-align:right;font-variant-numeric:tabular-nums}
.quotes{margin:0;padding:0;list-style:none}
.quotes li{font-size:14px;color:var(--ink);border-left:2px solid var(--accent);padding:2px 0 2px 12px;margin:0 0 9px}
.sheet__foot{display:flex;justify-content:space-between;margin:30px 0 0;padding-top:14px;border-top:1px solid var(--line-2);
  font-family:var(--mono);font-size:10.5px;color:var(--ink-3);letter-spacing:.05em;text-transform:uppercase}
code{font-family:var(--mono);font-size:.9em;background:var(--paper);padding:1px 5px;border-radius:4px}

@media print{
  body{background:#fff}
  .wrap{width:auto;padding:0}
  .cover,.found,.sheet{break-inside:avoid;page-break-after:always;border-radius:0;border:none;padding:0 0 24px}
  .index{display:none}
  .sheet::before{display:none}
}
</style>

<div class="wrap">
  <header class="cover">
    <span class="tag">${esc(meta.status)}</span>
    <h1>Smart Liquidity, brief by brief.</h1>
    <p class="lede">${esc(meta.subtitle)}</p>
    <div class="loop">
      <b><span>See</span>Everyday Buying Power<em>What liquidity exists</em></b>
      <b><span>Protect</span>AI Budgeting<em>What life will cost</em></b>
      <b><span>Grow</span>Smart Salary Allocation<em>Where the rest goes</em></b>
      <b><span>Cover</span>Auto Cover<em>Bring it back when needed</em></b>
    </div>
    <p class="meta">One page per feature. If a brief needs two, the feature needs splitting.<br>${esc(meta.prototype)}</p>
    <nav class="index">
      <h2>Briefs</h2>
      <ol>
        <li><a href="#foundations"><i>00</i><span>Foundations — read first</span></a></li>
        ${briefs.map((b, i) => `<li><a href="#${b.id}"><i>${String(i + 1).padStart(2, '0')}</i><span>${esc(b.title)}</span></a></li>`).join('\n        ')}
      </ol>
    </nav>
  </header>

  <section class="found" id="foundations">
    <p class="eyebrow">${esc(foundations.eyebrow)}</p>
    <h2>${esc(foundations.title)}</h2>
    <p class="job">${esc(foundations.job)}</p>
    <div class="cols">
      ${foundations.blocks.map((b) => `<section><h3>${esc(b.h)}</h3>${b.body.map((p) => `<p>${inline(p)}</p>`).join('')}</section>`).join('\n      ')}
    </div>
  </section>

  ${briefs.map(sheet).join('\n  ')}
</div>
`;

writeFileSync(join(here, 'index.html'), html);
console.log(`Wrote 00-foundations.md, ${briefs.length} feature briefs, and index.html`);
