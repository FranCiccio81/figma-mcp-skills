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
  RECURRING_DEBITS,
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
    autoCover: { ...INITIAL_AUTO_COVER, waterfall: [...INITIAL_AUTO_COVER.waterfall] },
    flags: {
      marketClosed: false,
      salaryDelayed: false,
      salaryMissing: false,
      irregularIncome: false,
      sourcesExhausted: false,
      marginCall: false,
      savingPlanOutage: false,
    },
    pendingSettlements: [],
    pendingAllocation: null,
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
    autoCover: { ...state.autoCover, waterfall: [...state.autoCover.waterfall] },
    flags: { ...state.flags },
    pendingSettlements: [...state.pendingSettlements],
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

interface DrawResult {
  drawn: number;
  parts: { source: MoneySource; amount: number; pending: boolean; fxCost?: number }[];
  skipped: { source: MoneySource; reason: string }[];
}

/** Walk the client-ordered waterfall and draw up to `needed` CHF. */
function drawFromWaterfall(s: EngineState, needed: number): DrawResult {
  const res: DrawResult = { drawn: 0, parts: [], skipped: [] };
  const order: MoneySource[] = [...s.autoCover.waterfall];
  if (s.autoCover.lombardEnabled && s.autoCover.lombardAcknowledged) order.push('lombard');

  for (const source of order) {
    if (res.drawn >= needed) break;
    const want = needed - res.drawn;
    const exhausted = s.flags.sourcesExhausted;

    if (source === 'saveEasy') {
      const avail = exhausted ? 0 : s.accounts.saveEasy;
      const take = Math.min(want, avail);
      if (take <= 0) { res.skipped.push({ source, reason: 'No balance available' }); continue; }
      s.accounts.saveEasy -= take;
      res.parts.push({ source, amount: take, pending: false });
      res.drawn += take;
    } else if (source === 'tradingCash') {
      if (s.flags.marketClosed) {
        res.skipped.push({ source, reason: 'Market closed — Trading cash cannot be moved right now' });
        continue;
      }
      const avail = exhausted ? 0 : s.accounts.tradingCash;
      const take = Math.min(want, avail);
      if (take <= 0) { res.skipped.push({ source, reason: 'No balance available' }); continue; }
      s.accounts.tradingCash -= take;
      res.parts.push({ source, amount: take, pending: false });
      res.drawn += take;
    } else if (source === 'investEasy') {
      const avail = exhausted ? 0 : s.accounts.investEasy;
      const take = Math.min(want, avail);
      if (take <= 0) { res.skipped.push({ source, reason: 'No positions available to sell' }); continue; }
      // A sale settles T+2 — the cash is pending, never shown as spendable early.
      s.accounts.investEasy -= take;
      res.parts.push({ source, amount: take, pending: true });
      res.drawn += take;
    } else if (source === 'eurWallet' || source === 'usdWallet') {
      const rate = source === 'eurWallet' ? FX.eurToChf : FX.usdToChf;
      const balance = exhausted ? 0 : s.accounts[source];
      const availChf = balance * rate;
      const takeChf = Math.min(want, availChf);
      if (takeChf <= 0) { res.skipped.push({ source, reason: 'No balance available' }); continue; }
      const fxCost = Math.round(takeChf * (FX.spreadPct / 100) * 100) / 100;
      s.accounts[source] -= takeChf / rate;
      res.parts.push({ source, amount: takeChf - fxCost, pending: false, fxCost });
      res.drawn += takeChf - fxCost;
    } else if (source === 'lombard') {
      const avail = exhausted ? 0 : s.accounts.lombardAvailable;
      const take = Math.min(want, avail);
      if (take <= 0) { res.skipped.push({ source, reason: 'No credit line available' }); continue; }
      s.accounts.lombardAvailable -= take;
      s.accounts.lombardDrawn += take;
      res.parts.push({ source, amount: take, pending: false });
      res.drawn += take;
    }
  }
  return res;
}

/**
 * Auto Cover — triggered when the balance falls below the minimum or an
 * incoming debit would breach it. Applies the §5.5 guardrails, then draws
 * from the waterfall. Returns true if the shortfall was (or will be) covered.
 */
function attemptAutoCover(s: EngineState, projectedBalance: number): boolean {
  const cfg = s.autoCover;
  if (!cfg.enabled) return false;

  const shortfall = cfg.minBalance - projectedBalance;
  if (shortfall <= 0) return true;

  // Guardrail: cooldown between top-ups.
  if (cfg.lastTopUpDay !== null && s.day - cfg.lastTopUpDay < cfg.cooldownDays) {
    addNotice(s, {
      kind: 'warning',
      title: 'Auto Cover on cooldown',
      body: `A top-up already ran on ${shortDate(cfg.lastTopUpDay)}. The next one can run after ${cfg.cooldownDays} day(s). You can move money manually at any time.`,
    });
    return false;
  }

  // Guardrail: monthly cap.
  const capLeft = cfg.monthlyCap - cfg.usedThisMonth;
  if (capLeft < cfg.topUpIncrement) {
    addNotice(s, {
      kind: 'warning',
      title: 'Auto Cover monthly cap reached',
      body: `Top-ups this month have used ${money(cfg.usedThisMonth)} of your ${money(cfg.monthlyCap)} cap. Move money manually, or raise the cap in Auto Cover settings.`,
    });
    return false;
  }

  // Top-ups run in increments of the configured size.
  const increments = Math.ceil(shortfall / cfg.topUpIncrement);
  const needed = Math.min(increments * cfg.topUpIncrement, capLeft);

  const before = s.accounts.everyday;
  const result = drawFromWaterfall(s, needed);

  for (const part of result.parts) {
    const settlesOnDay = part.pending ? s.day + 2 : undefined;
    if (!part.pending) s.accounts.everyday += part.amount;
    const after = s.accounts.everyday;
    const txn = addTxn(s, {
      day: s.day,
      label: `Auto Cover · from ${SOURCE_LABELS[part.source]}`,
      category: 'smart-liquidity',
      amount: part.amount,
      currency: 'CHF',
      status: part.pending ? 'pending' : 'booked',
      smart: {
        engine: 'autoCover',
        title: `Auto Cover · from ${SOURCE_LABELS[part.source]}`,
        source: part.source,
        destination: 'everyday',
        reason: buildCoverReason(s, before, part.source, part.amount, part.pending, part.fxCost),
        balanceBefore: before,
        balanceAfter: after,
        settlesOnDay,
        fxCostChf: part.fxCost,
        interestRatePa: part.source === 'lombard' ? LOMBARD_RATE_PA : undefined,
      },
    });
    if (part.pending && settlesOnDay !== undefined) {
      s.pendingSettlements.push({ source: part.source, amount: part.amount, settlesOnDay, txnId: txn.id });
    }
  }

  if (result.drawn > 0) {
    cfg.usedThisMonth += result.drawn;
    cfg.lastTopUpDay = s.day;
    const instant = result.parts.filter((p) => !p.pending).reduce((a, p) => a + p.amount, 0);
    if (instant > 0) {
      addNotice(s, {
        kind: 'info',
        title: 'Auto Cover executed',
        body: `${money(instant)} moved to Everyday (${result.parts.filter((p) => !p.pending).map((p) => SOURCE_LABELS[p.source]).join(', ')}). Balance is now ${money(s.accounts.everyday)}.`,
      });
      announce(s, `Auto Cover executed. Everyday balance ${money(s.accounts.everyday)}.`);
    }
    const pendingSum = result.parts.filter((p) => p.pending).reduce((a, p) => a + p.amount, 0);
    if (pendingSum > 0) {
      addNotice(s, {
        kind: 'info',
        title: 'Auto Cover pending settlement',
        body: `${money(pendingSum)} from an Invest Easy sale settles in 2 business days (T+2). It is not spendable until it settles.`,
      });
    }
  }

  if (result.drawn + 0.005 < needed) {
    const remaining = cfg.minBalance - s.accounts.everyday;
    if (remaining > 0 && result.parts.length === 0) {
      s.coverFailedDay = s.day;
      addNotice(s, {
        kind: 'error',
        title: 'Auto Cover could not top up',
        shortfall: remaining,
        body:
          `Every source in your list was unavailable` +
          (result.skipped.length ? ` (${result.skipped.map((k) => `${SOURCE_LABELS[k.source]}: ${k.reason.toLowerCase()}`).join('; ')})` : '') +
          `. Your balance is ${money(remaining)} below your minimum. You can transfer money in, or sell positions manually.`,
      });
      announce(s, `Auto Cover could not top up. Shortfall ${money(remaining)}.`);
      return false;
    }
  }
  return true;
}

function buildCoverReason(
  s: EngineState,
  balanceBefore: number,
  source: MoneySource,
  amount: number,
  pending: boolean,
  fxCost?: number,
): string {
  const base = `Your Everyday balance fell to ${money(balanceBefore)}, below your minimum of ${money(s.autoCover.minBalance)}. Auto Cover drew ${money(amount)} from ${SOURCE_LABELS[source]}, following your source order.`;
  if (pending) return `${base} The sale settles in 2 business days (T+2) — the cash is pending until then.`;
  if (fxCost !== undefined) return `${base} Conversion cost of ${money(fxCost)} (shown before execution) is included.`;
  if (source === 'lombard') return `${base} This is borrowing against your portfolio at ${LOMBARD_RATE_PA}% p.a.`;
  return base;
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

/** Apply one debit against Everyday, with pre-emptive Auto Cover (§5.5). */
function applyDebit(s: EngineState, t: Omit<Txn, 'id' | 'status'>, isDirectDebit: boolean): void {
  const amount = -t.amount; // positive cost
  const projected = s.accounts.everyday - amount;
  if (projected < s.autoCover.minBalance) {
    attemptAutoCover(s, projected);
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
  if (dom === 1) s.autoCover.usedThisMonth = 0; // monthly cap resets

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

  // 6 — safety net: end-of-day balance check (a debit may have slipped through).
  if (s.accounts.everyday < s.autoCover.minBalance) {
    attemptAutoCover(s, s.accounts.everyday);
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
      const w = s.autoCover.waterfall;
      const j = action.index + action.direction;
      if (action.index < 0 || action.index >= w.length || j < 0 || j >= w.length) return prev;
      [w[action.index], w[j]] = [w[j], w[action.index]];
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
