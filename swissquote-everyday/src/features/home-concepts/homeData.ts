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
  DIVIDENDS_YTD,
  FEES_LAST_MONTH,
  FEES_THIS_MONTH,
  FX,
  LOMBARD_LIMIT,
  LOMBARD_RATE_PA,
  MARKET,
  NEXT_DIVIDEND,
  NEXT_EARNINGS,
  OPEN_ORDER_BOOK,
  PORTFOLIO_DRAWDOWN_90D,
  PORTFOLIO_VOLATILITY_30D,
  POSITIONS,
  RECURRING_DEBITS,
  TRADING_PERIOD_GAIN,
  PENDING_CARD_RESERVED,
  PILLAR_3A,
  PILLAR_3A_ALLOWANCE,
  PILLAR_3A_PAID_IN,
  TRADING_DAY_CHANGE_PCT,
  TRADING_ORDERS_RESERVED,
  TRADING_POSITIONS,
} from '../../data/mockLedger';
import { dateOf, dayOfMonth, longDate, money, shortDate, swissNumber } from '../../lib/format';
import { nextSalaryDayAfter, type Forecast } from '../../state/forecast';
import type { AppTab, HomeScenario, Screen } from '../../state/store';
import { useStore } from '../../state/store';
import type { EngineState } from '../../state/types';

/* ------------------------------------------------------------------ */
/* Shapes                                                              */
/* ------------------------------------------------------------------ */

export type UniverseKey = 'trade' | 'bank' | 'plan';

/**
 * The worlds a dashboard row can belong to. Crypto is not a universe of its
 * own — it lives inside Trade — but it moves differently enough that a
 * client scanning the list wants to pick it out.
 */
export type MetricAccent = UniverseKey | 'crypto';

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

/**
 * The three states a financial life is in on any given day, as rings.
 * Deliberately parallel to a fitness dashboard's readiness rings: one for
 * what you can spend, one for how the position moved, one for how much of
 * it is at risk.
 */
export interface Ring {
  key: 'liquidity' | 'performance' | 'exposure';
  label: string;
  /** 0–100, for the arc. */
  pct: number;
  /** The figure itself — the ring is the shape, this is the truth. */
  display: string;
  caption: string;
  /** How the arc's fill should read. */
  tone: Tone;
  destination: Destination;
}

/** Which client a metric is for. Most people are one; some are both. */
export type MetricPreset = 'everyday' | 'trader';

/**
 * A dashboard row: a figure, what it is usually, and which way it moved.
 * Direction is never carried by colour alone — the arrow and the note say it.
 */
export interface Metric {
  id: string;
  /**
   * Which world the row belongs to. Rendered as a coloured rail down its left
   * edge, in the same hue that space wears everywhere else in the app — so a
   * long list stays scannable: find the colour, then read the label.
   */
  accent: MetricAccent;
  label: string;
  value: string;
  /** The comparison figure, printed under the value. */
  baseline?: string;
  /** What the baseline is, for the accessible name. */
  baselineLabel?: string;
  trend: 'up' | 'down' | 'flat';
  /** Whether the move is good, bad or simply a fact for this metric. */
  sentiment: 'good' | 'bad' | 'neutral';
  presets: MetricPreset[];
  destination?: Destination;
}

/** A monitor card: a handful of checks reduced to one state. */
export interface Monitor {
  key: 'risk' | 'market';
  title: string;
  state: string;
  detail: string;
  tone: Tone;
  checks?: { label: string; ok: boolean; note: string }[];
}

/** One line of proof under a finding — the figure, named. */
export interface Evidence {
  label: string;
  value: string;
}

/**
 * A finding about the client's own position.
 *
 * Computed here, from the same numbers the charts plot. The AI layer may
 * re-word a finding; it may not invent one, rank one differently, or act on
 * one. Anything transactional goes through the app's normal confirmation.
 */
export interface Finding {
  id: string;
  headline: string;
  /**
   * What the finding is about, with no figure in it. The closed tile uses
   * this: enough to be worth opening, nothing given away to someone reading
   * over a shoulder.
   */
  teaser: string;
  /** The plain-language version, used verbatim when the service is down. */
  detail: string;
  evidence: Evidence[];
  cta?: { label: string; destination: Destination };
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
  /** Ranked by how much a client could actually do about them. */
  findings: Finding[];
  rings: Ring[];
  metrics: Metric[];
  monitors: Monitor[];
  /** Resting orders — empty when the client holds no trading account. */
  orders: OrderRow[];
}

/**
 * A resting order, reduced to what makes it worth a tap: which instrument,
 * which way, and the cash it is holding. The mark is the ticker rather than a
 * logo — a bank cannot ship a brand mark for every instrument it lists, and a
 * missing one is worse than none.
 */
export interface OrderRow {
  ticker: string;
  name: string;
  side: 'buy' | 'sell';
  /** "Buy 40 at CHF 84.20" */
  detail: string;
  reserved: string;
}

/** The measured part of the analytics, before anything is derived from it. */
type AnalyticsBase = Omit<Analytics, 'findings' | 'rings' | 'metrics' | 'monitors' | 'orders'>;

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


/* ------------------------------------------------------------------ */
/* Rings, metrics and monitors — the at-a-glance layer                  */
/* ------------------------------------------------------------------ */

/** Average Everyday balance over the window, walked back from today. */
function averageEverydayBalance(state: EngineState, days: number): number {
  let running = state.accounts.everyday;
  let total = running;
  const byDay = new Map<number, number>();
  for (const t of state.txns) {
    if (t.status === 'failed') continue;
    byDay.set(t.day, (byDay.get(t.day) ?? 0) + t.amount);
  }
  for (let d = state.day; d > state.day - days; d -= 1) {
    running -= byDay.get(d) ?? 0;
    total += running;
  }
  return total / (days + 1);
}

/** Recurring debits still to be taken before the next salary lands. */
function committedBeforeSalary(state: EngineState): { total: number; next: { label: string; amount: number; day: number } | null } {
  const salaryDay = nextSalaryDayAfter(state.day);
  let total = 0;
  let next: { label: string; amount: number; day: number } | null = null;
  // Look a full cycle ahead so the row still says something useful on a day
  // when nothing happens to fall before the next salary.
  for (let d = state.day + 1; d <= state.day + 45; d += 1) {
    const dom = dayOfMonth(d);
    for (const r of RECURRING_DEBITS) {
      if (r.dayOfMonth !== dom) continue;
      if (d <= salaryDay) total += r.amount;
      if (!next) next = { label: r.label.split(' — ')[0], amount: r.amount, day: d };
    }
  }
  return { total, next };
}

/**
 * The daily state, in three rings.
 *
 * Each is a percentage of something stated, never a score the client cannot
 * reconstruct: cover against a six-month rule of thumb, today's move inside a
 * ±2% band, and the share of wealth actually at risk.
 */
function buildRings(
  analytics: AnalyticsBase,
  dayChangePct: number,
  chf: Money,
  owned: Set<UniverseKey>,
): Ring[] {
  const rings: Ring[] = [];

  if (owned.has('bank')) {
    const cover = analytics.monthsOfCover;
    rings.push({
      key: 'liquidity',
      label: 'Liquidity',
      pct: Math.max(0, Math.min(100, (cover / 6) * 100)),
      // Kept to one line so the three stats share a baseline; the unit is
      // spelled out in the caption underneath.
      display: cover >= 10 ? `${Math.round(cover)} mo` : `${cover.toFixed(1)} mo`,
      caption: `of cover at ${chf(analytics.typicalSpend, 0)} a month`,
      tone: cover >= 3 ? 'positive' : 'attention',
      destination: { tab: 'bank', screen: 'home' },
    });
  }

  if (owned.has('trade')) {
    // A ±2% band: wide enough that an ordinary day sits mid-ring, narrow
    // enough that a real move is visible. The number is the truth; the arc
    // only says where in the band it fell.
    const BAND = 2;
    rings.push({
      key: 'performance',
      label: 'Day move',
      pct: Math.max(0, Math.min(100, ((dayChangePct + BAND) / (BAND * 2)) * 100)),
      display: `${dayChangePct >= 0 ? '+' : '−'}${Math.abs(dayChangePct).toFixed(2)}%`,
      caption: 'across your positions today',
      tone: dayChangePct >= 0 ? 'positive' : 'attention',
      destination: { tab: 'trade' },
    });
  }

  rings.push({
    key: 'exposure',
    label: 'Exposure',
    pct: Math.max(0, Math.min(100, analytics.investedShare)),
    display: `${analytics.investedShare.toFixed(0)}%`,
    caption: 'invested — the rest is cash',
    tone: 'neutral',
    destination: { tab: 'plan' },
  });

  return rings;
}

/** Direction and whether that direction is good for THIS metric. */
function move(
  current: number,
  baseline: number,
  higherIsBetter: boolean,
): { trend: Metric['trend']; sentiment: Metric['sentiment'] } {
  // Under 2% apart is noise, not a move.
  const delta = baseline === 0 ? current : (current - baseline) / Math.abs(baseline);
  if (Math.abs(delta) < 0.02) return { trend: 'flat', sentiment: 'neutral' };
  const up = delta > 0;
  return { trend: up ? 'up' : 'down', sentiment: up === higherIsBetter ? 'good' : 'bad' };
}

function buildMetrics(
  state: EngineState,
  forecast: Forecast,
  analytics: AnalyticsBase,
  chf: Money,
  hidden: boolean,
  owned: Set<UniverseKey>,
): Metric[] {
  const a = state.accounts;
  const metrics: Metric[] = [];
  // A typographic minus, to match every other figure in the app.
  const pct = (v: number, digits = 1) =>
    hidden ? '•••' : `${v < 0 ? '−' : ''}${Math.abs(v).toFixed(digits)}%`;

  /* ---- The everyday client ------------------------------------- */
  if (owned.has('bank')) {
    const availableNow = Math.max(0, a.everyday - PENDING_CARD_RESERVED);
    const avgBalance = averageEverydayBalance(state, 30);
    metrics.push({
      id: 'available',
      accent: 'bank',
      label: 'Available to spend',
      value: chf(availableNow, 0),
      baseline: chf(avgBalance, 0),
      baselineLabel: '30-day average',
      ...move(availableNow, avgBalance, true),
      presets: ['everyday'],
      destination: { tab: 'bank', screen: 'home' },
    });

    const { total: committed, next: nextFixed } = committedBeforeSalary(state);
    metrics.push({
      id: 'committed',
      accent: 'bank',
      label: 'Fixed costs before salary',
      value: chf(committed, 0),
      baseline: nextFixed
        ? `next: ${nextFixed.label} ${chf(nextFixed.amount, 0)} on ${shortDate(nextFixed.day)}`
        : chf(forecast.keep, 0),
      baselineLabel: 'next standing debit',
      trend: 'flat',
      sentiment: 'neutral',
      presets: ['everyday'],
      destination: { tab: 'bank', screen: 'pay' },
    });

    const spend30 = state.txns
      .filter((t) => t.day > state.day - 30 && t.day <= state.day && t.amount < 0 && t.category !== 'smart-liquidity')
      .reduce((sum, t) => sum + -t.amount, 0);
    metrics.push({
      id: 'spending',
      accent: 'bank',
      label: 'Spending · 30 days',
      value: chf(spend30, 0),
      baseline: chf(analytics.typicalSpend, 0),
      baselineLabel: 'your usual month',
      ...move(spend30, analytics.typicalSpend, false),
      presets: ['everyday'],
      destination: { tab: 'bank', screen: 'transactions' },
    });

    const subs = RECURRING_DEBITS.reduce((sum, r) => sum + r.amount, 0);
    metrics.push({
      id: 'recurring',
      accent: 'bank',
      label: 'Recurring, per month',
      value: chf(subs, 0),
      baseline: `${RECURRING_DEBITS.length} standing items`,
      baselineLabel: 'count',
      trend: 'flat',
      sentiment: 'neutral',
      presets: ['everyday'],
      destination: { tab: 'bank', screen: 'pay' },
    });

    // The comparison is the client's own three-month rate — not a target
    // the bank invented for them.
    let in90 = 0;
    let work90 = 0;
    for (const t of state.txns) {
      if (t.day <= state.day - 90 || t.day > state.day || t.status === 'failed') continue;
      const dest = t.smart?.destination;
      if (dest && AT_WORK.has(dest)) work90 += Math.abs(t.amount);
      else if (t.amount > 0 && isExternal(t)) in90 += t.amount;
    }
    const rate90 = in90 > 0 ? (work90 / in90) * 100 : 0;
    metrics.push({
      id: 'put-to-work',
      accent: 'plan',
      label: 'Put to work · 30 days',
      value: pct(analytics.putToWorkRate, 0),
      baseline: `${pct(rate90, 0)} over 3 months`,
      baselineLabel: 'your own rate',
      ...move(analytics.putToWorkRate, rate90, true),
      presets: ['everyday'],
      destination: { tab: 'bank', screen: 'allocation' },
    });
  }

  /* ---- The trader ------------------------------------------------ */
  if (owned.has('trade')) {
    const tradeValue = TRADING_POSITIONS + a.tradingCash;
    const dayPnl = tradeValue - tradeValue / (1 + TRADING_DAY_CHANGE_PCT / 100);
    metrics.push({
      id: 'day-pnl',
      accent: 'trade',
      label: 'Day P&L',
      value: hidden ? 'CHF •••' : `${dayPnl >= 0 ? '+' : '−'}${swissNumber(Math.abs(dayPnl), 0)} CHF`,
      baseline: `${TRADING_DAY_CHANGE_PCT >= 0 ? '+' : '−'}${Math.abs(TRADING_DAY_CHANGE_PCT).toFixed(2)}%`,
      baselineLabel: 'since yesterday’s close',
      trend: dayPnl >= 0 ? 'up' : 'down',
      sentiment: dayPnl >= 0 ? 'good' : 'bad',
      presets: ['everyday', 'trader'],
      destination: { tab: 'trade' },
    });

    metrics.push({
      id: 'period-pnl',
      accent: 'trade',
      label: 'P&L · this period',
      value: hidden
        ? 'CHF •••'
        : `${TRADING_PERIOD_GAIN >= 0 ? '+' : '−'}${swissNumber(Math.abs(TRADING_PERIOD_GAIN), 0)} CHF`,
      baseline: 'since the start of the week',
      baselineLabel: 'period',
      trend: TRADING_PERIOD_GAIN >= 0 ? 'up' : 'down',
      sentiment: TRADING_PERIOD_GAIN >= 0 ? 'good' : 'bad',
      presets: ['everyday', 'trader'],
      destination: { tab: 'trade' },
    });

    const buyingPower = Math.max(0, a.tradingCash - TRADING_ORDERS_RESERVED);
    metrics.push({
      id: 'buying-power',
      accent: 'trade',
      label: 'Buying power',
      value: chf(buyingPower, 0),
      baseline: `${chf(TRADING_ORDERS_RESERVED, 0)} reserved`,
      baselineLabel: 'for open orders',
      trend: 'flat',
      sentiment: 'neutral',
      presets: ['trader'],
      destination: { tab: 'trade' },
    });

    // BACKEND: instrument classification, so crypto can be told apart from
    // equities and funds without matching on names.
    const crypto = POSITIONS.filter((pos) => /bitcoin|ethereum|crypto|ETP/i.test(pos.name));
    if (crypto.length > 0) {
      const cryptoValue = crypto.reduce((sum, pos) => sum + pos.value, 0);
      const cryptoDay =
        crypto.reduce((sum, pos) => sum + pos.value * pos.dayPct, 0) / (cryptoValue || 1);
      metrics.push({
        id: 'crypto',
        accent: 'crypto',
        label: 'Crypto',
        value: chf(cryptoValue, 0),
        baseline: `${cryptoDay >= 0 ? '+' : '−'}${Math.abs(cryptoDay).toFixed(2)}% today · ${pct(
          (cryptoValue / TRADING_POSITIONS) * 100,
          1,
        )} of your positions`,
        baselineLabel: 'today, and its weight',
        trend: cryptoDay >= 0 ? 'up' : 'down',
        sentiment: cryptoDay >= 0 ? 'good' : 'bad',
        presets: ['everyday', 'trader'],
        destination: { tab: 'trade' },
      });
    }

    const top = [...POSITIONS].sort((x, y) => y.value - x.value)[0];
    const topWeight = (top.value / TRADING_POSITIONS) * 100;
    metrics.push({
      id: 'largest-position',
      accent: 'trade',
      label: `Largest position · ${top.ticker}`,
      value: pct(topWeight, 1),
      baseline: chf(top.value, 0),
      baselineLabel: 'of the trading account',
      ...move(topWeight, 20, false),
      presets: ['trader'],
      destination: { tab: 'trade' },
    });

    metrics.push({
      id: 'volatility',
      accent: 'trade',
      label: 'Volatility · 30 days',
      value: pct(PORTFOLIO_VOLATILITY_30D, 1),
      baseline: '12–15% typical ⟨TO CONFIRM⟩',
      baselineLabel: 'reference range',
      trend: 'flat',
      sentiment: 'neutral',
      presets: ['trader'],
      destination: { tab: 'trade' },
    });

    metrics.push({
      id: 'drawdown',
      accent: 'trade',
      label: 'Drawdown from peak · 90d',
      value: pct(PORTFOLIO_DRAWDOWN_90D, 1),
      baseline: 'peak-to-trough',
      baselineLabel: 'over 90 days',
      trend: 'down',
      sentiment: 'neutral',
      presets: ['trader'],
      destination: { tab: 'trade' },
    });

    // No "Orders — 2 open" row: the order strip above the dashboard says the
    // same thing with the instruments in it, and a count on its own is not a
    // figure anyone can act on.

    metrics.push({
      id: 'fees',
      accent: 'trade',
      label: 'Fees · this month',
      value: chf(FEES_THIS_MONTH, 0),
      baseline: chf(FEES_LAST_MONTH, 0),
      baselineLabel: 'last month',
      ...move(FEES_THIS_MONTH, FEES_LAST_MONTH, false),
      presets: ['trader'],
      destination: { tab: 'trade' },
    });

    metrics.push({
      id: 'dividends',
      accent: 'trade',
      label: 'Dividends · this year',
      value: chf(DIVIDENDS_YTD, 0),
      baseline: `${NEXT_DIVIDEND.label} ${chf(NEXT_DIVIDEND.amount, 0)} in ${NEXT_DIVIDEND.inDays} days`,
      baselineLabel: 'next payment',
      trend: 'up',
      sentiment: 'good',
      presets: ['trader'],
      destination: { tab: 'trade' },
    });

    metrics.push({
      id: 'lombard',
      accent: 'bank',
      label: 'Lombard drawn',
      value: chf(a.lombardDrawn, 0),
      baseline: `${chf(a.lombardAvailable, 0)} available of ${chf(LOMBARD_LIMIT, 0)} · ${LOMBARD_RATE_PA}% p.a.`,
      baselineLabel: 'credit line',
      trend: 'flat',
      sentiment: 'neutral',
      presets: ['trader'],
      destination: { tab: 'bank', screen: 'autoCover' },
    });
  }

  /* ---- Held by both — last, so each preset leads with its own ---- */
  if (owned.has('bank')) {
    const fx = a.eurWallet * FX.eurToChf + a.usdWallet * FX.usdToChf;
    metrics.push({
      id: 'fx',
      accent: 'bank',
      label: 'Held in other currencies',
      value: chf(fx, 0),
      baseline: `EUR ${hidden ? '•••' : swissNumber(a.eurWallet, 0)} · USD ${
        hidden ? '•••' : swissNumber(a.usdWallet, 0)
      }`,
      baselineLabel: 'wallets',
      trend: 'flat',
      sentiment: 'neutral',
      presets: ['everyday', 'trader'],
      destination: { tab: 'bank', screen: 'pay' },
    });
  }

  return metrics;
}

/**
 * Two monitors, in the shape a health dashboard uses them: a set of checks
 * reduced to one line, and a live state with a timestamp.
 */
function buildMonitors(
  state: EngineState,
  analytics: AnalyticsBase,
  chf: Money,
  owned: Set<UniverseKey>,
): Monitor[] {
  const a = state.accounts;
  const monitors: Monitor[] = [];

  // Thresholds are product decisions, written here rather than hidden.
  const top = [...POSITIONS].sort((x, y) => y.value - x.value)[0];
  const topWeight = (top.value / TRADING_POSITIONS) * 100;
  const checks = [
    {
      label: 'Cash buffer',
      ok: analytics.monthsOfCover >= 3,
      note: `${analytics.monthsOfCover.toFixed(1)} months of spending, against a 3-month floor`,
    },
    {
      label: 'Borrowing',
      ok: a.lombardDrawn === 0,
      note: a.lombardDrawn === 0 ? 'Nothing drawn on your credit line' : `${chf(a.lombardDrawn, 0)} drawn`,
    },
    {
      label: 'Single position',
      ok: topWeight < 25,
      note: `${top.ticker} is ${topWeight.toFixed(1)}% of the trading account, against a 25% flag`,
    },
    {
      label: 'Drawdown',
      ok: PORTFOLIO_DRAWDOWN_90D > -10,
      note: `−${Math.abs(PORTFOLIO_DRAWDOWN_90D).toFixed(1)}% from peak over 90 days, against a −10% flag`,
    },
    {
      label: 'Payments',
      ok: state.status !== 'autoCoverFailed',
      note: state.status === 'autoCoverFailed' ? 'A payment could not go through' : 'Everything went through',
    },
  ];
  const passing = checks.filter((c) => c.ok).length;

  monitors.push({
    key: 'risk',
    title: 'Risk monitor',
    state: passing === checks.length ? 'Within range' : `${checks.length - passing} to look at`,
    detail: `${passing}/${checks.length} checks`,
    tone: passing === checks.length ? 'positive' : 'attention',
    checks,
  });

  if (owned.has('trade')) {
    monitors.push({
      key: 'market',
      title: 'Market',
      state: MARKET.open ? 'Open' : 'Closed',
      detail: MARKET.open
        ? `${MARKET.venue} · closes ${MARKET.closesAt}`
        : `${MARKET.venue} · opens tomorrow`,
      tone: 'neutral',
      checks: [
        {
          label: 'Next earnings',
          ok: true,
          note: `${NEXT_EARNINGS.label} reports in ${NEXT_EARNINGS.inDays} days`,
        },
      ],
    });
  }

  return monitors;
}

/**
 * What stands out in this position. Ranked by actionability: something the
 * client can do this week outranks something structural, which outranks an
 * observation. Thresholds are product decisions, written here in the open —
 * no model chooses what counts as notable.
 */
function buildFindings(
  state: EngineState,
  forecast: Forecast,
  analytics: AnalyticsBase,
  chf: Money,
  owned: Set<UniverseKey>,
): Finding[] {
  const a = state.accounts;
  const findings: Finding[] = [];

  // 1. Cash held above what the next cycle is forecast to need.
  const idle = Math.max(0, a.everyday - PENDING_CARD_RESERVED - forecast.keep);
  if (owned.has('bank') && idle >= 5_000) {
    findings.push({
      id: 'idle-cash',
      teaser: 'the cash you are not using',
      headline: `${chf(idle, 0)} is sitting in Everyday doing nothing`,
      detail: `AI Budgeting expects this cycle to need ${chf(forecast.keep, 0)}. Everything above that is yours to place — or to leave exactly where it is.`,
      evidence: [
        { label: 'Everyday balance', value: chf(a.everyday, 0) },
        { label: 'Authorised card payments', value: `− ${chf(PENDING_CARD_RESERVED, 0)}` },
        { label: 'Forecast need before your next salary', value: `− ${chf(forecast.keep, 0)}` },
        { label: 'Left over', value: chf(idle, 0) },
      ],
      cta: { label: 'See the options', destination: { tab: 'bank', screen: 'budgeting' } },
    });
  }

  // 2. An allowance with a date on it beats an observation without one.
  const room = PILLAR_3A_ALLOWANCE - PILLAR_3A_PAID_IN;
  if (owned.has('plan') && room > 0) {
    findings.push({
      id: 'pillar-3a-room',
      teaser: 'an allowance with a deadline',
      headline: `${chf(room, 0)} of 3a allowance expires on 31 December`,
      detail: 'Unused allowance does not carry over to next year. Paying it in is a decision only you can make.',
      evidence: [
        { label: 'Paid in this year', value: chf(PILLAR_3A_PAID_IN, 0) },
        { label: 'Annual maximum', value: `${chf(PILLAR_3A_ALLOWANCE, 0)} ⟨TO CONFIRM⟩` },
        { label: 'Still open', value: chf(room, 0) },
      ],
      cta: { label: 'Open 3a', destination: { tab: 'plan' } },
    });
  }

  // 3. Liquidity far beyond the usual rule of thumb.
  if (analytics.monthsOfCover >= 9) {
    findings.push({
      id: 'over-covered',
      teaser: 'how much you hold as cash',
      headline: `${analytics.monthsOfCover.toFixed(1)} months of spending held as cash`,
      detail: `A safety net is usually put at three to six months. Yours is well past that, so part of it could be doing more — at whatever risk you decide is right.`,
      evidence: [
        { label: 'Typical monthly spending', value: chf(analytics.typicalSpend, 0) },
        { label: 'Liquid cash and savings', value: chf(analytics.typicalSpend * analytics.monthsOfCover, 0) },
        { label: 'Common rule of thumb', value: '3–6 months ⟨TO CONFIRM⟩' },
      ],
      cta: { label: 'Open Plan', destination: { tab: 'plan' } },
    });
  }

  // 4. Concentration — one space holding most of the position.
  const biggest = [...analytics.allocation].sort((x, y) => y.pct - x.pct)[0];
  if (biggest && biggest.pct >= 50) {
    findings.push({
      id: 'concentration',
      teaser: 'where most of your wealth sits',
      headline: `${biggest.label} holds ${biggest.pct.toFixed(0)}% of everything you have`,
      detail: `Not a problem in itself — worth knowing, because one space moving takes most of your position with it.`,
      evidence: analytics.allocation.map((s) => ({
        label: s.label,
        value: `${s.pct.toFixed(1)}% · ${chf(s.value, 0)}`,
      })),
      cta: { label: `Open ${biggest.label}`, destination: biggest.destination },
    });
  }

  return findings;
}

function buildAnalytics(
  state: EngineState,
  forecast: Forecast,
  universes: Universe[],
  totalWealth: number,
  snapshot: Snapshot,
  chf: Money,
  hidden: boolean,
  ownedKeys: Set<UniverseKey>,
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

  const base: AnalyticsBase = {
    trend: buildTrend(state, totalWealth),
    months: buildMonths(state),
    allocation,
    investedShare: totalWealth > 0 ? (invested / totalWealth) * 100 : 0,
    putToWorkRate: snapshot.inflow > 0 ? (snapshot.putToWork / snapshot.inflow) * 100 : 0,
    monthsOfCover: spend > 0 ? liquid / spend : 0,
    typicalSpend: spend,
    windowDays: snapshot.days,
  };

  const dayChangePct = ownedKeys.has('trade') ? TRADING_DAY_CHANGE_PCT : 0;
  return {
    ...base,
    findings: buildFindings(state, forecast, base, chf, ownedKeys),
    rings: buildRings(base, dayChangePct, chf, ownedKeys),
    metrics: buildMetrics(state, forecast, base, chf, hidden, ownedKeys),
    monitors: buildMonitors(state, base, chf, ownedKeys),
    orders: ownedKeys.has('trade') ? buildOrders(chf) : [],
  };
}

/**
 * The order book, as rows. Orders reserve trading cash, which is why they
 * belong on an analytical Home at all: they are the reason a balance and the
 * amount actually available disagree.
 */
function buildOrders(chf: Money): OrderRow[] {
  return OPEN_ORDER_BOOK.map((o) => ({
    ticker: o.ticker,
    name: o.name,
    side: o.side,
    detail: `${o.side === 'buy' ? 'Buy' : 'Sell'} ${o.quantity} at ${o.currency} ${swissNumber(o.limit, 2)}`,
    reserved: chf(o.reservedChf, 0),
  }));
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
    analytics: buildAnalytics(
      state,
      forecast,
      universes,
      totalWealth,
      snapshot,
      chf,
      home.balancesHidden,
      ownedKeys,
    ),
    streak: ownedKeys.has('bank') ? buildStreak(state) : null,
    scenario: home.scenario,
    firstName: 'Léa',
    chf,
    balancesHidden: home.balancesHidden,
  };
}
