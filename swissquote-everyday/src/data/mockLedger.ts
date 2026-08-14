/**
 * Mock ledger — §10 of the brief, verbatim, plus 90 days of synthetic
 * transaction history consistent with the stated spending pattern
 * (rent 1'950 on the 1st, insurance 385 on the 5th, card ≈ CHF 1'800/month,
 * salary 8'400 on the 25th). The history is generated deterministically so the
 * 30-day forecast is COMPUTED from it, never hardcoded.
 */
import { dayOfMonth, dateOf, isWeekend, mulberry32 } from '../lib/format';
import type { Accounts, AllocationRule, AutoCoverConfig, Txn } from '../state/types';

export const CLIENT = {
  name: 'Léa Baumann',
  ibanMasked: 'CH•• •••• •••• •••• 4 291',
  ibanFull: 'CH93 0076 2011 6238 5295 7', // sample-format IBAN, prototype only
  employer: 'Employer SA',
  salaryNet: 21_000, // wealthy profile — senior executive net salary
  salaryDayOfMonth: 25,
};

export const FX = {
  eurToChf: 574.1 / 612.0, // §10: EUR 612.00 ≈ CHF 574.10 (indicative)
  usdToChf: 842.3 / 1_050.0, // §10: USD 1'050.00 ≈ CHF 842.30 (indicative)
  spreadPct: 0.95, // conversion cost shown before any FX top-up ⟨TO CONFIRM⟩
};

export const LOMBARD_RATE_PA = 4.25; // ⟨rate TO CONFIRM⟩

/**
 * Operational reservations — Buying Power §18–§22 and FR-02/FR-04.
 * These amounts exist in the product but are NOT spendable liquidity, so they
 * are deducted before anything is called "available".
 */
/** Card transactions authorised but not yet booked. */
export const PENDING_CARD_RESERVED = 1_240;
/** Trading cash committed to open limit orders. */
export const TRADING_ORDERS_RESERVED = 6_000;
/** Save Easy amount withdrawable without notice period or penalty ⟨TO CONFIRM⟩. */
export const SAVE_EASY_PENALTY_FREE = 25_000;
/** Lombard contractual limit; `lombardAvailable` is the currently drawable part. */
export const LOMBARD_LIMIT = 150_000;

export const INITIAL_ACCOUNTS: Accounts = {
  everyday: 165_880.5, // 1'880.10 + 1'000 Auto Cover + 163'000.40 annual bonus (day 0)
  eurWallet: 8_612.0,
  usdWallet: 12_050.0,
  saveEasy: 86_400.0,
  tradingCash: 24_260.0,
  investEasy: 428_900.0,
  savingPlan: 24_500.0,
  lombardAvailable: 118_600.0,
  lombardDrawn: 0,
};

export const INITIAL_ALLOCATION: AllocationRule = {
  enabled: true,
  paused: false,
  skipNext: false,
  mode: 'automatic',
  bufferMode: 'ai',
  manualBuffer: 12_000, // fixed liquidity fallback (§16/§43)
  safetyLevel: 'balanced',
  // An absolute floor, deliberately below the usual prediction so the AI —
  // not the floor — normally decides how much is kept.
  minKeep: 3_000,
  maxKeep: 20_000,
  basis: 'excess',
  // Spec §14/§28 example plan: Save Easy 30 · Invest Easy 40 · Trading 10 · ETF Plan 20.
  splits: [
    { destination: 'saveEasy', label: 'Save Easy', percent: 30 },
    { destination: 'investEasy', label: 'Invest Easy', percent: 40 },
    { destination: 'tradingCash', label: 'Trading', percent: 10 },
    { destination: 'savingPlan', label: 'Global ETF Saving Plan', percent: 20 },
  ],
  // Guardrails — §19, scaled to the CHF 21'000 salary.
  maxPerSalary: 25_000,
  minAllocation: 500,
  askOnVariance: true,
  variancePct: 20,
  scheduledForDay: null,
  lastReceived: 0,
  lastRun: {
    day: -18, // Monday 27 July — salary landed Friday 24 July (25th was a Saturday)
    moved: [
      { destination: 'saveEasy', amount: 2_800 },
      { destination: 'investEasy', amount: 3_700 },
      { destination: 'tradingCash', amount: 900 },
      { destination: 'savingPlan', amount: 1_900 },
    ],
  },
};

export const INITIAL_AUTO_COVER: AutoCoverConfig = {
  // Pre-enabled in the demo so the 14 August cover exists; the product default is OFF.
  enabled: true,
  paused: false,
  coverMode: 'buffer',
  bufferAmount: 1_000,
  perTransactionMax: 25_000,
  monthlyCap: 40_000,
  usedThisMonth: 1_000, // the 14 August cover
  // Invest Easy is deliberately absent: Auto Cover never sells investments (§6.3/FR-26).
  sources: [
    { source: 'saveEasy', enabled: true, monthlyLimit: 25_000, usedThisMonth: 1_000 },
    { source: 'tradingCash', enabled: true, monthlyLimit: 15_000, usedThisMonth: 0 },
    { source: 'eurWallet', enabled: false, monthlyLimit: 5_000, usedThisMonth: 0 },
    { source: 'usdWallet', enabled: false, monthlyLimit: 5_000, usedThisMonth: 0 },
  ],
  tradingReserve: 10_000,
  lombardEnabled: false,
  lombardAcknowledged: false,
  lombardPerCoverMax: 5_000,
  lombardMonthlyMax: 10_000,
  lombardUsedThisMonth: 0,
  lastTopUpDay: 0,
  keepMinimumEnabled: true, // advanced §31 mode, on in the demo so the loop is visible
  minBalance: 2_000,
};

/** Scales synthetic card spend to the wealthy profile (~CHF 5'500 card spend
 * per month), keeping the computed buffer and the Auto Cover demo loop in
 * proportion with the CHF 21'000 salary. One calibration knob. */
export const SPEND_SCALE = 4.2;

interface MerchantSpec {
  label: string;
  category: Txn['category'];
  min: number;
  max: number;
  weight: number;
}

/** Lausanne-flavoured merchant pool — no lorem ipsum, no placeholder merchants. */
const MERCHANTS: MerchantSpec[] = [
  { label: 'Coop Lausanne St-François', category: 'groceries', min: 12, max: 85, weight: 5 },
  { label: 'Migros Lausanne Flon', category: 'groceries', min: 9, max: 70, weight: 5 },
  { label: 'Denner Lausanne Gare', category: 'groceries', min: 8, max: 40, weight: 2 },
  { label: 'SBB CFF FFS', category: 'transport', min: 3.6, max: 46, weight: 3 },
  { label: 'TL Lausanne', category: 'transport', min: 3.6, max: 9.8, weight: 2 },
  { label: 'Boulangerie Saint-Pierre', category: 'dining', min: 4.2, max: 14, weight: 3 },
  { label: 'Café de Grancy', category: 'dining', min: 6.5, max: 26, weight: 2 },
  { label: 'Holy Cow! Lausanne', category: 'dining', min: 14, max: 34, weight: 2 },
  { label: 'Restaurant du Théâtre', category: 'dining', min: 32, max: 96, weight: 1 },
  { label: 'Pharmacie Amavita Gare', category: 'health', min: 12, max: 58, weight: 1 },
  { label: 'Galaxus', category: 'shopping', min: 24, max: 130, weight: 1 },
  { label: 'TWINT · P2P payment', category: 'transfer', min: 10, max: 60, weight: 2 },
];

interface RecurringSpec {
  label: string;
  category: Txn['category'];
  amount: number;
  dayOfMonth: number;
}

export const RECURRING_DEBITS: RecurringSpec[] = [
  { label: 'Rent — Régie du Léman', category: 'housing', amount: 4_950, dayOfMonth: 1 },
  { label: 'Sanitas — health insurance', category: 'insurance', amount: 885, dayOfMonth: 5 },
  { label: 'Country Club Lausanne', category: 'subscription', amount: 389, dayOfMonth: 3 },
  { label: 'Swisscom', category: 'subscription', amount: 95, dayOfMonth: 8 },
  { label: 'Netflix', category: 'subscription', amount: 18.9, dayOfMonth: 12 },
];

/** Salary lands on the 25th; if that is a weekend it arrives the preceding Friday. */
export function salaryCreditDay(day: number): boolean {
  const dom = dayOfMonth(day);
  if (dom === CLIENT.salaryDayOfMonth) return !isWeekend(day);
  // Friday before a weekend 25th
  const wd = dateOf(day).getUTCDay();
  if (wd !== 5) return false;
  const domNext = dayOfMonth(day + 1);
  const domNext2 = dayOfMonth(day + 2);
  return domNext === CLIENT.salaryDayOfMonth || domNext2 === CLIENT.salaryDayOfMonth;
}

function pickMerchant(rng: () => number): MerchantSpec {
  const total = MERCHANTS.reduce((s, m) => s + m.weight, 0);
  let r = rng() * total;
  for (const m of MERCHANTS) {
    r -= m.weight;
    if (r <= 0) return m;
  }
  return MERCHANTS[0];
}

/**
 * Generate the 90-day history ending on day 0 (14 August 2026).
 * Includes the §10 "Recent Auto Cover" of 14 August verbatim: CHF 400.00 from
 * Save Easy after the balance hit CHF 480.00, followed by the expense
 * reimbursement that brings the Everyday balance to its §10 value of 3'840.50.
 */
export function generateHistory(): Txn[] {
  const rng = mulberry32(20_260_814);
  const txns: Txn[] = [];
  let seq = 0;
  const push = (t: Omit<Txn, 'id'>) => {
    seq += 1;
    txns.push({ id: `hist-${seq}`, ...t });
  };

  for (let day = -90; day <= 0; day += 1) {
    const dom = dayOfMonth(day);

    for (const r of RECURRING_DEBITS) {
      if (dom === r.dayOfMonth) {
        push({ day, label: r.label, category: r.category, amount: -r.amount, currency: 'CHF', status: 'booked' });
      }
    }

    if (salaryCreditDay(day) && day < 0) {
      push({
        day,
        label: `Salary — ${CLIENT.employer}`,
        category: 'salary',
        amount: CLIENT.salaryNet,
        currency: 'CHF',
        status: 'booked',
      });
    }

    // Smart Salary Allocation runs from history (26 May, 26 June, 27 July) —
    // the §14 example plan: Save Easy 30 · Invest Easy 40 · Trading 10 · ETF Plan 20.
    if (day === -80 || day === -49 || day === -18) {
      const total = day === -18 ? 9_300 : day === -49 ? 8_400 : 8_900;
      const received = 21_000 + (day === -18 ? 214.4 : 0);
      const plan: { destination: 'saveEasy' | 'investEasy' | 'tradingCash' | 'savingPlan'; label: string; percent: number }[] = [
        { destination: 'saveEasy', label: 'Save Easy', percent: 30 },
        { destination: 'investEasy', label: 'Invest Easy', percent: 40 },
        { destination: 'tradingCash', label: 'Trading', percent: 10 },
        { destination: 'savingPlan', label: 'Global ETF Saving Plan', percent: 20 },
      ];
      let before = 33_000 + Math.round(rng() * 2_000);
      for (const p of plan) {
        const amount = Math.round((total * p.percent) / 100 / 10) * 10;
        push({
          day,
          label: `Smart Salary Allocation · to ${p.label}`,
          category: 'smart-liquidity',
          amount: -amount,
          currency: 'CHF',
          status: 'booked',
          smart: {
            engine: 'allocation',
            title: `Smart Salary Allocation · to ${p.label}`,
            source: 'everyday',
            destination: p.destination,
            reason: `CHF ${received.toFixed(2)} was received from ${CLIENT.employer}. Your plan keeps your Cash Safety Buffer available in Banking; the allocatable amount was distributed by your plan — ${p.percent}% to ${p.label}.`,
            balanceBefore: before,
            balanceAfter: before - amount,
          },
        });
        before -= amount;
      }
    }

    // One-off large item (excluded from the forecast's recurring detection).
    if (day === -33) {
      push({
        day,
        label: 'SWISS International Air Lines',
        category: 'leisure',
        amount: -2_486,
        currency: 'CHF',
        status: 'booked',
      });
    }
    if (day === -61) {
      push({ day, label: 'Amazon.de', category: 'shopping', amount: -374.9, currency: 'EUR', status: 'booked' });
    }
    if (day === -26) {
      push({ day, label: 'Airbnb', category: 'leisure', amount: -1_212.0, currency: 'EUR', status: 'booked' });
    }

    // Everyday card spend — calibrated to ≈ CHF 1'650–1'800/month.
    if (day < 0) {
      const countRoll = rng();
      const count = countRoll < 0.25 ? 0 : countRoll < 0.6 ? 1 : countRoll < 0.9 ? 2 : 3;
      for (let i = 0; i < count; i += 1) {
        const m = pickMerchant(rng);
        const amount = -(m.min + rng() * (m.max - m.min)) * SPEND_SCALE;
        push({
          day,
          label: m.label,
          category: m.category,
          amount: Math.round(amount * 20) / 20, // Swiss 5-centime rounding
          currency: 'CHF',
          status: 'booked',
        });
      }
    }
  }

  // ----- Day 0, in order: the debit that breached the minimum, the Auto Cover
  // top-up, then the annual bonus that explains today's balance — and gives
  // the next Smart Salary Allocation something spectacular to sweep.
  push({
    day: 0,
    label: 'Beau-Rivage Palace',
    category: 'dining',
    amount: -486.4,
    currency: 'CHF',
    status: 'booked',
  });
  push({
    day: 0,
    label: 'Auto Cover · from Save Easy',
    category: 'smart-liquidity',
    amount: 1_000,
    currency: 'CHF',
    status: 'booked',
    smart: {
      engine: 'autoCover',
      title: 'Auto Cover · from Save Easy',
      source: 'saveEasy',
      destination: 'everyday',
      reason:
        "Your Everyday balance fell to CHF 1'880.10, below your minimum of CHF 2'000.00. Auto Cover topped up one increment of CHF 1'000.00 from Save Easy, the first source in your list (instant, no cost).",
      balanceBefore: 1_880.1,
      balanceAfter: 2_880.1,
    },
  });
  push({
    day: 0,
    label: `Annual bonus — ${CLIENT.employer}`,
    category: 'salary',
    amount: 163_000.4,
    currency: 'CHF',
    status: 'booked',
  });

  return txns;
}
