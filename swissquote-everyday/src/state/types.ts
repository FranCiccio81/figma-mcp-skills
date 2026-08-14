/**
 * Shared domain types for the Smart Liquidity engine, the mock ledger and the UI.
 * The engine is a real state machine over this model — screens only render it.
 */
import type { Currency } from '../lib/format';

/** Every pool of value the engine can move money between. */
export type MoneySource =
  | 'everyday'
  | 'eurWallet'
  | 'usdWallet'
  | 'saveEasy'
  | 'tradingCash'
  | 'investEasy'
  | 'savingPlan'
  | 'lombard';

export interface Accounts {
  /** Everyday CHF balance — the only figure ever shown as "in the account". */
  everyday: number;
  eurWallet: number;
  usdWallet: number;
  saveEasy: number;
  tradingCash: number;
  investEasy: number;
  /** Global ETF Saving Plan — funded by allocation, invested by the plan itself. */
  savingPlan: number;
  lombardAvailable: number;
  lombardDrawn: number;
}

export type TxnCategory =
  | 'housing'
  | 'insurance'
  | 'groceries'
  | 'dining'
  | 'transport'
  | 'shopping'
  | 'health'
  | 'leisure'
  | 'subscription'
  | 'salary'
  | 'transfer'
  | 'smart-liquidity';

export interface SmartMeta {
  engine: 'autoCover' | 'allocation';
  /** Plain inline label, e.g. `Auto Cover · from Save Easy`. */
  title: string;
  source?: MoneySource;
  destination?: MoneySource;
  /** Which rule fired and why — shown verbatim in the transaction detail. */
  reason: string;
  balanceBefore: number;
  balanceAfter: number;
  /** Set while a T+2 sale has not settled — the cash is NOT spendable yet. */
  settlesOnDay?: number;
  fxCostChf?: number;
  interestRatePa?: number;
}

export interface Txn {
  id: string;
  day: number;
  label: string;
  category: TxnCategory;
  /** Signed amount in the account currency. Negative = money out of Everyday. */
  amount: number;
  currency: Currency;
  status: 'booked' | 'pending' | 'failed';
  smart?: SmartMeta;
}

/** §6 — the visible states of the Everyday account. */
export type EngineStatus =
  | 'healthy'
  | 'approachingMinimum'
  | 'autoCoverPending'
  | 'autoCoverExecuted'
  | 'autoCoverFailed'
  | 'rulesPaused';

export type AllocationDestination = 'tradingCash' | 'investEasy' | 'saveEasy' | 'savingPlan' | 'goal';

export interface AllocationSplit {
  destination: AllocationDestination;
  label: string;
  /** Share of the allocatable amount, in percent. All splits total ≤ 100; the remainder stays in Banking. */
  percent: number;
}

/** A prepared allocation waiting for the client (review mode or salary anomaly). */
export interface PendingAllocation {
  preparedDay: number;
  received: number;
  total: number;
  amounts: { destination: AllocationDestination; label: string; amount: number }[];
  /** Set when the salary differed from the expected amount beyond the variance guardrail. */
  anomaly: string | null;
}

/** AI Budgeting conservativeness — §17: shown as CHF values, never labels alone. */
export type SafetyLevel = 'efficient' | 'balanced' | 'cautious';

export interface AllocationRule {
  enabled: boolean;
  paused: boolean;
  skipNext: boolean;
  /** Execution preference — §20: allocate automatically, or prepare and ask. */
  mode: 'automatic' | 'review';
  /** `ai` = AI Budgeting predicts the keep amount; `manual` = fixed liquidity fallback. */
  bufferMode: 'ai' | 'manual';
  manualBuffer: number;
  /** AI Budgeting settings — safety level and the client's hard corridor (§17/§18). */
  safetyLevel: SafetyLevel;
  minKeep: number;
  maxKeep: number;
  /** `excess` = split what is above the buffer; `percentOfReceived` = irregular-income mode. */
  basis: 'excess' | 'percentOfReceived';
  splits: AllocationSplit[];
  /** Guardrails — §19/§22. */
  maxPerSalary: number;
  minAllocation: number;
  /** Ask first when the salary differs from the expected amount by more than variancePct. */
  askOnVariance: boolean;
  variancePct: number;
  /** Set when salary is recognised; allocation executes on the next business day. */
  scheduledForDay: number | null;
  /** Amount of the salary credit that scheduled the current run. */
  lastReceived: number;
  lastRun: { day: number; moved: { destination: AllocationDestination; amount: number }[] } | null;
}

/** A client-authorised Auto Cover funding source, with its own monthly cap (§33). */
export interface AutoCoverSource {
  source: Extract<MoneySource, 'saveEasy' | 'tradingCash' | 'eurWallet' | 'usdWallet'>;
  enabled: boolean;
  monthlyLimit: number;
  usedThisMonth: number;
}

export interface AutoCoverConfig {
  /** Off by default — opt-in only, same pattern as Auto FX (§6.1). */
  enabled: boolean;
  paused: boolean;
  /** Exact shortfall, or shortfall + a buffer left in Everyday afterwards (§29). */
  coverMode: 'exact' | 'buffer';
  bufferAmount: number;
  /** Guardrails — §32. */
  perTransactionMax: number;
  monthlyCap: number;
  usedThisMonth: number;
  /** Client-ordered own-cash sources; Lombard is separate and always last. */
  sources: AutoCoverSource[];
  /** Keep at least this much in Trading for tactical use (§23). */
  tradingReserve: number;
  /** Lombard is opted into separately, behind an explicit acknowledgement (§34–36). */
  lombardEnabled: boolean;
  lombardAcknowledged: boolean;
  lombardPerCoverMax: number;
  lombardMonthlyMax: number;
  lombardUsedThisMonth: number;
  lastTopUpDay: number | null;
  /** Advanced: keep Everyday topped up to this balance (§31 Use Case B). */
  keepMinimumEnabled: boolean;
  minBalance: number;
}

/** Prototype-only levers to force each §6 edge case. Not part of the product surface. */
export interface SimFlags {
  marketClosed: boolean;
  salaryDelayed: boolean;
  salaryMissing: boolean;
  irregularIncome: boolean;
  sourcesExhausted: boolean;
  marginCall: boolean;
  /** Forces the Saving Plan destination to fail — §35 partial-failure demo. */
  savingPlanOutage: boolean;
  /** Makes Trading cash temporarily untransferable — Auto Cover §66. */
  tradingUnavailable: boolean;
}

export interface PendingSettlement {
  source: MoneySource;
  amount: number;
  settlesOnDay: number;
  txnId: string;
}

export interface EngineNotice {
  id: string;
  day: number;
  kind: 'info' | 'warning' | 'error' | 'marginCall';
  title: string;
  body: string;
  shortfall?: number;
}

export interface EngineState {
  /** Simulation day. 0 = 14 August 2026. */
  day: number;
  accounts: Accounts;
  txns: Txn[];
  status: EngineStatus;
  allocation: AllocationRule;
  autoCover: AutoCoverConfig;
  flags: SimFlags;
  pendingSettlements: PendingSettlement[];
  /** Prepared allocation awaiting the client's approval (review mode / anomaly). */
  pendingAllocation: PendingAllocation | null;
  /** Client-declared future spending the forecast must protect (§32 / FR-14). */
  plannedExpenses: { id: string; label: string; amount: number }[];
  notices: EngineNotice[];
  /** Day the last Auto Cover attempt failed with sources exhausted; cleared once the balance recovers. */
  coverFailedDay: number | null;
  /** Latest balance announcement for the screen-reader live region. */
  announcement: string;
  /** Monotonic counter for deterministic ids. */
  seq: number;
}
