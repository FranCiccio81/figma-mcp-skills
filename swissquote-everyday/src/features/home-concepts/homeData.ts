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
import { dateOf, longDate, money, swissNumber } from '../../lib/format';
import { nextSalaryDayAfter, type Forecast } from '../../state/forecast';
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

/**
 * A rolling window rather than the calendar month: on the 2nd of a month a
 * month-to-date figure is nearly empty and says nothing useful.
 */
export interface Snapshot {
  days: number;
  inflow: number;
  /** Spending only — money moved into savings is not "out". */
  outflow: number;
  /** Moved into Save Easy, Invest Easy, Trading or the Saving Plan. */
  putToWork: number;
}

/**
 * Something the client is working towards, with a real number behind it.
 * A goal is only here if the app can measure it honestly — no invented
 * targets, and nothing the client did not choose or the law did not set.
 */
export interface Goal {
  id: string;
  title: string;
  note: string;
  current: number;
  target: number;
  done: boolean;
  destination: Destination;
}

/** Consecutive months in which the salary allocation ran. Habit, not activity. */
export interface Streak {
  months: number;
  nextRun: string;
}

/* ---- Analytics (Variant D) --------------------------------------- */

export interface TrendPoint {
  day: number;
  value: number;
}

export interface MonthFlow {
  key: string;
  label: string;
  inflow: number;
  outflow: number;
  net: number;
  /** The current month is not over — say so rather than comparing it as if it were. */
  partial: boolean;
}

export interface AllocationSlice {
  key: UniverseKey;
  label: string;
  value: number;
  pct: number;
  destination: Destination;
}

export interface Analytics {
  /** Daily total wealth, oldest first. */
  trend: TrendPoint[];
  months: MonthFlow[];
  allocation: AllocationSlice[];
  /** Share of wealth held in securities, funds and retirement rather than cash. */
  investedShare: number;
  /** Of everything that came in over the window, how much was put to work. */
  putToWorkRate: number;
  /** Liquid cash ÷ typical monthly spending. */
  monthsOfCover: number;
  typicalSpend: number;
  windowDays: number;
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
  /** Last 30 days, for the momentum strip. */
  snapshot: Snapshot;
  goals: Goal[];
  streak: Streak | null;
  analytics: Analytics;
  scenario: HomeScenario;
  firstName: string;
  /** Formats CHF for display, masking every figure when balances are hidden. */
  chf: Money;
  /** The client's privacy choice — screens need it for accessible labels too. */
  balancesHidden: boolean;
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
/* Momentum, goals and habit                                           */
/* ------------------------------------------------------------------ */

const WINDOW_DAYS = 30;

/** Destinations that count as money put to work rather than money spent. */
const AT_WORK = new Set(['saveEasy', 'investEasy', 'tradingCash', 'savingPlan']);

// BACKEND: categorised transaction history across the relationship. The
// prototype reads the same ledger every other screen reads.
function buildSnapshot(state: EngineState): Snapshot {
  const from = state.day - WINDOW_DAYS;
  let inflow = 0;
  let outflow = 0;
  let putToWork = 0;

  for (const t of state.txns) {
    if (t.day <= from || t.day > state.day || t.status === 'failed') continue;
    const moved = t.smart?.destination;
    if (moved && AT_WORK.has(moved)) {
      // A transfer into savings leaves Everyday but does not leave the client.
      putToWork += Math.abs(t.amount);
      continue;
    }
    // Auto Cover brings the client's own money back in — not income.
    if (t.smart?.engine === 'autoCover') continue;
    if (t.amount > 0) inflow += t.amount;
    else outflow += -t.amount;
  }

  return { days: WINDOW_DAYS, inflow, outflow, putToWork };
}

/** Typical monthly spending, from the client's own history. */
function typicalMonthlySpend(state: EngineState): number {
  const from = state.day - 90;
  let total = 0;
  for (const t of state.txns) {
    if (t.day <= from || t.day > state.day || t.status === 'failed') continue;
    if (t.amount >= 0 || t.category === 'smart-liquidity') continue;
    total += -t.amount;
  }
  return total / 3;
}

function buildGoals(state: EngineState, chf: Money, owned: Set<UniverseKey>): Goal[] {
  const goals: Goal[] = [];

  // BACKEND: contributions paid in this tax year, and the year's maximum.
  if (owned.has('plan')) {
    const room = Math.max(0, PILLAR_3A_ALLOWANCE - PILLAR_3A_PAID_IN);
    goals.push({
      id: 'pillar-3a',
      title: 'Your 3a, this year',
      note:
        room > 0
          ? `${chf(room, 0)} to go before 31 December. After that the allowance is gone.`
          : 'Paid in full. Nothing left to do this year.',
      current: PILLAR_3A_PAID_IN,
      target: PILLAR_3A_ALLOWANCE,
      done: room === 0,
      destination: { tab: 'plan' },
    });
  }

  // Six months of the client's own spending — a rule of thumb, and labelled
  // as one. Not a target the bank invented for them.
  if (owned.has('plan') && owned.has('bank')) {
    const target = Math.round((typicalMonthlySpend(state) * 6) / 500) * 500;
    const current = Math.min(state.accounts.saveEasy, target);
    goals.push({
      id: 'safety-net',
      title: 'Six months of spending, set aside',
      note:
        current >= target
          ? `Save Easy covers six months at your usual pace — about ${chf(target, 0)}.`
          : `${chf(target - current, 0)} more and Save Easy covers six months at your usual pace.`,
      current,
      target,
      done: current >= target,
      destination: { tab: 'plan' },
    });
  }

  return goals;
}

/**
 * Consecutive months in which the salary allocation ran. This counts a habit
 * the client set up, not activity the bank wants more of — the distinction
 * matters, and it is why nothing here counts trades.
 */
function buildStreak(state: EngineState): Streak | null {
  const months = new Set<string>();
  for (const t of state.txns) {
    if (t.smart?.engine !== 'allocation' || t.status === 'failed') continue;
    const d = dateOf(t.day);
    months.add(`${d.getUTCFullYear()}-${d.getUTCMonth()}`);
  }
  if (months.size === 0) return null;

  // Walk back month by month from the most recent run; stop at the first gap.
  const keys = [...months].sort();
  const [lastY, lastM] = keys[keys.length - 1].split('-').map(Number);
  let count = 0;
  for (let i = 0; ; i += 1) {
    const m = lastM - i;
    const y = lastY + Math.floor(m / 12);
    if (!months.has(`${y}-${((m % 12) + 12) % 12}`)) break;
    count += 1;
  }

  return { months: count, nextRun: longDate(nextSalaryDayAfter(state.day) + 1) };
}


/* ------------------------------------------------------------------ */
/* Analytics — the numbers Variant D plots                             */
/* ------------------------------------------------------------------ */

const TREND_DAYS = 90;
const MONTH_NAMES = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

/** Does this transaction move money in or out of the relationship? */
function isExternal(t: { category: string; smart?: { engine?: string; destination?: string } }): boolean {
  if (t.smart?.engine === 'autoCover') return false; // own money coming back
  if (t.smart?.destination && AT_WORK.has(t.smart.destination)) return false; // own money moving across
  return t.category !== 'smart-liquidity';
}

/**
 * Total wealth per day, walked backwards from today.
 *
 * BACKEND: a daily valuation snapshot per product. The prototype reconstructs
 * the line from cash movements only, so market performance before today is
 * NOT in it — the chart is labelled accordingly rather than implying a
 * precision the data does not have.
 */
function buildTrend(state: EngineState, today: number): TrendPoint[] {
  const byDay = new Map<number, number>();
  for (const t of state.txns) {
    if (t.status === 'failed' || !isExternal(t)) continue;
    byDay.set(t.day, (byDay.get(t.day) ?? 0) + t.amount);
  }

  const points: TrendPoint[] = [{ day: state.day, value: today }];
  let running = today;
  for (let d = state.day; d > state.day - TREND_DAYS; d -= 1) {
    running -= byDay.get(d) ?? 0;
    points.unshift({ day: d - 1, value: running });
  }
  return points;
}

/** Money in and money out per calendar month, most recent last. */
function buildMonths(state: EngineState): MonthFlow[] {
  const acc = new Map<string, MonthFlow>();
  const currentKey = (() => {
    const d = dateOf(state.day);
    return `${d.getUTCFullYear()}-${d.getUTCMonth()}`;
  })();

  for (const t of state.txns) {
    if (t.status === 'failed' || !isExternal(t) || t.day > state.day) continue;
    const d = dateOf(t.day);
    const key = `${d.getUTCFullYear()}-${d.getUTCMonth()}`;
    const row =
      acc.get(key) ??
      {
        key,
        label: `${MONTH_NAMES[d.getUTCMonth()]}`,
        inflow: 0,
        outflow: 0,
        net: 0,
        partial: key === currentKey,
      };
    if (t.amount > 0) row.inflow += t.amount;
    else row.outflow += -t.amount;
    row.net = row.inflow - row.outflow;
    acc.set(key, row);
  }

  const rows = [...acc.values()].sort((a, b) => {
    const [ay, am] = a.key.split('-').map(Number);
    const [by, bm] = b.key.split('-').map(Number);
    return ay - by || am - bm;
  });

  // The oldest month is cut off by where the history starts, exactly as the
  // current one is cut off by today. Both are marked, or the first bar reads
  // as a good month when it is really half a month.
  const historyStart = dateOf(state.day - TREND_DAYS + 1);
  if (rows.length > 0 && historyStart.getUTCDate() !== 1) rows[0].partial = true;

  return rows;
}

function buildAnalytics(
  state: EngineState,
  universes: Universe[],
  totalWealth: number,
  snapshot: Snapshot,
): Analytics {
  const a = state.accounts;
  const owned = universes.filter((u) => u.owned);

  const allocation: AllocationSlice[] = owned.map((u) => ({
    key: u.key,
    label: u.title,
    value: u.value,
    pct: totalWealth > 0 ? (u.value / totalWealth) * 100 : 0,
    destination: u.destination,
  }));

  // Invested = securities, funds and retirement. Cash and savings accounts
  // are not "invested", however large they are.
  const invested =
    (owned.some((u) => u.key === 'trade') ? TRADING_POSITIONS : 0) +
    (owned.some((u) => u.key === 'plan') ? a.investEasy + a.savingPlan + PILLAR_3A : 0);

  const spend = typicalMonthlySpend(state);
  const liquid = a.everyday + a.saveEasy + a.eurWallet * FX.eurToChf + a.usdWallet * FX.usdToChf;

  return {
    trend: buildTrend(state, totalWealth),
    months: buildMonths(state),
    allocation,
    investedShare: totalWealth > 0 ? (invested / totalWealth) * 100 : 0,
    putToWorkRate: snapshot.inflow > 0 ? (snapshot.putToWork / snapshot.inflow) * 100 : 0,
    monthsOfCover: spend > 0 ? liquid / spend : 0,
    typicalSpend: spend,
    windowDays: snapshot.days,
  };
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
  const ownedKeys = new Set(owned.map((u) => u.key));
  // Money in, money out and the salary habit all live in the Bank space —
  // a client without one has no such history to show.
  const snapshot: Snapshot = ownedKeys.has('bank')
    ? buildSnapshot(state)
    : { days: WINDOW_DAYS, inflow: 0, outflow: 0, putToWork: 0 };

  return {
    totalWealth,
    dayChange,
    universes,
    today,
    loading: home.scenario === 'loading',
    aiUnavailable: home.scenario === 'aiError',
    snapshot,
    goals: buildGoals(state, chf, ownedKeys),
    analytics: buildAnalytics(state, universes, totalWealth, snapshot),
    streak: ownedKeys.has('bank') ? buildStreak(state) : null,
    scenario: home.scenario,
    firstName: 'Léa',
    chf,
    balancesHidden: home.balancesHidden,
  };
}
