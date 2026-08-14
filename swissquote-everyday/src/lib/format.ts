/** Swiss-convention formatting helpers. `CHF 8'400.00` — code before amount, apostrophe thousands. */

export type Currency = 'CHF' | 'EUR' | 'USD';

/** Format a number with apostrophe thousands separators and 2 decimals. */
export function swissNumber(value: number, decimals = 2): string {
  const negative = value < 0;
  const fixed = Math.abs(value).toFixed(decimals);
  const [int, frac] = fixed.split('.');
  const grouped = int.replace(/\B(?=(\d{3})+(?!\d))/g, "'");
  return `${negative ? '−' : ''}${grouped}${frac !== undefined ? '.' + frac : ''}`;
}

/** `CHF 3'840.50` */
export function money(value: number, currency: Currency = 'CHF', decimals = 2): string {
  return `${currency} ${swissNumber(value, decimals)}`;
}

/** Signed variant for transaction rows: `+ CHF 8'400.00` / `− CHF 42.60` */
export function signedMoney(value: number, currency: Currency = 'CHF'): string {
  const sign = value > 0 ? '+ ' : value < 0 ? '− ' : '';
  return `${sign}${money(Math.abs(value), currency)}`;
}

const DAY_MS = 86_400_000;
/** Simulation epoch: day 0 = Friday 14 August 2026 (the "today" of the mock data set). */
export const EPOCH_UTC = Date.UTC(2026, 7, 14);

export function dateOf(day: number): Date {
  return new Date(EPOCH_UTC + day * DAY_MS);
}

const MONTHS = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December',
];
const WEEKDAYS = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];

/** `14 August` */
export function shortDate(day: number): string {
  const d = dateOf(day);
  return `${d.getUTCDate()} ${MONTHS[d.getUTCMonth()]}`;
}

/** `Friday 14 August 2026` */
export function longDate(day: number): string {
  const d = dateOf(day);
  return `${WEEKDAYS[d.getUTCDay()]} ${d.getUTCDate()} ${MONTHS[d.getUTCMonth()]} ${d.getUTCFullYear()}`;
}

export function dayOfMonth(day: number): number {
  return dateOf(day).getUTCDate();
}

/** Saturday/Sunday check for business-day logic (salary + 1 business day). */
export function isWeekend(day: number): boolean {
  const wd = dateOf(day).getUTCDay();
  return wd === 0 || wd === 6;
}

export function nextBusinessDay(day: number): number {
  let d = day + 1;
  while (isWeekend(d)) d += 1;
  return d;
}

/** Deterministic PRNG (mulberry32) so the synthetic ledger is stable run to run. */
export function mulberry32(seed: number): () => number {
  let a = seed >>> 0;
  return () => {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export function roundTo(value: number, step: number): number {
  return Math.round(value / step) * step;
}
