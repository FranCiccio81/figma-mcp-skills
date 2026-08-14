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
  salaryNet: 8_400,
  salaryDayOfMonth: 25,
};

export const FX = {
  eurToChf: 574.1 / 612.0, // §10: EUR 612.00 ≈ CHF 574.10 (indicative)
  usdToChf: 842.3 / 1_050.0, // §10: USD 1'050.00 ≈ CHF 842.30 (indicative)
  spreadPct: 0.95, // conversion cost shown before any FX top-up ⟨TO CONFIRM⟩
};

export const LOMBARD_RATE_PA = 4.25; // §10 ⟨rate TO CONFIRM⟩

export const INITIAL_ACCOUNTS: Accounts = {
  everyday: 3_840.5,
  eurWallet: 612.0,
  usdWallet: 1_050.0,
  saveEasy: 12_400.0,
  tradingCash: 4_260.0,
  investEasy: 28_900.0,
  lombardAvailable: 18_600.0,
  lombardDrawn: 0,
};

export const INITIAL_ALLOCATION: AllocationRule = {
  enabled: true,
  paused: false,
  skipNext: false,
  bufferMode: 'ai',
  manualBuffer: 4_150,
  basis: 'excess',
  splits: [
    // §10 ratio: 2'300 → Invest Easy, 950 → Save Easy ≈ 70/29 of the surplus.
    { destination: 'investEasy', label: 'Invest Easy', percent: 70 },
    { destination: 'saveEasy', label: 'Save Easy', percent: 29 },
  ],
  scheduledForDay: null,
  lastRun: {
    day: -18, // Monday 27 July — salary landed Friday 24 July (25th was a Saturday)
    moved: [
      { destination: 'investEasy', amount: 2_250 },
      { destination: 'saveEasy', amount: 900 },
    ],
  },
};

export const INITIAL_AUTO_COVER: AutoCoverConfig = {
  enabled: true, // pre-enabled in the demo so the recent Auto Cover of §10 exists; product default is OFF
  minBalance: 500,
  waterfall: ['saveEasy', 'tradingCash', 'investEasy', 'eurWallet', 'usdWallet'],
  lombardEnabled: false,
  lombardAcknowledged: false,
  topUpIncrement: 400,
  monthlyCap: 2_000,
  cooldownDays: 1,
  usedThisMonth: 400, // the 14 August top-up
  lastTopUpDay: 0,
};

/** Scales synthetic card spend so the computed 30-day need lands in the §10
 * neighbourhood (~CHF 1'700–1'800 card spend per month). One calibration knob. */
export const SPEND_SCALE = 1.38;

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
  { label: 'Rent — Régie du Léman', category: 'housing', amount: 1_950, dayOfMonth: 1 },
  { label: 'Sanitas — health insurance', category: 'insurance', amount: 385, dayOfMonth: 5 },
  { label: 'NonStop Gym Lausanne', category: 'subscription', amount: 89, dayOfMonth: 3 },
  { label: 'Swisscom', category: 'subscription', amount: 65, dayOfMonth: 8 },
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

    // Smart Salary Allocation runs from history (26 May, 26 June, 27 July).
    if (day === -80 || day === -49 || day === -18) {
      const pairs: [number, number] =
        day === -18 ? [2_250, 900] : day === -49 ? [2_050, 850] : [2_200, 900];
      const before = 6_900 + Math.round(rng() * 400);
      push({
        day,
        label: 'Smart Salary Allocation · to Invest Easy',
        category: 'smart-liquidity',
        amount: -pairs[0],
        currency: 'CHF',
        status: 'booked',
        smart: {
          engine: 'allocation',
          title: 'Smart Salary Allocation · to Invest Easy',
          source: 'everyday',
          destination: 'investEasy',
          reason: `Salary recognised from ${CLIENT.employer}. Your rule keeps the AI buffer in Everyday and moves 70% of the rest to Invest Easy.`,
          balanceBefore: before,
          balanceAfter: before - pairs[0],
        },
      });
      push({
        day,
        label: 'Smart Salary Allocation · to Save Easy',
        category: 'smart-liquidity',
        amount: -pairs[1],
        currency: 'CHF',
        status: 'booked',
        smart: {
          engine: 'allocation',
          title: 'Smart Salary Allocation · to Save Easy',
          source: 'everyday',
          destination: 'saveEasy',
          reason: `Salary recognised from ${CLIENT.employer}. Your rule moves 29% of the amount above the buffer to Save Easy.`,
          balanceBefore: before - pairs[0],
          balanceAfter: before - pairs[0] - pairs[1],
        },
      });
    }

    // One-off large item (excluded from the forecast's recurring detection).
    if (day === -33) {
      push({
        day,
        label: 'SWISS International Air Lines',
        category: 'leisure',
        amount: -486,
        currency: 'CHF',
        status: 'booked',
      });
    }
    if (day === -61) {
      push({ day, label: 'Amazon.de', category: 'shopping', amount: -74.9, currency: 'EUR', status: 'booked' });
    }
    if (day === -26) {
      push({ day, label: 'Airbnb', category: 'leisure', amount: -212.0, currency: 'EUR', status: 'booked' });
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
  // top-up (§10 verbatim), then the reimbursement that explains today's balance.
  push({
    day: 0,
    label: 'SBB CFF FFS',
    category: 'transport',
    amount: -86.4,
    currency: 'CHF',
    status: 'booked',
  });
  push({
    day: 0,
    label: 'Auto Cover · from Save Easy',
    category: 'smart-liquidity',
    amount: 400,
    currency: 'CHF',
    status: 'booked',
    smart: {
      engine: 'autoCover',
      title: 'Auto Cover · from Save Easy',
      source: 'saveEasy',
      destination: 'everyday',
      reason:
        'Your Everyday balance fell to CHF 480.00, below your minimum of CHF 500.00. Auto Cover topped up one increment of CHF 400.00 from Save Easy, the first source in your list (instant, no cost).',
      balanceBefore: 480.0,
      balanceAfter: 880.0,
    },
  });
  push({
    day: 0,
    label: `Expense reimbursement — ${CLIENT.employer}`,
    category: 'transfer',
    amount: 2_960.5,
    currency: 'CHF',
    status: 'booked',
  });

  return txns;
}
