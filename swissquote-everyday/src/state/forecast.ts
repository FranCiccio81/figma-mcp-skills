/**
 * AI Budgeting — predicts the liquidity the client is likely to need before
 * their next salary, and therefore how much cash is genuinely surplus.
 *
 * Per the AI Budgeting spec:
 * - the horizon is the salary cycle (today → next expected salary), §24;
 * - the requirement is built from confirmed upcoming payments, predicted
 *   recurring expenses and predicted variable spending, §25/§27;
 * - a safety margin is added on top, sized by the client's safety level and
 *   by forecast confidence, §19/§20;
 * - the result is clamped to the client's own corridor, §18 — the AI never
 *   overrides a client-defined minimum;
 * - everything is an ESTIMATE and consumers must use probabilistic language.
 *
 * The AI recommends. The rules engine protects (§55).
 */
import { dayOfMonth } from '../lib/format';
import { CLIENT, PENDING_CARD_RESERVED, salaryCreditDay } from '../data/mockLedger';
import type { EngineState, SafetyLevel, Txn, TxnCategory } from './types';

export interface RecurringItem {
  label: string;
  amount: number;
  dayOfMonth: number;
  /** Falls inside the current forecast horizon. */
  dueInCycle: boolean;
}

export interface ForecastPoint {
  day: number;
  typical: number;
  high: number;
  /** Known event landing on this day, for the x-axis markers. */
  event?: string;
}

export type Confidence = 'high' | 'medium' | 'low';

export interface CategoryEstimate {
  category: TxnCategory;
  label: string;
  amount: number;
}

export interface Forecast {
  /* ---- horizon (§24) ---- */
  horizonStart: number;
  horizonEnd: number;
  horizonDays: number;

  /* ---- the requirement, component by component (§25/§27) ---- */
  /** Client-declared planned expenses + card transactions already authorised. */
  confirmedUpcoming: number;
  pendingCard: number;
  plannedTotal: number;
  /** Rent, insurance, subscriptions detected from history and due this cycle. */
  recurringPredicted: number;
  /** Groceries, dining, transport… predicted statistically. */
  variablePredicted: number;
  /** Expected requirement before the safety margin. */
  expectedRequirement: number;
  safetyMargin: number;

  /** Protected liquidity — what Smart Salary Allocation must keep in Banking. */
  keep: number;
  /** Raw recommendation before the client's corridor was applied. */
  keepRaw: number;
  /** True when the prediction exceeded the client's preferred maximum (§18). */
  aboveMax: boolean;
  /** True when the client's minimum lifted the recommendation (§18/BR-02). */
  liftedByMin: boolean;
  /** True when the fixed fallback buffer is in use instead of the prediction. */
  fallbackUsed: boolean;

  confidence: Confidence;
  confidenceNote: string;

  /** Legacy field names kept for the chart and the allocation engine. */
  buffer: number;
  bufferLow: number;
  bufferHigh: number;
  points: ForecastPoint[];
  nextSalaryDay: number;

  factors: {
    recurring: RecurringItem[];
    recurringMonthlyTotal: number;
    categories: CategoryEstimate[];
    avgDailyCardSpend: number;
    dailyStdDev: number;
    monthsOfHistory: number;
    oneOffsExcluded: { label: string; amount: number }[];
    seasonalNote: string | null;
    widened: boolean;
  };
}

/** Safety level → share of the expected requirement held back as margin (§17). */
const MARGIN_FACTOR: Record<SafetyLevel, number> = {
  efficient: 0.08,
  balanced: 0.16,
  cautious: 0.3,
};

/* Above this, a single debit is treated as a one-off, not routine spend. */
const ONE_OFF_THRESHOLD = 1_500;

const CATEGORY_LABELS: Partial<Record<TxnCategory, string>> = {
  housing: 'Housing',
  insurance: 'Insurance',
  groceries: 'Groceries',
  dining: 'Restaurants',
  transport: 'Transport',
  shopping: 'Shopping',
  health: 'Health',
  leisure: 'Travel & leisure',
  subscription: 'Subscriptions',
  transfer: 'Transfers',
};

function isDiscretionary(t: Txn): boolean {
  return (
    t.amount < 0 &&
    t.currency === 'CHF' &&
    t.category !== 'smart-liquidity' &&
    t.category !== 'housing' &&
    t.category !== 'insurance' &&
    t.category !== 'subscription' &&
    t.status === 'booked'
  );
}

/** Detect debits recurring at a monthly cadence: same label, similar amount, ≥ 2 occurrences. */
function detectRecurring(txns: Txn[]): Omit<RecurringItem, 'dueInCycle'>[] {
  const groups = new Map<string, Txn[]>();
  for (const t of txns) {
    if (t.amount >= 0 || t.category === 'smart-liquidity' || t.currency !== 'CHF') continue;
    const list = groups.get(t.label) ?? [];
    list.push(t);
    groups.set(t.label, list);
  }
  const out: Omit<RecurringItem, 'dueInCycle'>[] = [];
  for (const [label, list] of groups) {
    if (list.length < 2) continue;
    const amounts = list.map((t) => -t.amount);
    const mean = amounts.reduce((s, a) => s + a, 0) / amounts.length;
    const similar = amounts.every((a) => Math.abs(a - mean) / mean < 0.15);
    const doms = list.map((t) => dayOfMonth(t.day));
    const sameDom = doms.every((d) => Math.abs(d - doms[0]) <= 2);
    if (similar && sameDom) {
      out.push({ label, amount: Math.round(mean * 100) / 100, dayOfMonth: doms[doms.length - 1] });
    }
  }
  return out.sort((a, b) => b.amount - a.amount);
}

export function nextSalaryDayAfter(day: number): number {
  for (let d = day + 1; d <= day + 40; d += 1) {
    if (salaryCreditDay(d)) return d;
  }
  return day + 30;
}

/** Does a monthly debit on `dom` fall between today and the end of the cycle? */
function fallsInHorizon(dom: number, start: number, end: number): boolean {
  for (let d = start + 1; d <= end; d += 1) {
    if (dayOfMonth(d) === dom) return true;
  }
  return false;
}

export function computeForecast(state: EngineState): Forecast {
  const { day, txns, accounts, flags, allocation, plannedExpenses } = state;
  const windowStart = day - 90;
  const history = txns.filter((t) => t.day >= windowStart && t.day < day);

  /* ---- 1. horizon: today → next expected salary (§24) ---- */
  const horizonEnd = nextSalaryDayAfter(day);
  const horizonDays = Math.max(1, horizonEnd - day);

  /* ---- 2. recurring expenses detected from history ---- */
  const detected = detectRecurring(history);
  const recurring: RecurringItem[] = detected.map((r) => ({
    ...r,
    dueInCycle: fallsInHorizon(r.dayOfMonth, day, horizonEnd),
  }));
  const recurringMonthlyTotal = recurring.reduce((s, r) => s + r.amount, 0);
  const recurringPredicted = recurring.filter((r) => r.dueInCycle).reduce((s, r) => s + r.amount, 0);
  const recurringLabels = new Set(recurring.map((r) => r.label));

  /* ---- 3. variable spending, predicted statistically ---- */
  const oneOffsExcluded = history
    .filter((t) => isDiscretionary(t) && !recurringLabels.has(t.label) && -t.amount >= ONE_OFF_THRESHOLD)
    .map((t) => ({ label: t.label, amount: -t.amount }));
  const daily = new Map<number, number>();
  const byCategory = new Map<TxnCategory, number>();
  for (const t of history) {
    if (!isDiscretionary(t) || recurringLabels.has(t.label) || -t.amount >= ONE_OFF_THRESHOLD) continue;
    daily.set(t.day, (daily.get(t.day) ?? 0) + -t.amount);
    byCategory.set(t.category, (byCategory.get(t.category) ?? 0) + -t.amount);
  }
  const nDays = 90;
  let sum = 0;
  for (const v of daily.values()) sum += v;
  const avgDaily = sum / nDays;
  let variance = 0;
  for (let d = windowStart; d < day; d += 1) {
    const v = daily.get(d) ?? 0;
    variance += (v - avgDaily) ** 2;
  }
  const dailyStd = Math.sqrt(variance / nDays);
  const variablePredicted = avgDaily * horizonDays;

  /* ---- 4. confirmed upcoming: client-planned expenses + authorised card spend (§29/§32) ---- */
  const plannedTotal = plannedExpenses.reduce((s, p) => s + p.amount, 0);
  const pendingCard = PENDING_CARD_RESERVED;
  const confirmedUpcoming = plannedTotal + pendingCard;

  /* ---- 5. confidence (§20) — volatility and income regularity drive it ---- */
  const volatility = avgDaily > 0 ? dailyStd / avgDaily : 1;
  let confidence: Confidence = 'high';
  if (flags.irregularIncome || volatility > 1.4) confidence = 'low';
  else if (volatility > 0.9) confidence = 'medium';
  const confidenceNote =
    confidence === 'high'
      ? 'Your recent spending has been relatively predictable.'
      : confidence === 'medium'
        ? "Your spending varies from month to month, so we've included a larger safety margin."
        : "Your recent activity is less predictable than usual, so we're keeping more available for your protection.";

  /* ---- 6. safety margin (§19) — level + uncertainty; uncertainty rises as confidence falls ---- */
  const expectedRequirement = confirmedUpcoming + recurringPredicted + variablePredicted;
  const confidenceUplift = confidence === 'high' ? 0 : confidence === 'medium' ? 0.06 : 0.15;
  const safetyMargin = Math.round(
    (expectedRequirement * (MARGIN_FACTOR[allocation.safetyLevel] + confidenceUplift)) / 50,
  ) * 50;

  /* ---- 7. protected liquidity, clamped to the client's corridor (§18/BR-02) ---- */
  const round50 = (v: number) => Math.round(v / 50) * 50;
  const keepRaw = round50(expectedRequirement + safetyMargin);
  const liftedByMin = keepRaw < allocation.minKeep;
  const aboveMax = keepRaw > allocation.maxKeep;
  // A prediction above the preferred maximum is NOT silently capped — the client
  // is warned and the higher, safer figure is protected (§18).
  const keep = liftedByMin ? allocation.minKeep : keepRaw;
  const fallbackUsed = allocation.bufferMode === 'manual';
  const effectiveKeep = fallbackUsed ? allocation.manualBuffer : keep;

  /* ---- 8. projected balance path across the horizon ---- */
  const points: ForecastPoint[] = [];
  const spanDays = Math.max(horizonDays, 14);
  let typical = accounts.everyday - pendingCard;
  let high = accounts.everyday - pendingCard;
  for (let i = 0; i <= spanDays; i += 1) {
    const d = day + i;
    let event: string | undefined;
    if (i > 0) {
      typical -= avgDaily;
      high -= avgDaily + 0.45 * dailyStd;
      for (const r of recurring) {
        if (dayOfMonth(d) === r.dayOfMonth) {
          typical -= r.amount;
          high -= r.amount;
          if (r.amount >= 800) event = r.label.split(' — ')[0].split(' · ')[0];
        }
      }
      if (d === horizonEnd && !flags.salaryMissing) {
        const credited = flags.salaryDelayed ? 0 : CLIENT.salaryNet;
        typical += credited;
        high += credited;
        event = flags.salaryDelayed ? 'Salary (delayed)' : 'Salary';
      }
    }
    points.push({ day: d, typical: Math.round(typical), high: Math.round(high), event });
  }

  /* ---- 9. category breakdown for the forecast detail (§37) ---- */
  const categories: CategoryEstimate[] = [...byCategory.entries()]
    .map(([category, total]) => ({
      category,
      label: CATEGORY_LABELS[category] ?? 'Other',
      amount: Math.round(((total / nDays) * horizonDays) / 10) * 10,
    }))
    .filter((c) => c.amount > 0)
    .sort((a, b) => b.amount - a.amount);

  const seasonalNote = null;

  return {
    horizonStart: day,
    horizonEnd,
    horizonDays,
    confirmedUpcoming: Math.round(confirmedUpcoming),
    pendingCard,
    plannedTotal,
    recurringPredicted: Math.round(recurringPredicted),
    variablePredicted: Math.round(variablePredicted),
    expectedRequirement: Math.round(expectedRequirement),
    safetyMargin,
    keep: effectiveKeep,
    keepRaw,
    aboveMax,
    liftedByMin,
    fallbackUsed,
    confidence,
    confidenceNote,

    buffer: effectiveKeep,
    bufferLow: round50(expectedRequirement),
    bufferHigh: round50(keepRaw + safetyMargin * 0.5),
    points,
    nextSalaryDay: horizonEnd,

    factors: {
      recurring,
      recurringMonthlyTotal: Math.round(recurringMonthlyTotal),
      categories,
      avgDailyCardSpend: Math.round(avgDaily * 100) / 100,
      dailyStdDev: Math.round(dailyStd * 100) / 100,
      monthsOfHistory: 3,
      oneOffsExcluded,
      seasonalNote,
      widened: flags.irregularIncome,
    },
  };
}
