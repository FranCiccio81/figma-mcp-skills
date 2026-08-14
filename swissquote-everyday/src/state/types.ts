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
  | 'lombard';

export interface Accounts {
  /** Everyday CHF balance — the only figure ever shown as "in the account". */
  everyday: number;
  eurWallet: number;
  usdWallet: number;
  saveEasy: number;
  tradingCash: number;
  investEasy: number;
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

export type AllocationDestination = 'tradingCash' | 'investEasy' | 'saveEasy' | 'goal';

export interface AllocationSplit {
  destination: AllocationDestination;
  label: string;
  /** Share of the amount above the buffer, in percent. All splits total ≤ 100; the remainder stays in Everyday. */
  percent: number;
}

export interface AllocationRule {
  enabled: boolean;
  paused: boolean;
  skipNext: boolean;
  /** `ai` = use the forecast buffer; `manual` = client override. */
  bufferMode: 'ai' | 'manual';
  manualBuffer: number;
  /** `excess` = split what is above the buffer; `percentOfReceived` = irregular-income mode. */
  basis: 'excess' | 'percentOfReceived';
  splits: AllocationSplit[];
  /** Set when salary is recognised; allocation executes on the next business day. */
  scheduledForDay: number | null;
  lastRun: { day: number; moved: { destination: AllocationDestination; amount: number }[] } | null;
}

export interface AutoCoverConfig {
  /** Off by default — same pattern as Auto FX. */
  enabled: boolean;
  /** Balance below this triggers a top-up (or an incoming debit that would breach it). */
  minBalance: number;
  /** Client-ordered sources. Lombard is pinned last and gated separately. */
  waterfall: Exclude<MoneySource, 'everyday' | 'lombard'>[];
  lombardEnabled: boolean;
  lombardAcknowledged: boolean;
  /** Guardrails — §5.5, displayed on screen. */
  topUpIncrement: number;
  monthlyCap: number;
  cooldownDays: number;
  usedThisMonth: number;
  lastTopUpDay: number | null;
}

/** Prototype-only levers to force each §6 edge case. Not part of the product surface. */
export interface SimFlags {
  marketClosed: boolean;
  salaryDelayed: boolean;
  salaryMissing: boolean;
  irregularIncome: boolean;
  sourcesExhausted: boolean;
  marginCall: boolean;
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
  notices: EngineNotice[];
  /** Day the last Auto Cover attempt failed with sources exhausted; cleared once the balance recovers. */
  coverFailedDay: number | null;
  /** Latest balance announcement for the screen-reader live region. */
  announcement: string;
  /** Monotonic counter for deterministic ids. */
  seq: number;
}
