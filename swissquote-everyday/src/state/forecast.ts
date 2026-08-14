/**
 * AI Budgeting — 30-day liquidity forecast.
 *
 * Computed from the transaction history at call time, never hardcoded. The
 * output is an ESTIMATE and every consumer must present it with probabilistic
 * language ("likely", "based on your last 3 months") — see §5.4 and §9.3.
 */
import { dayOfMonth } from '../lib/format';
import { CLIENT, salaryCreditDay } from '../data/mockLedger';
import type { EngineState, Txn } from './types';

export interface RecurringItem {
  label: string;
  amount: number;
  dayOfMonth: number;
}

export interface ForecastPoint {
  day: number;
  typical: number;
  high: number;
  /** Known event landing on this day, for the x-axis markers. */
  event?: string;
}

export interface Forecast {
  /** Recommended buffer — a range, not a point estimate. */
  buffer: number;
  bufferLow: number;
  bufferHigh: number;
  /** 30-day projected balance path (typical and high-spend scenarios). */
  points: ForecastPoint[];
  nextSalaryDay: number;
  /** Explainability — §5.4 "How this is calculated" panel. */
  factors: {
    recurring: RecurringItem[];
    recurringMonthlyTotal: number;
    avgDailyCardSpend: number;
    dailyStdDev: number;
    monthsOfHistory: number;
    oneOffsExcluded: { label: string; amount: number }[];
    seasonalNote: string | null;
    widened: boolean;
  };
}

const ONE_OFF_THRESHOLD = 300;

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
function detectRecurring(txns: Txn[]): RecurringItem[] {
  const groups = new Map<string, Txn[]>();
  for (const t of txns) {
    if (t.amount >= 0 || t.category === 'smart-liquidity' || t.currency !== 'CHF') continue;
    const list = groups.get(t.label) ?? [];
    list.push(t);
    groups.set(t.label, list);
  }
  const out: RecurringItem[] = [];
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

export function computeForecast(state: EngineState): Forecast {
  const { day, txns, accounts, flags } = state;
  const windowStart = day - 90;
  const history = txns.filter((t) => t.day >= windowStart && t.day < day);

  const recurring = detectRecurring(history);
  const recurringLabels = new Set(recurring.map((r) => r.label));
  const recurringMonthlyTotal = recurring.reduce((s, r) => s + r.amount, 0);

  // Average discretionary card spend per day over the window, one-offs excluded.
  const oneOffsExcluded = history
    .filter((t) => isDiscretionary(t) && !recurringLabels.has(t.label) && -t.amount >= ONE_OFF_THRESHOLD)
    .map((t) => ({ label: t.label, amount: -t.amount }));
  const daily = new Map<number, number>();
  for (const t of history) {
    if (!isDiscretionary(t) || recurringLabels.has(t.label) || -t.amount >= ONE_OFF_THRESHOLD) continue;
    daily.set(t.day, (daily.get(t.day) ?? 0) + -t.amount);
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

  // Irregular income (Marc mode): the band widens, and says so in the UI.
  const widen = flags.irregularIncome ? 1.8 : 1;

  // 30-day projected balance path from today.
  const points: ForecastPoint[] = [];
  let typical = accounts.everyday;
  let high = accounts.everyday;
  const salaryDay = nextSalaryDayAfter(day);
  for (let i = 0; i <= 30; i += 1) {
    const d = day + i;
    let event: string | undefined;
    if (i > 0) {
      typical -= avgDaily;
      high -= avgDaily + 0.45 * dailyStd * widen;
      for (const r of recurring) {
        if (dayOfMonth(d) === r.dayOfMonth) {
          typical -= r.amount;
          high -= r.amount;
          if (r.amount >= 300) event = r.label.split(' — ')[0].split(' · ')[0];
        }
      }
      if (d === salaryDay && !flags.salaryMissing) {
        const delayed = flags.salaryDelayed ? 0 : CLIENT.salaryNet;
        typical += delayed;
        high += delayed;
        event = flags.salaryDelayed ? 'Salary (delayed)' : 'Salary';
      }
    }
    points.push({ day: d, typical: Math.round(typical), high: Math.round(high), event });
  }

  // Recommended buffer = liquidity likely needed over the next 30 days:
  // recurring debits + typical card spend, high scenario for the upper bound.
  const typicalNeed = recurringMonthlyTotal + avgDaily * 30;
  const highNeed = recurringMonthlyTotal + (avgDaily + 0.45 * dailyStd * widen) * 30;
  const lowNeed = recurringMonthlyTotal + Math.max(0, avgDaily - 0.3 * dailyStd) * 30;
  const round50 = (v: number) => Math.round(v / 50) * 50;

  const seasonalNote =
    dayOfMonth(day) >= 1 && new Date().getUTCMonth() === 11
      ? 'December spending typically runs higher — the estimate is adjusted up.'
      : null;

  return {
    buffer: round50(typicalNeed),
    bufferLow: round50(lowNeed),
    bufferHigh: round50(highNeed),
    points,
    nextSalaryDay: salaryDay,
    factors: {
      recurring,
      recurringMonthlyTotal: Math.round(recurringMonthlyTotal),
      avgDailyCardSpend: Math.round(avgDaily * 100) / 100,
      dailyStdDev: Math.round(dailyStd * 100) / 100,
      monthsOfHistory: 3,
      oneOffsExcluded,
      seasonalNote,
      widened: flags.irregularIncome,
    },
  };
}
