/**
 * Home data adapter — the ONE place either Home concept reads from.
 *
 * Both variants consume this shape and nothing else, so swapping the mock for
 * real services is a change to this file alone. Every field carries a
 * `BACKEND:` note naming the capability the real implementation needs; where
 * the prototype already computes something honestly (balances, the liquidity
 * forecast, the Auto Cover state machine) it reads the engine rather than a
 * hardcoded number, so the two Homes can never disagree with the rest of the
 * app.
 */
import {
  FX,
  PENDING_CARD_RESERVED,
  PILLAR_3A,
  PILLAR_3A_ALLOWANCE,
  PILLAR_3A_PAID_IN,
  TRADING_DAY_CHANGE_PCT,
  TRADING_ORDERS_RESERVED,
  TRADING_POSITIONS,
} from '../../data/mockLedger';
import { money, swissNumber } from '../../lib/format';
import type { Forecast } from '../../state/forecast';
import type { AppTab, HomeScenario, Screen } from '../../state/store';
import { useStore } from '../../state/store';
import type { EngineState } from '../../state/types';

/* ------------------------------------------------------------------ */
/* Shapes                                                              */
/* ------------------------------------------------------------------ */

export type UniverseKey = 'trade' | 'bank' | 'plan';

export type Tone = 'positive' | 'neutral' | 'attention';

/** Where a card or an action sends the client. Never invents a destination. */
export interface Destination {
  tab: AppTab;
  /** Only meaningful for the Bank tab. */
  screen?: Screen;
}

export interface Universe {
  key: UniverseKey;
  title: string;
  /** What the client owns in this space, in CHF. Zero when they have not opened it. */
  value: number;
  /** One line under the title — what the space is for. */
  purpose: string;
  /** Exactly one signal per card. More than one and the card stops being scannable. */
  signal: { tone: Tone; text: string };
  destination: Destination;
  /**
   * False when the client has no product in this space. The card stays on the
   * screen — a trade-only client must still be able to find Bank — but it
   * carries no balance and reads as an invitation, not a holding.
   */
  owned: boolean;
}

/**
 * Priority classes, highest first. The order is the product rule, not a
 * styling choice: something the client must do outranks something that
 * merely changed, which outranks an opportunity, which outranks an insight.
 */
export type TodayKind = 'action' | 'change' | 'opportunity' | 'insight';

export const TODAY_RANK: Record<TodayKind, number> = {
  action: 0,
  change: 1,
  opportunity: 2,
  insight: 3,
};

export const TODAY_LABELS: Record<TodayKind, string> = {
  action: 'Needs you',
  change: 'Changed',
  opportunity: 'Opportunity',
  insight: 'Good to know',
};

export interface TodayItem {
  id: string;
  kind: TodayKind;
  title: string;
  body: string;
  /** The figure or record this was derived from — shown so nothing is a black box. */
  basis: string;
  cta?: { label: string; destination: Destination };
}

export interface HomeData {
  /** Sum of everything owned, less anything borrowed. */
  totalWealth: number;
  /**
   * Movement since yesterday's close, across everything owned.
   * BACKEND: an end-of-previous-day valuation snapshot per product. Null when
   * nothing the client holds actually moves daily.
   */
  dayChange: { amount: number; pct: number } | null;
  universes: Universe[];
  /** Already sorted by priority and capped by the caller. */
  today: TodayItem[];
  /** True while the client's positions have not arrived yet. */
  loading: boolean;
  /** The AI service is down — variants must still be useful. */
  aiUnavailable: boolean;
  scenario: HomeScenario;
  firstName: string;
  /** Formats CHF for display, masking every figure when balances are hidden. */
  chf: Money;
}

/* ------------------------------------------------------------------ */
/* Formatting — the hide-balances choice applies to every figure        */
/* ------------------------------------------------------------------ */

/**
 * Hiding balances has to mean every amount on the screen, not just the big
 * one at the top: a card that says "CHF 160'791 is sitting still" has given
 * the number away. Copy is therefore written through this formatter.
 */
export interface Money {
  (value: number, decimals?: number): string;
  signed(value: number): string;
}

const MASK = 'CHF •••';

function makeMoney(hidden: boolean): Money {
  const fn = ((value: number, decimals = 2) =>
    hidden ? MASK : money(value, 'CHF', decimals)) as Money;
  fn.signed = (value: number) =>
    hidden ? MASK : `${value >= 0 ? '+' : '−'}${swissNumber(Math.abs(value))} CHF`;
  return fn;
}

/* ------------------------------------------------------------------ */
/* Universes                                                           */
/* ------------------------------------------------------------------ */

function buildUniverses(
  state: EngineState,
  forecast: Forecast,
  scenario: HomeScenario,
  chf: Money,
): Universe[] {
  const a = state.accounts;

  // BACKEND: positions valuation + intraday performance for the trading account.
  const tradeValue = TRADING_POSITIONS + a.tradingCash;
  const tradeChange = tradeValue - tradeValue / (1 + TRADING_DAY_CHANGE_PCT / 100);

  // BACKEND: multi-currency balances with an indicative FX rate per wallet.
  const bankValue = a.everyday + a.eurWallet * FX.eurToChf + a.usdWallet * FX.usdToChf;
  const availableNow = Math.max(0, a.everyday - PENDING_CARD_RESERVED);

  // BACKEND: savings/retirement product balances + this year's 3a contributions.
  const planValue = a.saveEasy + a.investEasy + a.savingPlan + PILLAR_3A;
  const pillarRoom = Math.max(0, PILLAR_3A_ALLOWANCE - PILLAR_3A_PAID_IN);

  const coverRan = state.status === 'autoCoverExecuted' || state.status === 'autoCoverPending';
  const coverFailed = state.status === 'autoCoverFailed';

  const all: Universe[] = [
    {
      key: 'trade',
      title: 'Trade',
      value: tradeValue,
      purpose: 'Your positions and the cash behind them',
      signal:
        TRADING_DAY_CHANGE_PCT >= 0
          ? { tone: 'positive', text: `Up ${TRADING_DAY_CHANGE_PCT.toFixed(2)}% today · ${chf.signed(tradeChange)}` }
          : {
              tone: 'attention',
              text: `Down ${Math.abs(TRADING_DAY_CHANGE_PCT).toFixed(2)}% today · ${chf.signed(tradeChange)}`,
            },
      destination: { tab: 'trade' },
      owned: scenario !== 'bankOnly',
    },
    {
      key: 'bank',
      title: 'Bank',
      value: bankValue,
      purpose: 'Everyday, your cards and your payments',
      signal: coverFailed
        ? { tone: 'attention', text: 'A payment needs your attention' }
        : coverRan
          ? { tone: 'neutral', text: 'Auto Cover moved money to keep a payment going through' }
          : { tone: 'neutral', text: `${chf(availableNow)} ready to spend now` },
      destination: { tab: 'bank', screen: 'home' },
      owned: scenario !== 'tradeOnly',
    },
    {
      key: 'plan',
      title: 'Plan',
      value: planValue,
      purpose: 'Saving, investing and your 3a',
      signal:
        pillarRoom > 0
          ? { tone: 'neutral', text: `${chf(pillarRoom, 0)} of 3a allowance still open this year` }
          : { tone: 'positive', text: "This year's 3a allowance is fully paid in" },
      destination: { tab: 'plan' },
      owned: scenario !== 'tradeOnly' && scenario !== 'bankOnly',
    },
  ];

  // A space the client has not opened keeps its place in the layout — the
  // order never changes — but shows an invitation instead of a balance.
  const INVITATION: Record<UniverseKey, string> = {
    trade: 'Open a trading account and start investing',
    bank: 'Open an Everyday account, with a card and payments',
    plan: 'Start a 3a or a saving plan',
  };
  // `forecast` is read by the Today builder; kept in the signature so the
  // adapter has one entry point per screen load.
  void forecast;
  return all.map((u) =>
    u.owned ? u : { ...u, value: 0, signal: { tone: 'neutral' as Tone, text: INVITATION[u.key] } },
  );
}

/* ------------------------------------------------------------------ */
/* Today                                                               */
/* ------------------------------------------------------------------ */

/**
 * The prioritised list. Everything here is derived from state the app already
 * holds — nothing is scheduled, promoted or personalised by a model. An AI
 * layer may later re-word these; it may not invent them.
 */
function buildToday(
  state: EngineState,
  forecast: Forecast,
  universes: Universe[],
  chf: Money,
): TodayItem[] {
  const shown = new Set(universes.filter((u) => u.owned).map((u) => u.key));
  const items: TodayItem[] = [];
  const a = state.accounts;

  /* --- action required ------------------------------------------- */

  // BACKEND: liquidity state machine — the same one Auto Cover already runs on.
  if (shown.has('bank') && state.status === 'autoCoverFailed') {
    items.push({
      id: 'cover-failed',
      kind: 'action',
      title: 'A payment could not go through',
      body: 'Auto Cover tried your authorised sources and none of them had enough. Move money in, or free some up.',
      basis: 'Auto Cover attempt, today',
      cta: { label: 'See what happened', destination: { tab: 'bank', screen: 'autoCover' } },
    });
  }

  // BACKEND: salary detection + the allocation rule engine.
  if (shown.has('bank') && state.pendingAllocation) {
    const p = state.pendingAllocation;
    items.push({
      id: 'allocation-pending',
      kind: 'action',
      title: 'Your allocation is ready for you',
      body: p.anomaly
        ? `${p.anomaly} It is waiting for your go-ahead rather than guessing.`
        : `${chf(p.total)} from your salary is ready to move, the way you set it up.`,
      basis: `Salary of ${chf(p.received)} received`,
      cta: { label: 'Review it', destination: { tab: 'bank', screen: 'allocation' } },
    });
  }

  // BACKEND: collateral monitoring on the Lombard facility.
  if (state.flags.marginCall) {
    items.push({
      id: 'margin-call',
      kind: 'action',
      title: 'Your Lombard cover is below the required level',
      body: 'You have until the deadline to add cover or reduce what you have borrowed.',
      basis: 'Collateral check on your Lombard facility',
      cta: { label: 'Open Lombard', destination: { tab: 'bank', screen: 'autoCover' } },
    });
  }

  /* --- important change ------------------------------------------ */

  const today = state.txns.filter((t) => t.day === state.day && t.status !== 'failed');

  const salary = today.find((t) => t.category === 'salary');
  if (shown.has('bank') && salary) {
    // The ledger books a bonus under the same category; the copy should not
    // call a one-off bonus "your salary".
    const isBonus = /bonus/i.test(salary.label);
    items.push({
      id: 'salary-in',
      kind: 'change',
      title: isBonus ? 'Your bonus landed' : 'Your salary landed',
      body: `${chf(salary.amount)} · ${salary.label}. Your allocation runs on the next business day.`,
      basis: `Credit booked today · ${salary.label}`,
      cta: { label: 'See your plan', destination: { tab: 'bank', screen: 'allocation' } },
    });
  }

  const cover = today.find((t) => t.smart?.engine === 'autoCover');
  if (shown.has('bank') && cover?.smart) {
    items.push({
      id: 'cover-ran',
      kind: 'change',
      title: 'Auto Cover moved money for you',
      body: `${chf(Math.abs(cover.amount))} in, and your balance went from ${chf(cover.smart.balanceBefore)} to ${chf(cover.smart.balanceAfter)}. The full reason is on the transaction.`,
      basis: cover.smart.title,
      cta: { label: 'See the transaction', destination: { tab: 'bank', screen: 'transactions' } },
    });
  }

  // BACKEND: intraday portfolio valuation; the threshold is a product decision,
  // not a model output — below it, a move is noise and does not earn the slot.
  if (shown.has('trade') && Math.abs(TRADING_DAY_CHANGE_PCT) >= 0.5) {
    const tradeValue = TRADING_POSITIONS + a.tradingCash;
    const delta = tradeValue - tradeValue / (1 + TRADING_DAY_CHANGE_PCT / 100);
    items.push({
      id: 'trade-move',
      kind: 'change',
      title: `Your portfolio is ${TRADING_DAY_CHANGE_PCT >= 0 ? 'up' : 'down'} ${Math.abs(TRADING_DAY_CHANGE_PCT).toFixed(2)}% today`,
      body: `${chf.signed(delta)} since yesterday's close.`,
      basis: 'Intraday valuation of your positions',
      cta: { label: 'Open Trade', destination: { tab: 'trade' } },
    });
  }

  /* --- opportunity ----------------------------------------------- */

  // Surplus = own cash above what AI Budgeting says this cycle needs. A
  // proposal only; nothing moves without the normal confirmation flow.
  const surplus = Math.max(0, a.everyday - PENDING_CARD_RESERVED - forecast.keep);
  if (shown.has('bank') && surplus >= 5_000) {
    items.push({
      id: 'surplus',
      kind: 'opportunity',
      title: `${chf(surplus, 0)} is sitting still`,
      body: `That is what you hold above the ${chf(forecast.keep, 0)} this cycle looks like it needs. You decide whether it moves.`,
      basis: `AI Budgeting forecast to ${forecast.horizonDays} days out`,
      cta: { label: 'See the options', destination: { tab: 'bank', screen: 'budgeting' } },
    });
  }

  // BACKEND: year-to-date 3a contributions and the current tax-year maximum.
  const pillarRoom = Math.max(0, PILLAR_3A_ALLOWANCE - PILLAR_3A_PAID_IN);
  if (shown.has('plan') && pillarRoom > 0) {
    items.push({
      id: 'pillar-3a',
      kind: 'opportunity',
      title: `${chf(pillarRoom, 0)} of 3a allowance is still open`,
      body: 'Paying it in before the year ends is the difference between using this year’s allowance and losing it.',
      basis: `${chf(PILLAR_3A_PAID_IN, 0)} of ${chf(PILLAR_3A_ALLOWANCE, 0)} paid in`,
      cta: { label: 'Open 3a', destination: { tab: 'plan' } },
    });
  }

  /* --- insight ---------------------------------------------------- */

  if (shown.has('bank')) {
    items.push({
      id: 'forecast',
      kind: 'insight',
      title: `About ${chf(forecast.buffer, 0)} before your next salary`,
      body: `Between ${chf(forecast.bufferLow, 0)} and ${chf(forecast.bufferHigh, 0)}, going on how this cycle usually looks. An estimate, not a promise.`,
      basis: `${forecast.horizonDays} days of your own history · ${forecast.confidence} confidence`,
      cta: { label: 'See the detail', destination: { tab: 'bank', screen: 'budgeting' } },
    });
  }

  if (shown.has('trade')) {
    items.push({
      id: 'orders-reserved',
      kind: 'insight',
      title: `${chf(TRADING_ORDERS_RESERVED, 0)} is committed to open orders`,
      body: 'That cash is spoken for until those orders fill or you cancel them.',
      basis: 'Open orders on your trading account',
      cta: { label: 'Open Trade', destination: { tab: 'trade' } },
    });
  }

  return prioritise(items);
}

/**
 * Ordering rule for the Today list. Priority decides, with one correction:
 * never more than two of the same kind up front, so the third slot always
 * brings something different. Three "changed" cards in a row read as a feed;
 * the point of this list is that it reads as a summary.
 */
export function prioritise(items: TodayItem[]): TodayItem[] {
  const sorted = [...items].sort((x, y) => TODAY_RANK[x.kind] - TODAY_RANK[y.kind]);
  const seen: Partial<Record<TodayKind, number>> = {};
  const lead: TodayItem[] = [];
  const held: TodayItem[] = [];
  for (const item of sorted) {
    const n = seen[item.kind] ?? 0;
    if (n < 2) {
      seen[item.kind] = n + 1;
      lead.push(item);
    } else {
      held.push(item);
    }
  }
  return [...lead, ...held];
}

/* ------------------------------------------------------------------ */
/* Hook                                                                */
/* ------------------------------------------------------------------ */

export function useHomeData(): HomeData {
  const { state, forecast, home } = useStore();
  const a = state.accounts;

  const chf = makeMoney(home.balancesHidden);
  const universes = buildUniverses(state, forecast, home.scenario, chf);

  // The roll-up of what is owned, less what is borrowed — the same arithmetic
  // as the wealth breakdown, so the two always agree.
  const owned = universes.filter((u) => u.owned);
  const totalWealth = owned.reduce((sum, u) => sum + u.value, 0) - a.lombardDrawn;

  // Only the trading account moves intraday; cash and savings do not. Passing
  // that through honestly beats inventing a whole-portfolio tick.
  const tradeUniverse = owned.find((u) => u.key === 'trade');
  const dayChange = tradeUniverse
    ? (() => {
        const delta = tradeUniverse.value - tradeUniverse.value / (1 + TRADING_DAY_CHANGE_PCT / 100);
        return { amount: delta, pct: totalWealth > 0 ? (delta / (totalWealth - delta)) * 100 : 0 };
      })()
    : null;

  const today = home.scenario === 'quiet' ? [] : buildToday(state, forecast, universes, chf);

  return {
    totalWealth,
    dayChange,
    universes,
    today,
    loading: home.scenario === 'loading',
    aiUnavailable: home.scenario === 'aiError',
    scenario: home.scenario,
    firstName: 'Léa',
    chf,
  };
}
