/**
 * Smart Liquidity engine — a real state machine over the mock ledger (§6).
 *
 * It evaluates the client's rules (Smart Salary Allocation, Auto Cover) against
 * the ledger day by day and produces the resulting transactions, notices and
 * account states. The UI renders this state; it never fakes an outcome.
 *
 * States: healthy → approachingMinimum → autoCoverPending → autoCoverExecuted
 *         → autoCoverFailed → rulesPaused (any state, when the client pauses).
 */
import { money, mulberry32, nextBusinessDay, shortDate } from '../lib/format';
import {
  CLIENT,
  FX,
  SPEND_SCALE,
  INITIAL_ACCOUNTS,
  INITIAL_ALLOCATION,
  INITIAL_AUTO_COVER,
  LOMBARD_RATE_PA,
  PENDING_CARD_RESERVED,
  RECURRING_DEBITS,
  SAVE_EASY_PENALTY_FREE,
  TRADING_ORDERS_RESERVED,
  generateHistory,
  salaryCreditDay,
} from '../data/mockLedger';
import { computeForecast } from './forecast';
import type {
  AllocationRule,
  AllocationSplit,
  EngineNotice,
  EngineState,
  MoneySource,
  SafetyLevel,
  SimFlags,
  Txn,
} from './types';

export const SOURCE_LABELS: Record<MoneySource, string> = {
  everyday: 'Everyday',
  eurWallet: 'EUR wallet',
  usdWallet: 'USD wallet',
  saveEasy: 'Save Easy',
  tradingCash: 'Trading cash',
  investEasy: 'Invest Easy',
  savingPlan: 'Global ETF Saving Plan',
  lombard: 'Lombard credit',
};

export function initialState(): EngineState {
  return {
    day: 0,
    accounts: { ...INITIAL_ACCOUNTS },
    txns: generateHistory(),
    status: 'healthy',
    allocation: { ...INITIAL_ALLOCATION, splits: INITIAL_ALLOCATION.splits.map((s) => ({ ...s })) },
    autoCover: { ...INITIAL_AUTO_COVER, sources: INITIAL_AUTO_COVER.sources.map((x) => ({ ...x })) },
    flags: {
      marketClosed: false,
      salaryDelayed: false,
      salaryMissing: false,
      irregularIncome: false,
      sourcesExhausted: false,
      marginCall: false,
      savingPlanOutage: false,
      tradingUnavailable: false,
    },
    pendingSettlements: [],
    pendingAllocation: null,
    plannedExpenses: [],
    notices: [],
    coverFailedDay: null,
    announcement: '',
    seq: 0,
  };
}

export type EngineAction =
  | { type: 'advanceDay' }
  | { type: 'setAllocationMode'; mode: 'automatic' | 'review' }
  | { type: 'setMaxPerSalary'; value: number }
  | { type: 'setAskOnVariance'; value: boolean }
  | { type: 'approvePendingAllocation' }
  | { type: 'skipPendingAllocation' }
  | { type: 'setAutoCoverEnabled'; enabled: boolean }
  | { type: 'setMinBalance'; value: number }
  | { type: 'moveWaterfallSource'; index: number; direction: -1 | 1 }
  | { type: 'setLombard'; enabled: boolean; acknowledged: boolean }
  /* Auto Cover — spec configuration */
  | { type: 'toggleCoverSource'; source: MoneySource; enabled: boolean }
  | { type: 'setCoverMode'; mode: 'exact' | 'buffer'; bufferAmount?: number }
  | { type: 'setPerTransactionMax'; value: number }
  | { type: 'setCoverMonthlyCap'; value: number }
  | { type: 'setTradingReserve'; value: number }
  | { type: 'setLombardCoverLimits'; perCover?: number; monthly?: number }
  | { type: 'setKeepMinimum'; enabled: boolean }
  /* AI Budgeting — spec configuration */
  | { type: 'setSafetyLevel'; level: SafetyLevel }
  | { type: 'setKeepBoundaries'; min?: number; max?: number }
  | { type: 'addPlannedExpense'; label: string; amount: number }
  | { type: 'removePlannedExpense'; id: string }
  | { type: 'setAllocationPaused'; paused: boolean }
  | { type: 'skipNextAllocation' }
  | { type: 'setBufferMode'; mode: 'ai' | 'manual'; manualBuffer?: number }
  | { type: 'setBasis'; basis: AllocationRule['basis'] }
  | { type: 'setSplits'; splits: AllocationSplit[] }
  | { type: 'setFlag'; flag: keyof SimFlags; value: boolean }
  | { type: 'triggerMarginCall' }
  | { type: 'resolveMarginCall' }
  | { type: 'dismissNotice'; id: string }
  | { type: 'manualTransferIn'; amount: number }
  /** Prototype rig: a payment that Everyday alone cannot fund (Auto Cover §7 Use Case A). */
  | { type: 'simulateLargePayment'; label: string; amount: number }
  | { type: 'pauseAll' }
  | { type: 'resumeAll' };

/* ------------------------------------------------------------------ */
/* Internal helpers — every mutation happens on a draft copy.          */
/* ------------------------------------------------------------------ */

function draft(state: EngineState): EngineState {
  return {
    ...state,
    accounts: { ...state.accounts },
    txns: [...state.txns],
    allocation: { ...state.allocation, splits: state.allocation.splits.map((s) => ({ ...s })) },
    autoCover: { ...state.autoCover, sources: state.autoCover.sources.map((x) => ({ ...x })) },
    flags: { ...state.flags },
    pendingSettlements: [...state.pendingSettlements],
    plannedExpenses: [...state.plannedExpenses],
    notices: [...state.notices],
  };
}

function nextId(s: EngineState, prefix: string): string {
  s.seq += 1;
  return `${prefix}-${s.seq}`;
}

function addNotice(s: EngineState, n: Omit<EngineNotice, 'id' | 'day'>): void {
  s.notices = [{ id: nextId(s, 'ntc'), day: s.day, ...n }, ...s.notices].slice(0, 12);
}

function addTxn(s: EngineState, t: Omit<Txn, 'id'>): Txn {
  const txn: Txn = { id: nextId(s, 'txn'), ...t };
  s.txns = [...s.txns, txn];
  return txn;
}

function announce(s: EngineState, text: string): void {
  s.announcement = text;
}

/** §6 state derivation — one place, applied after every mutation. */
function deriveStatus(s: EngineState): void {
  const { accounts, autoCover, allocation } = s;
  if (s.coverFailedDay !== null && accounts.everyday < autoCover.minBalance) {
    s.status = 'autoCoverFailed';
    return;
  }
  s.coverFailedDay = null;
  if (s.pendingSettlements.length > 0) {
    s.status = 'autoCoverPending';
    return;
  }
  if (allocation.paused) {
    s.status = 'rulesPaused';
    return;
  }
  if (autoCover.enabled && autoCover.lastTopUpDay === s.day) {
    s.status = 'autoCoverExecuted';
    return;
  }
  if (accounts.everyday < autoCover.minBalance + 1_000) {
    s.status = 'approachingMinimum';
    return;
  }
  s.status = 'healthy';
}

export interface CoverPart {
  source: MoneySource;
  /** CHF credited to Everyday, after any conversion cost. */
  amount: number;
  fxCost?: number;
  isCredit?: boolean;
}

export interface CoverPlan {
  parts: CoverPart[];
  total: number;
  /** Amount the authorised sources could NOT provide. */
  missing: number;
  skipped: { source: MoneySource; reason: string }[];
  usesLombard: boolean;
}

/**
 * What a single source can contribute right now, after product conditions
 * (open orders, penalty-free limits, market hours) and the client's own
 * limits (trading reserve, per-source monthly cap). Pure — no mutation.
 */
export function sourceCoverCapacity(s: EngineState, source: MoneySource): { amount: number; reason?: string } {
  return sourceCapacity(s, source);
}

/** Total Auto Cover capacity, own cash and credit kept apart (§13/§84). */
export function coverCapacity(s: EngineState): { own: number; credit: number } {
  const own = s.autoCover.sources.reduce((sum, x) => sum + sourceCapacity(s, x.source).amount, 0);
  const credit = sourceCapacity(s, 'lombard').amount;
  return { own: Math.round(own), credit: Math.round(credit) };
}

function sourceCapacity(s: EngineState, source: MoneySource): { amount: number; reason?: string } {
  const cfg = s.autoCover;
  const exhausted = s.flags.sourcesExhausted;
  const cfgSource = cfg.sources.find((x) => x.source === source);

  if (source === 'lombard') {
    if (!cfg.lombardEnabled || !cfg.lombardAcknowledged) {
      return { amount: 0, reason: 'Automatic borrowing is off' };
    }
    const monthLeft = cfg.lombardMonthlyMax - cfg.lombardUsedThisMonth;
    const amount = Math.max(
      0,
      Math.min(exhausted ? 0 : s.accounts.lombardAvailable, cfg.lombardPerCoverMax, monthLeft),
    );
    return amount > 0 ? { amount } : { amount: 0, reason: 'Borrowing limit reached' };
  }

  if (!cfgSource || !cfgSource.enabled) return { amount: 0, reason: 'Not authorised for Auto Cover' };
  const monthLeft = cfgSource.monthlyLimit - cfgSource.usedThisMonth;
  if (monthLeft <= 0) return { amount: 0, reason: 'Monthly limit for this source reached' };

  if (source === 'saveEasy') {
    // Only the amount withdrawable without a notice period or penalty (§20).
    const penaltyFree = Math.max(0, SAVE_EASY_PENALTY_FREE - cfgSource.usedThisMonth);
    const amount = Math.max(0, Math.min(exhausted ? 0 : s.accounts.saveEasy, penaltyFree, monthLeft));
    return amount > 0 ? { amount } : { amount: 0, reason: 'No penalty-free balance available' };
  }

  if (source === 'tradingCash') {
    if (s.flags.marketClosed || s.flags.tradingUnavailable) {
      return { amount: 0, reason: 'Temporarily unavailable — Auto Cover will skip this source' };
    }
    // Open orders and the client's own trading reserve are never touched (§22/§23).
    const free = s.accounts.tradingCash - TRADING_ORDERS_RESERVED - cfg.tradingReserve;
    const amount = Math.max(0, Math.min(exhausted ? 0 : free, monthLeft));
    return amount > 0 ? { amount } : { amount: 0, reason: 'Reserved for open orders and your Trading reserve' };
  }

  if (source === 'eurWallet' || source === 'usdWallet') {
    const rate = source === 'eurWallet' ? FX.eurToChf : FX.usdToChf;
    const grossChf = (exhausted ? 0 : s.accounts[source]) * rate;
    const netChf = grossChf * (1 - FX.spreadPct / 100);
    const amount = Math.max(0, Math.min(netChf, monthLeft));
    return amount > 0 ? { amount } : { amount: 0, reason: 'No balance available' };
  }

  return { amount: 0, reason: 'Not eligible' };
}

/**
 * Build the complete funding plan BEFORE moving anything (§55 pre-check).
 * Own cash first, in the client's order; Lombard only ever last.
 */
function planCover(s: EngineState, needed: number): CoverPlan {
  const cfg = s.autoCover;
  const plan: CoverPlan = { parts: [], total: 0, missing: 0, skipped: [], usesLombard: false };

  // Global ceilings: per transaction and what remains of the monthly cap.
  const budget = Math.min(needed, cfg.perTransactionMax, Math.max(0, cfg.monthlyCap - cfg.usedThisMonth));

  const order: MoneySource[] = [...cfg.sources.map((x) => x.source), 'lombard'];
  for (const source of order) {
    if (plan.total >= budget - 0.005) break;
    const { amount, reason } = sourceCapacity(s, source);
    if (amount <= 0) {
      if (reason) plan.skipped.push({ source, reason });
      continue;
    }
    const take = Math.min(amount, budget - plan.total);
    const isCredit = source === 'lombard';
    const fxCost =
      source === 'eurWallet' || source === 'usdWallet'
        ? Math.round(take * (FX.spreadPct / 100) * 100) / 100
        : undefined;
    plan.parts.push({ source, amount: take, fxCost, isCredit });
    plan.total += take;
    if (isCredit) plan.usesLombard = true;
  }
  plan.missing = Math.max(0, needed - plan.total);
  return plan;
}


/**
 * Auto Cover — brings authorised liquidity back to Everyday when a payment
 * needs more than the account holds (transaction cover, the spec's MVP), or
 * when the optional keep-minimum mode is on.
 *
 * All-or-nothing: the full funding plan is computed first, and if the
 * authorised sources cannot cover the whole shortfall, nothing is moved
 * (§54/§55) — no transfers that fail to solve the problem.
 */
function attemptAutoCover(s: EngineState, shortfall: number, trigger: string): boolean {
  const cfg = s.autoCover;
  if (!cfg.enabled || cfg.paused) return false;
  if (shortfall <= 0) return true;

  // Cover the exact shortfall, plus a buffer if the client configured one (§29).
  const needed = cfg.coverMode === 'buffer' ? shortfall + cfg.bufferAmount : shortfall;
  const plan = planCover(s, needed);

  // All-or-nothing: unless the plan clears the whole shortfall, nothing moves —
  // a partial transfer would not solve the problem it was meant to solve (§54).
  if (plan.total + 0.005 < shortfall) {
    s.coverFailedDay = s.day;
    const monthlyLeft = cfg.monthlyCap - cfg.usedThisMonth;
    const limitReached = monthlyLeft <= 0 || shortfall > cfg.perTransactionMax;
    addNotice(s, {
      kind: 'error',
      title: limitReached ? 'Auto Cover limit reached' : "We couldn't cover this payment",
      shortfall: shortfall - plan.total,
      body: limitReached
        ? `This would need ${money(shortfall)}, above your ${money(cfg.perTransactionMax)} per-payment limit or your ${money(cfg.monthlyCap)} monthly limit (${money(cfg.usedThisMonth)} used). Auto Cover stays on but won't move more until you change the limits.`
        : `${money(shortfall)} was required, but your authorised sources could provide ${money(plan.total)}. ` +
          (plan.skipped.length
            ? `${plan.skipped.map((k) => `${SOURCE_LABELS[k.source]}: ${k.reason.toLowerCase()}`).join('; ')}. `
            : '') +
          (!cfg.lombardEnabled && s.accounts.lombardAvailable > 0
            ? 'You have Lombard capacity available, but automatic borrowing is off. '
            : '') +
          'No money was moved.',
    });
    announce(s, `Auto Cover could not cover ${money(shortfall)}.`);
    return false;
  }

  // Execute the plan.
  const before = s.accounts.everyday;
  for (const part of plan.parts) {
    if (part.source === 'saveEasy') s.accounts.saveEasy -= part.amount;
    else if (part.source === 'tradingCash') s.accounts.tradingCash -= part.amount;
    else if (part.source === 'eurWallet') s.accounts.eurWallet -= (part.amount + (part.fxCost ?? 0)) / FX.eurToChf;
    else if (part.source === 'usdWallet') s.accounts.usdWallet -= (part.amount + (part.fxCost ?? 0)) / FX.usdToChf;
    else if (part.source === 'lombard') {
      s.accounts.lombardAvailable -= part.amount;
      s.accounts.lombardDrawn += part.amount;
      cfg.lombardUsedThisMonth += part.amount;
    }
    const cfgSource = cfg.sources.find((x) => x.source === part.source);
    if (cfgSource) cfgSource.usedThisMonth += part.amount;

    s.accounts.everyday += part.amount;
    addTxn(s, {
      day: s.day,
      label: part.isCredit
        ? 'Auto Cover · borrowed through Lombard'
        : `Auto Cover · from ${SOURCE_LABELS[part.source]}`,
      category: 'smart-liquidity',
      amount: part.amount,
      currency: 'CHF',
      status: 'booked',
      smart: {
        engine: 'autoCover',
        title: part.isCredit
          ? 'Auto Cover · borrowed through Lombard'
          : `Auto Cover · from ${SOURCE_LABELS[part.source]}`,
        source: part.source,
        destination: 'everyday',
        reason: buildCoverReason(s, trigger, shortfall, plan, part),
        balanceBefore: before,
        balanceAfter: s.accounts.everyday,
        fxCostChf: part.fxCost,
        interestRatePa: part.isCredit ? LOMBARD_RATE_PA : undefined,
      },
    });
  }

  cfg.usedThisMonth += plan.total;
  cfg.lastTopUpDay = s.day;

  const ownCash = plan.parts.filter((p) => !p.isCredit).reduce((a, p) => a + p.amount, 0);
  const borrowed = plan.parts.filter((p) => p.isCredit).reduce((a, p) => a + p.amount, 0);
  addNotice(s, {
    kind: borrowed > 0 ? 'warning' : 'info',
    title: borrowed > 0 ? 'Lombard Auto Cover was used' : 'Payment covered automatically',
    body:
      (borrowed > 0
        ? `${money(ownCash)} came from your own cash and ${money(borrowed)} was borrowed through your Lombard facility — your borrowing has increased by ${money(borrowed)}. `
        : `We moved ${money(plan.total)} from ${plan.parts.map((p) => SOURCE_LABELS[p.source]).join(' and ')} so your ${trigger} could go through. `) +
      `Everyday balance is now ${money(s.accounts.everyday)}.`,
  });
  announce(s, `Auto Cover moved ${money(plan.total)}. Everyday balance ${money(s.accounts.everyday)}.`);
  return true;
}

/** §63 explainability — why it ran, why this source, why this amount. */
function buildCoverReason(
  s: EngineState,
  trigger: string,
  shortfall: number,
  plan: CoverPlan,
  part: CoverPart,
): string {
  const cfg = s.autoCover;
  const position = plan.parts.indexOf(part) + 1;
  const why =
    part.source === 'lombard'
      ? 'Your own cash sources could not cover the whole amount, so Lombard — your last authorised source — was used.'
      : position === 1
        ? `${SOURCE_LABELS[part.source]} is your first Auto Cover source and had eligible cash available.`
        : `${SOURCE_LABELS[part.source]} is next in your source order; the previous source could not cover the whole amount.`;
  const amountWhy =
    cfg.coverMode === 'buffer'
      ? `You chose to cover the shortfall plus a ${money(cfg.bufferAmount)} buffer, so ${money(plan.total)} was moved in total.`
      : `You chose Exact Cover, so only the ${money(shortfall)} shortfall was moved.`;
  const extra =
    part.fxCost !== undefined
      ? ` The conversion cost of ${money(part.fxCost)} is included.`
      : part.source === 'lombard'
        ? ` Interest applies to borrowed amounts at ${LOMBARD_RATE_PA}% p.a. This is credit, not your own cash.`
        : '';
  return `Your Everyday balance was ${money(shortfall)} short for ${trigger}. ${why} ${amountWhy}${extra}`;
}

/**
 * §22 — allocatable liquidity, never a blind percentage of salary:
 * available balance − Cash Safety Buffer, capped by the client's
 * maximum per salary. Zero or below the minimum allocation → nothing moves.
 */
function computeAllocationAmounts(s: EngineState): {
  buffer: number;
  allocatable: number;
  total: number;
  amounts: { destination: AllocationRule['splits'][number]['destination']; label: string; amount: number }[];
} {
  const rule = s.allocation;
  const buffer = rule.bufferMode === 'ai' ? computeForecast(s).buffer : rule.manualBuffer;
  const base =
    rule.basis === 'percentOfReceived' ? Math.max(rule.lastReceived, 0) : Number.POSITIVE_INFINITY;
  const allocatable = Math.min(Math.max(0, s.accounts.everyday - buffer), base);
  const total = Math.min(allocatable, rule.maxPerSalary);
  const amounts = rule.splits
    .map((split) => ({
      destination: split.destination,
      label: split.label,
      amount: Math.round((total * split.percent) / 100 / 10) * 10,
    }))
    .filter((a) => a.amount > 0);
  return { buffer, allocatable, total, amounts };
}

/** §31 explainability — the calculation, spelled out. */
function buildAllocationReason(
  s: EngineState,
  buffer: number,
  allocatable: number,
  total: number,
  split: { label: string; amount: number },
  percent: number,
): string {
  const rule = s.allocation;
  const capped = total < allocatable - 1;
  return (
    `${money(rule.lastReceived)} was received from ${CLIENT.employer}. ` +
    `Your plan keeps at least ${money(buffer)} available in Banking (${rule.bufferMode === 'ai' ? 'recommended Cash Safety Buffer' : 'your Cash Safety Buffer'}), leaving ${money(allocatable)} allocatable. ` +
    (capped ? `Your maximum of ${money(rule.maxPerSalary)} per salary applied, so ${money(total)} was distributed. ` : `${money(total)} was distributed according to your plan. `) +
    `${percent}% went to ${split.label}: ${money(split.amount)}.`
  );
}

/** Move the approved amounts. Destinations fail independently — §35/FR-17/FR-18. */
function executeAllocation(
  s: EngineState,
  calc: ReturnType<typeof computeAllocationAmounts>,
): void {
  const rule = s.allocation;
  const moved: { destination: AllocationRule['splits'][number]['destination']; amount: number }[] = [];
  let failedAmount = 0;
  for (const part of calc.amounts) {
    const percent = rule.splits.find((x) => x.destination === part.destination)?.percent ?? 0;
    const before = s.accounts.everyday;
    // §36 — an unavailable destination keeps its share in Banking, never redirected.
    if (part.destination === 'savingPlan' && s.flags.savingPlanOutage) {
      failedAmount += part.amount;
      addTxn(s, {
        day: s.day,
        label: `Smart Salary Allocation · to ${part.label}`,
        category: 'smart-liquidity',
        amount: -part.amount,
        currency: 'CHF',
        status: 'failed',
        smart: {
          engine: 'allocation',
          title: `Smart Salary Allocation · to ${part.label}`,
          source: 'everyday',
          destination: part.destination,
          reason: `${buildAllocationReason(s, calc.buffer, calc.allocatable, calc.total, part, percent)} The Saving Plan could not accept the transfer, so this amount stayed in Banking. It was not redirected to any other product.`,
          balanceBefore: before,
          balanceAfter: before,
        },
      });
      continue;
    }
    s.accounts.everyday -= part.amount;
    if (part.destination === 'investEasy') s.accounts.investEasy += part.amount;
    else if (part.destination === 'saveEasy') s.accounts.saveEasy += part.amount;
    else if (part.destination === 'tradingCash') s.accounts.tradingCash += part.amount;
    else if (part.destination === 'savingPlan') s.accounts.savingPlan += part.amount;
    addTxn(s, {
      day: s.day,
      label: `Smart Salary Allocation · to ${part.label}`,
      category: 'smart-liquidity',
      amount: -part.amount,
      currency: 'CHF',
      status: 'booked',
      smart: {
        engine: 'allocation',
        title: `Smart Salary Allocation · to ${part.label}`,
        source: 'everyday',
        destination: part.destination === 'goal' ? 'saveEasy' : part.destination,
        reason: buildAllocationReason(s, calc.buffer, calc.allocatable, calc.total, part, percent),
        balanceBefore: before,
        balanceAfter: s.accounts.everyday,
      },
    });
    moved.push({ destination: part.destination, amount: part.amount });
  }
  rule.lastRun = { day: s.day, moved };
  const okTotal = moved.reduce((a, m) => a + m.amount, 0);
  if (failedAmount > 0) {
    addNotice(s, {
      kind: 'warning',
      title: 'Most of your salary plan was completed',
      body: `${money(okTotal)} was allocated, but ${money(failedAmount)} could not be sent to your Saving Plan and stayed in Banking. It was not moved to any other product. You can try again or keep it in Banking.`,
    });
  } else {
    addNotice(s, {
      kind: 'info',
      title: 'Your salary is working',
      body: `${money(okTotal)} was allocated: ${moved.map((m) => `${money(m.amount)} → ${rule.splits.find((x) => x.destination === m.destination)?.label ?? m.destination}`).join(', ')}. ${money(calc.buffer)} stays available in Banking.`,
    });
  }
  announce(s, `Allocation executed. ${money(okTotal)} moved. Banking balance ${money(s.accounts.everyday)}.`);
}

/** Smart Salary Allocation — runs on income + 1 business day. */
function runAllocation(s: EngineState): void {
  const rule = s.allocation;
  rule.scheduledForDay = null;
  if (!rule.enabled || rule.paused) return;
  if (rule.skipNext) {
    rule.skipNext = false;
    addNotice(s, {
      kind: 'info',
      title: 'Allocation skipped',
      body: 'This salary allocation was skipped, as you asked. The plan resumes with your next salary.',
    });
    return;
  }

  const calc = computeAllocationAmounts(s);

  // §37 — below the minimum allocation, nothing moves and the client is told why.
  if (calc.total < rule.minAllocation) {
    addNotice(s, {
      kind: 'info',
      title: 'Your salary stayed in Banking',
      body: `There wasn't enough excess liquidity above your ${money(calc.buffer)} safety buffer (minimum allocation ${money(rule.minAllocation)}). No action is required.`,
    });
    return;
  }

  // §19/§26 — an unusual salary pauses the automation and asks first.
  const expected = CLIENT.salaryNet;
  const variance = expected > 0 ? Math.abs(rule.lastReceived - expected) / expected : 0;
  const anomaly =
    rule.askOnVariance && variance > rule.variancePct / 100
      ? `${money(rule.lastReceived)} arrived from your salary payer — significantly ${rule.lastReceived > expected ? 'above' : 'below'} your usual ${money(expected)}. The allocation was paused for your review.`
      : null;

  // §20 — review mode prepares the allocation and asks for approval.
  if (rule.mode === 'review' || anomaly) {
    s.pendingAllocation = {
      preparedDay: s.day,
      received: rule.lastReceived,
      total: calc.total,
      amounts: calc.amounts.map((a) => ({ ...a })),
      anomaly,
    };
    addNotice(s, {
      kind: anomaly ? 'warning' : 'info',
      title: anomaly ? 'This payment looks different' : 'Your salary plan is ready',
      body: anomaly ?? `${money(calc.total)} can be allocated according to your plan. Approve it, or it lapses with your next salary.`,
    });
    announce(s, anomaly ?? `Salary plan ready. ${money(calc.total)} awaiting your approval.`);
    return;
  }

  executeAllocation(s, calc);
}

/**
 * Apply one debit against Everyday. Auto Cover runs BEFORE the payment when
 * the available balance (booked minus authorised card transactions) cannot
 * fund it — transaction cover, the spec's primary trigger (§7 Use Case A).
 */
function applyDebit(s: EngineState, t: Omit<Txn, 'id' | 'status'>, isDirectDebit: boolean): void {
  const amount = -t.amount; // positive cost
  const cfg = s.autoCover;
  const available = s.accounts.everyday - PENDING_CARD_RESERVED;
  // Use Case A: the payment itself is short. Use Case B (advanced): the
  // payment would take the balance below the client's minimum.
  const paymentShortfall = amount - available;
  const minimumShortfall = cfg.keepMinimumEnabled ? cfg.minBalance - (available - amount) : 0;
  const shortfall = Math.max(paymentShortfall, minimumShortfall);
  if (shortfall > 0) {
    attemptAutoCover(s, Math.ceil(shortfall), `your ${money(amount)} ${isDirectDebit ? 'payment' : 'card payment'} to ${t.label}`);
  }
  if (s.accounts.everyday - amount < 0) {
    // Not enough even after cover: a card payment is declined; a direct debit fails.
    addTxn(s, { ...t, status: 'failed' });
    addNotice(s, {
      kind: 'error',
      title: isDirectDebit ? 'Direct debit failed' : 'Card payment declined',
      shortfall: amount - s.accounts.everyday,
      body: `${t.label} for ${money(amount)} could not be paid — your Everyday balance is ${money(s.accounts.everyday)}. Transfer money in, or sell positions, then the payment can be retried.`,
    });
    announce(s, `${isDirectDebit ? 'Direct debit failed' : 'Card declined'}: ${t.label}, ${money(amount)}.`);
    return;
  }
  s.accounts.everyday -= amount;
  addTxn(s, { ...t, status: 'booked' });
}

/** One simulated day: settlements → scheduled debits → salary → allocation → card spend. */
function advanceDay(prev: EngineState): EngineState {
  const s = draft(prev);
  s.day += 1;
  const dom = new Date(Date.UTC(2026, 7, 14) + s.day * 86_400_000).getUTCDate();
  if (dom === 1) {
    // Monthly caps reset — overall, per source, and Lombard.
    s.autoCover.usedThisMonth = 0;
    s.autoCover.lombardUsedThisMonth = 0;
    s.autoCover.sources = s.autoCover.sources.map((x) => ({ ...x, usedThisMonth: 0 }));
  }

  // 1 — settle due T+2 sales: the pending cash becomes spendable now.
  const due = s.pendingSettlements.filter((p) => p.settlesOnDay <= s.day);
  s.pendingSettlements = s.pendingSettlements.filter((p) => p.settlesOnDay > s.day);
  for (const p of due) {
    s.accounts.everyday += p.amount;
    s.txns = s.txns.map((t) =>
      t.id === p.txnId
        ? { ...t, status: 'booked', smart: t.smart ? { ...t.smart, balanceAfter: s.accounts.everyday } : t.smart }
        : t,
    );
    addNotice(s, {
      kind: 'info',
      title: 'Auto Cover settled',
      body: `${money(p.amount)} from the ${SOURCE_LABELS[p.source]} sale has settled and is now spendable. Balance: ${money(s.accounts.everyday)}.`,
    });
    announce(s, `Settlement complete. Everyday balance ${money(s.accounts.everyday)}.`);
  }

  // 2 — recurring debits due today.
  for (const r of RECURRING_DEBITS) {
    if (dom === r.dayOfMonth) {
      applyDebit(
        s,
        { day: s.day, label: r.label, category: r.category, amount: -r.amount, currency: 'CHF' },
        true,
      );
    }
  }

  // 3 — salary. If it is early, late or missing, the allocation waits — it does not guess.
  const expectedToday = salaryCreditDay(s.day);
  const delayedArrival = s.flags.salaryDelayed && salaryCreditDay(s.day - 3);
  if ((expectedToday && !s.flags.salaryDelayed && !s.flags.salaryMissing) || delayedArrival) {
    const amount = s.flags.irregularIncome
      ? Math.round((12_000 + mulberry32(s.day)() * 30_000) / 100) * 100
      : CLIENT.salaryNet;
    s.accounts.everyday += amount;
    addTxn(s, {
      day: s.day,
      label: `Salary — ${CLIENT.employer}`,
      category: 'salary',
      amount,
      currency: 'CHF',
      status: 'booked',
    });
    // A prepared-but-unapproved allocation lapses when the next salary arrives (§20).
    if (s.pendingAllocation) {
      s.pendingAllocation = null;
      addNotice(s, {
        kind: 'info',
        title: 'Previous salary plan lapsed',
        body: 'The prepared allocation was not approved before this salary arrived, so no transfer occurred.',
      });
    }
    s.allocation.lastReceived = amount;
    s.allocation.scheduledForDay = nextBusinessDay(s.day);
    addNotice(s, {
      kind: 'info',
      title: delayedArrival ? 'Salary arrived (late)' : 'Salary arrived',
      body: `${money(amount)} from ${CLIENT.employer}. Smart Salary Allocation is scheduled for ${shortDate(s.allocation.scheduledForDay)}.`,
    });
    announce(s, `Salary received. Everyday balance ${money(s.accounts.everyday)}.`);
  } else if (expectedToday && (s.flags.salaryDelayed || s.flags.salaryMissing)) {
    addNotice(s, {
      kind: 'warning',
      title: 'Salary not received yet',
      body: 'Your salary was expected today and has not arrived. Smart Salary Allocation waits for the money — it does not run on a guess.',
    });
  }

  // 4 — allocation scheduled for today (income + 1 business day).
  if (s.allocation.scheduledForDay === s.day) runAllocation(s);

  // 5 — everyday card spend, deterministic per day.
  const rng = mulberry32(s.day * 7_919 + 17);
  const roll = rng();
  const count = roll < 0.25 ? 0 : roll < 0.6 ? 1 : roll < 0.9 ? 2 : 3;
  const pool: { label: string; category: Txn['category']; min: number; max: number }[] = [
    { label: 'Coop Lausanne St-François', category: 'groceries', min: 12, max: 85 },
    { label: 'Migros Lausanne Flon', category: 'groceries', min: 9, max: 70 },
    { label: 'SBB CFF FFS', category: 'transport', min: 3.6, max: 46 },
    { label: 'Boulangerie Saint-Pierre', category: 'dining', min: 4.2, max: 14 },
    { label: 'Café de Grancy', category: 'dining', min: 6.5, max: 26 },
    { label: 'TWINT · P2P payment', category: 'transfer', min: 10, max: 60 },
  ];
  // The sim pool skews to smaller everyday merchants than the history pool;
  // the extra factor keeps simulated card spend at the same ≈CHF 1'800/month.
  const SIM_POOL_FACTOR = 1.25;
  for (let i = 0; i < count; i += 1) {
    const m = pool[Math.floor(rng() * pool.length)];
    const amount = Math.round((m.min + rng() * (m.max - m.min)) * SPEND_SCALE * SIM_POOL_FACTOR * 20) / 20;
    applyDebit(
      s,
      { day: s.day, label: m.label, category: m.category, amount: -amount, currency: 'CHF' },
      false,
    );
  }

  // 6 — advanced keep-minimum mode: top Everyday back up at the end of the day.
  if (s.autoCover.keepMinimumEnabled) {
    const available = s.accounts.everyday - PENDING_CARD_RESERVED;
    if (available < s.autoCover.minBalance) {
      attemptAutoCover(s, Math.ceil(s.autoCover.minBalance - available), 'your minimum Everyday balance');
    }
  }

  deriveStatus(s);
  return s;
}

/* ------------------------------------------------------------------ */
/* Reducer                                                             */
/* ------------------------------------------------------------------ */

export function reduce(prev: EngineState, action: EngineAction): EngineState {
  switch (action.type) {
    case 'advanceDay':
      return advanceDay(prev);

    case 'setAutoCoverEnabled': {
      const s = draft(prev);
      s.autoCover.enabled = action.enabled;
      deriveStatus(s);
      return s;
    }
    case 'setMinBalance': {
      const s = draft(prev);
      s.autoCover.minBalance = Math.max(0, action.value);
      deriveStatus(s);
      return s;
    }
    case 'moveWaterfallSource': {
      const s = draft(prev);
      const w = s.autoCover.sources;
      const j = action.index + action.direction;
      if (action.index < 0 || action.index >= w.length || j < 0 || j >= w.length) return prev;
      [w[action.index], w[j]] = [w[j], w[action.index]];
      return s;
    }
    case 'toggleCoverSource': {
      const s = draft(prev);
      const src = s.autoCover.sources.find((x) => x.source === action.source);
      if (!src) return prev;
      src.enabled = action.enabled;
      return s;
    }
    case 'setCoverMode': {
      const s = draft(prev);
      s.autoCover.coverMode = action.mode;
      if (action.bufferAmount !== undefined) s.autoCover.bufferAmount = Math.max(0, action.bufferAmount);
      return s;
    }
    case 'setPerTransactionMax': {
      const s = draft(prev);
      s.autoCover.perTransactionMax = Math.max(0, action.value);
      return s;
    }
    case 'setCoverMonthlyCap': {
      const s = draft(prev);
      s.autoCover.monthlyCap = Math.max(0, action.value);
      return s;
    }
    case 'setTradingReserve': {
      const s = draft(prev);
      s.autoCover.tradingReserve = Math.max(0, action.value);
      return s;
    }
    case 'setLombardCoverLimits': {
      const s = draft(prev);
      if (action.perCover !== undefined) s.autoCover.lombardPerCoverMax = Math.max(0, action.perCover);
      if (action.monthly !== undefined) s.autoCover.lombardMonthlyMax = Math.max(0, action.monthly);
      return s;
    }
    case 'setKeepMinimum': {
      const s = draft(prev);
      s.autoCover.keepMinimumEnabled = action.enabled;
      deriveStatus(s);
      return s;
    }
    case 'setSafetyLevel': {
      const s = draft(prev);
      s.allocation.safetyLevel = action.level;
      return s;
    }
    case 'setKeepBoundaries': {
      const s = draft(prev);
      if (action.min !== undefined) s.allocation.minKeep = Math.max(0, action.min);
      if (action.max !== undefined) s.allocation.maxKeep = Math.max(0, action.max);
      if (s.allocation.maxKeep < s.allocation.minKeep) s.allocation.maxKeep = s.allocation.minKeep;
      return s;
    }
    case 'addPlannedExpense': {
      const s = draft(prev);
      s.plannedExpenses = [
        ...s.plannedExpenses,
        { id: nextId(s, 'plan'), label: action.label, amount: Math.max(0, action.amount) },
      ];
      return s;
    }
    case 'removePlannedExpense': {
      const s = draft(prev);
      s.plannedExpenses = s.plannedExpenses.filter((p) => p.id !== action.id);
      return s;
    }
    case 'setLombard': {
      const s = draft(prev);
      // Lombard can only be enabled with an explicit risk acknowledgement.
      s.autoCover.lombardEnabled = action.enabled && action.acknowledged;
      s.autoCover.lombardAcknowledged = action.acknowledged;
      return s;
    }
    case 'setAllocationMode': {
      const s = draft(prev);
      s.allocation.mode = action.mode;
      return s;
    }
    case 'setMaxPerSalary': {
      const s = draft(prev);
      s.allocation.maxPerSalary = Math.max(0, action.value);
      return s;
    }
    case 'setAskOnVariance': {
      const s = draft(prev);
      s.allocation.askOnVariance = action.value;
      return s;
    }
    case 'approvePendingAllocation': {
      if (!prev.pendingAllocation) return prev;
      const s = draft(prev);
      s.pendingAllocation = null;
      // Recompute at approval time — the balance may have moved since preparation.
      const calc = computeAllocationAmounts(s);
      if (calc.total < s.allocation.minAllocation) {
        addNotice(s, {
          kind: 'info',
          title: 'Nothing left to allocate',
          body: `Since the plan was prepared, your available liquidity fell below the ${money(s.allocation.minAllocation)} minimum. Your money stayed in Banking.`,
        });
        deriveStatus(s);
        return s;
      }
      executeAllocation(s, calc);
      deriveStatus(s);
      return s;
    }
    case 'skipPendingAllocation': {
      if (!prev.pendingAllocation) return prev;
      const s = draft(prev);
      s.pendingAllocation = null;
      addNotice(s, {
        kind: 'info',
        title: 'Allocation skipped',
        body: 'The prepared allocation was skipped. Your money stays in Banking; the plan resumes with your next salary.',
      });
      return s;
    }
    case 'setAllocationPaused': {
      const s = draft(prev);
      s.allocation.paused = action.paused;
      deriveStatus(s);
      return s;
    }
    case 'skipNextAllocation': {
      const s = draft(prev);
      s.allocation.skipNext = !s.allocation.skipNext;
      return s;
    }
    case 'setBufferMode': {
      const s = draft(prev);
      s.allocation.bufferMode = action.mode;
      if (action.manualBuffer !== undefined) s.allocation.manualBuffer = action.manualBuffer;
      return s;
    }
    case 'setBasis': {
      const s = draft(prev);
      s.allocation.basis = action.basis;
      return s;
    }
    case 'setSplits': {
      const s = draft(prev);
      const total = action.splits.reduce((a, x) => a + x.percent, 0);
      if (total > 100) return prev;
      s.allocation.splits = action.splits.map((x) => ({ ...x }));
      return s;
    }
    case 'setFlag': {
      const s = draft(prev);
      s.flags[action.flag] = action.value;
      deriveStatus(s);
      return s;
    }
    case 'triggerMarginCall': {
      // Markets fell: the Lombard line shrinks below what is drawn.
      const s = draft(prev);
      s.flags.marginCall = true;
      const drawn = Math.max(s.accounts.lombardDrawn, 28_800);
      s.accounts.lombardDrawn = drawn;
      s.accounts.lombardAvailable = Math.max(0, drawn - 13_200);
      addNotice(s, {
        kind: 'marginCall',
        title: 'Margin call on your Lombard credit',
        shortfall: 13_200,
        body: `Markets have fallen and your portfolio no longer fully covers what you have borrowed. Add ${money(13_200)} by tomorrow 16:00, or Swissquote may sell positions to restore cover.`,
      });
      announce(s, 'Margin call on your Lombard credit. Action required.');
      return s;
    }
    case 'resolveMarginCall': {
      const s = draft(prev);
      s.flags.marginCall = false;
      s.notices = s.notices.filter((n) => n.kind !== 'marginCall');
      return s;
    }
    case 'dismissNotice': {
      const s = draft(prev);
      s.notices = s.notices.filter((n) => n.id !== action.id);
      return s;
    }
    case 'manualTransferIn': {
      const s = draft(prev);
      s.accounts.everyday += action.amount;
      addTxn(s, {
        day: s.day,
        label: 'Transfer in — manual',
        category: 'transfer',
        amount: action.amount,
        currency: 'CHF',
        status: 'booked',
      });
      announce(s, `Money moved. Everyday balance ${money(s.accounts.everyday)}.`);
      deriveStatus(s);
      return s;
    }
    case 'simulateLargePayment': {
      const s = draft(prev);
      applyDebit(
        s,
        { day: s.day, label: action.label, category: 'transfer', amount: -action.amount, currency: 'CHF' },
        true,
      );
      deriveStatus(s);
      return s;
    }
    case 'pauseAll': {
      const s = draft(prev);
      s.allocation.paused = true;
      s.autoCover.enabled = false;
      deriveStatus(s);
      return s;
    }
    case 'resumeAll': {
      const s = draft(prev);
      s.allocation.paused = false;
      s.autoCover.enabled = true;
      deriveStatus(s);
      return s;
    }
    default:
      return prev;
  }
}
