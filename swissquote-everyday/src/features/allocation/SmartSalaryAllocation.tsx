/**
 * Smart Salary Allocation — management dashboard (spec §27).
 *
 * Trigger → Cash Safety Buffer → allocation plan (§28 visual, % AND CHF) →
 * execution preference (§20) → guardrails (§19) → monthly overview (§29) →
 * allocation history (§30, each run explained). Pending approvals and salary
 * anomalies (§26) surface at the top with clear next actions.
 */
import { dateOf, money, roundTo, shortDate, swissNumber } from '../../lib/format';
import { CLIENT } from '../../data/mockLedger';
import { nextSalaryDayAfter } from '../../state/forecast';
import { useStore } from '../../state/store';
import { Toggle } from '../../components/ui';
import type { AllocationSplit, Txn } from '../../state/types';

const PLAN_SWATCH: Record<string, string> = {
  saveEasy: 'plan-bar__segment--saveEasy',
  investEasy: 'plan-bar__segment--investEasy',
  tradingCash: 'plan-bar__segment--tradingCash',
  savingPlan: 'plan-bar__segment--savingPlan',
  goal: 'plan-bar__segment--saveEasy',
};

export function SmartSalaryAllocation() {
  const { state, dispatch, forecast, nav } = useStore();
  const rule = state.allocation;
  const pending = state.pendingAllocation;
  const buffer = rule.bufferMode === 'ai' ? forecast.buffer : rule.manualBuffer;
  const splitTotal = rule.splits.reduce((a, s) => a + s.percent, 0);
  const remainder = 100 - splitTotal;

  // Estimate for the next run — §22 model applied to today's balance + expected salary.
  const estAllocatable = Math.max(0, state.accounts.everyday + CLIENT.salaryNet - buffer);
  const estTotal = Math.min(estAllocatable, rule.maxPerSalary);

  // §29 monthly overview + year total, computed from the ledger.
  const currentMonth = dateOf(state.day).getUTCMonth();
  const monthTxns = state.txns.filter((t) => dateOf(t.day).getUTCMonth() === currentMonth && t.day > state.day - 31);
  const monthSalary = monthTxns.filter((t) => t.category === 'salary').reduce((a, t) => a + t.amount, 0);
  const monthAllocated = monthTxns
    .filter((t) => t.smart?.engine === 'allocation' && t.status === 'booked')
    .reduce((a, t) => a + -t.amount, 0);
  const yearAllocated = state.txns
    .filter((t) => t.smart?.engine === 'allocation' && t.status === 'booked')
    .reduce((a, t) => a + -t.amount, 0);

  // §30 history — allocation runs grouped by day, newest first.
  const runs = new Map<number, Txn[]>();
  for (const t of state.txns) {
    if (t.smart?.engine !== 'allocation') continue;
    const list = runs.get(t.day) ?? [];
    list.push(t);
    runs.set(t.day, list);
  }
  const history = [...runs.entries()].sort((a, b) => b[0] - a[0]).slice(0, 3);

  const setSplit = (i: number, percent: number) => {
    const splits: AllocationSplit[] = rule.splits.map((s, j) => (j === i ? { ...s, percent } : s));
    dispatch({ type: 'setSplits', splits });
  };

  const excessCash = state.accounts.everyday > buffer + 20_000;

  return (
    <div className="screen">
      {/* Status header */}
      <section className="card" aria-label="Plan status">
        <div className="flex items-center justify-between">
          <span className="section-title" style={{ textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            {rule.paused ? 'Paused' : rule.enabled ? 'Active' : 'Not activated'}
          </span>
          <span className="caption">Next expected salary ~{shortDate(nextSalaryDayAfter(state.day))}</span>
        </div>
        <p className="m-0 caption" style={{ marginTop: 'var(--space-2xs)' }}>
          Income: {CLIENT.employer} · ~{money(CLIENT.salaryNet, 'CHF', 0)}/month · confirmed salary
          {rule.scheduledForDay !== null && ` · runs ${shortDate(rule.scheduledForDay)}`}
        </p>
        <div className="flex items-center flex-wrap" style={{ gap: 'var(--space-xs)', marginTop: 'var(--space-sm)' }}>
          <button type="button" className="btn btn--secondary" onClick={() => dispatch({ type: 'setAllocationPaused', paused: !rule.paused })}>
            {rule.paused ? 'Resume' : 'Pause'}
          </button>
          <button type="button" className="btn btn--secondary" aria-pressed={rule.skipNext} onClick={() => dispatch({ type: 'skipNextAllocation' })}>
            {rule.skipNext ? 'Skipping next salary ✓' : 'Skip next allocation'}
          </button>
        </div>
      </section>

      {/* Pending approval / anomaly — §20 & §26 */}
      {pending && (
        <section className={`notice ${pending.anomaly ? 'notice--warning' : 'notice--info'}`} aria-label="Allocation awaiting approval">
          <strong>{pending.anomaly ? 'This payment looks different' : 'Your salary plan is ready'}</strong>
          <p className="m-0 caption" style={{ color: 'var(--color-text-primary)', marginTop: 'var(--space-2xs)' }}>
            {pending.anomaly ?? `${money(pending.total)} can be allocated according to your plan.`}
          </p>
          <ul className="m-0 list-none caption amount" style={{ padding: 0, marginTop: 'var(--space-2xs)' }}>
            {pending.amounts.map((a) => (
              <li key={a.destination}>→ {money(a.amount)} {a.label}</li>
            ))}
          </ul>
          <div className="flex flex-wrap" style={{ gap: 'var(--space-xs)', marginTop: 'var(--space-sm)' }}>
            <button type="button" className="btn btn--primary" onClick={() => dispatch({ type: 'approvePendingAllocation' })}>
              Allocate {money(pending.total, 'CHF', 0)}
            </button>
            <button type="button" className="btn btn--secondary" onClick={() => dispatch({ type: 'skipPendingAllocation' })}>
              Skip this time
            </button>
          </div>
        </section>
      )}

      {/* AI insight — §40, a recommendation, never a silent change */}
      {excessCash && !pending && (
        <section className="ai-card" aria-label="Excess cash insight" style={{ display: 'block' }}>
          <span className="ai-card__eyebrow">Excess cash</span>
          <p className="m-0" style={{ marginTop: 'var(--space-2xs)' }}>
            Your Banking balance is {money(roundTo(state.accounts.everyday - buffer, 100), 'CHF', 0)} above your safety
            buffer. Your next allocation will put up to {money(rule.maxPerSalary, 'CHF', 0)} of it to work — you can
            raise the maximum below if you want more allocated.
          </p>
        </section>
      )}

      {/* Your plan — §28 visual, both % and CHF */}
      <section className="card" aria-label="Your salary plan">
        <h2 className="section-title m-0" style={{ marginBottom: 'var(--space-sm)' }}>Your salary plan</h2>
        <div className="plan-bar" aria-hidden="true">
          <span className="plan-bar__segment plan-bar__segment--keep" style={{ width: `${Math.max(6, (buffer / (buffer + estTotal)) * 100)}%` }} />
          {rule.splits.map((s) => (
            <span
              key={s.destination}
              className={`plan-bar__segment ${PLAN_SWATCH[s.destination]}`}
              style={{ width: `${Math.max(2, ((estTotal * s.percent) / 100 / (buffer + estTotal)) * 100)}%` }}
            />
          ))}
        </div>
        <div className="plan-row" style={{ marginTop: 'var(--space-sm)' }}>
          <span className="plan-row__swatch plan-bar__segment--keep" aria-hidden="true" />
          <span className="flex-1" style={{ fontWeight: 'var(--font-weight-medium)' }}>Keep first in Banking</span>
          <span className="amount" style={{ fontWeight: 'var(--font-weight-semibold)' }}>{money(buffer, 'CHF', 0)}</span>
        </div>
        <p className="micro m-0" style={{ margin: 'var(--space-2xs) 0 var(--space-2xs) calc(10px + var(--space-xs))' }}>
          Then allocate the excess (next run ≈ {money(estTotal, 'CHF', 0)}):
        </p>
        {rule.splits.map((s, i) => (
          <div key={s.destination} className="plan-row">
            <span className={`plan-row__swatch ${PLAN_SWATCH[s.destination]}`} aria-hidden="true" />
            <span className="flex-1 min-w-0">
              <span className="block" style={{ fontWeight: 'var(--font-weight-medium)' }}>{s.label}</span>
              <input
                type="range"
                className="slider"
                style={{ minHeight: 'var(--space-lg)' }}
                min={0}
                max={100}
                step={5}
                value={s.percent}
                onChange={(e) => setSplit(i, Number(e.target.value))}
                aria-label={`Share to ${s.label}, percent`}
              />
            </span>
            <span className="text-right" style={{ minWidth: 'var(--space-2xl)' }}>
              <span className="block amount" style={{ fontWeight: 'var(--font-weight-semibold)' }}>{s.percent}%</span>
              <span className="micro block amount">≈ {swissNumber(roundTo((estTotal * s.percent) / 100, 10), 0)}</span>
            </span>
          </div>
        ))}
        <p className="caption m-0" role="status">
          Stays in Banking beyond the buffer: <strong className="amount">{remainder}%</strong>
          {remainder < 0 && ' — splits cannot exceed 100%'}
        </p>
      </section>

      {/* Cash Safety Buffer — §10–§12 */}
      <section className="card" aria-label="Cash Safety Buffer">
        <h2 className="section-title m-0" style={{ marginBottom: 'var(--space-xs)' }}>Cash Safety Buffer</h2>
        <p className="m-0 amount" style={{ fontSize: 'var(--font-size-title)', fontWeight: 'var(--font-weight-bold)' }}>
          {money(buffer)}
        </p>
        <p className="caption m-0">
          {rule.bufferMode === 'ai'
            ? `Recommended from your recent Banking activity (range ${money(forecast.bufferLow, 'CHF', 0)}–${money(forecast.bufferHigh, 'CHF', 0)}) — covers about one month of usual payments. Smart Liquidity only allocates money above this amount.`
            : 'Your own amount. Smart Liquidity only allocates money above it.'}
        </p>
        <div className="flex items-center" style={{ gap: 'var(--space-xs)', marginTop: 'var(--space-sm)' }}>
          <button type="button" className={`btn ${rule.bufferMode === 'ai' ? 'btn--primary' : 'btn--secondary'}`} onClick={() => dispatch({ type: 'setBufferMode', mode: 'ai' })}>
            Use recommended
          </button>
          <button type="button" className={`btn ${rule.bufferMode === 'manual' ? 'btn--primary' : 'btn--secondary'}`} onClick={() => dispatch({ type: 'setBufferMode', mode: 'manual', manualBuffer: buffer })}>
            Choose my own
          </button>
        </div>
        {rule.bufferMode === 'manual' && (
          <label className="block" style={{ marginTop: 'var(--space-sm)' }}>
            <span className="caption">Keep at least {money(rule.manualBuffer)}</span>
            <input
              type="range"
              className="slider"
              min={4000}
              max={24000}
              step={100}
              value={rule.manualBuffer}
              onChange={(e) => dispatch({ type: 'setBufferMode', mode: 'manual', manualBuffer: Number(e.target.value) })}
              aria-label="Cash Safety Buffer amount"
            />
          </label>
        )}
      </section>

      {/* Execution preference — §20 */}
      <section className="card" aria-label="Execution preference">
        <h2 className="section-title m-0" style={{ marginBottom: 'var(--space-sm)' }}>Execution</h2>
        <div className="flex flex-col" style={{ gap: 'var(--space-xs)' }} role="radiogroup" aria-label="Execution preference">
          <button type="button" className="choice-row" role="radio" aria-checked={rule.mode === 'automatic'} onClick={() => dispatch({ type: 'setAllocationMode', mode: 'automatic' })}>
            <span className="choice-row__dot" aria-hidden="true" />
            <span>
              <span className="block" style={{ fontWeight: 'var(--font-weight-medium)' }}>Automatic</span>
              <span className="caption block">Allocate my salary automatically when it arrives. I'm notified every time.</span>
            </span>
          </button>
          <button type="button" className="choice-row" role="radio" aria-checked={rule.mode === 'review'} onClick={() => dispatch({ type: 'setAllocationMode', mode: 'review' })}>
            <span className="choice-row__dot" aria-hidden="true" />
            <span>
              <span className="block" style={{ fontWeight: 'var(--font-weight-medium)' }}>Review before allocation</span>
              <span className="caption block">Prepare the allocation and ask me to approve it. If I don't approve, nothing moves.</span>
            </span>
          </button>
        </div>
      </section>

      {/* Guardrails — §19 */}
      <section className="card" aria-label="Guardrails">
        <h2 className="section-title m-0" style={{ marginBottom: 'var(--space-xs)' }}>Guardrails</h2>
        <label className="block" style={{ marginBottom: 'var(--space-sm)' }}>
          <span className="caption">
            Maximum per salary: <strong className="amount">{money(rule.maxPerSalary, 'CHF', 0)}</strong> — never allocate more after one salary payment.
          </span>
          <input
            type="range"
            className="slider"
            min={5000}
            max={50000}
            step={1000}
            value={rule.maxPerSalary}
            onChange={(e) => dispatch({ type: 'setMaxPerSalary', value: Number(e.target.value) })}
            aria-label="Maximum allocation per salary"
          />
        </label>
        <label className="flex items-center justify-between" style={{ gap: 'var(--space-sm)' }}>
          <span>
            <span className="block" style={{ fontWeight: 'var(--font-weight-medium)' }}>Salary variation protection</span>
            <span className="caption block">If the salary differs by more than ±{rule.variancePct}%, ask me first instead of allocating.</span>
          </span>
          <Toggle checked={rule.askOnVariance} onChange={(v) => dispatch({ type: 'setAskOnVariance', value: v })} label="Ask first on unusual salary" />
        </label>
        <p className="caption m-0" style={{ marginTop: 'var(--space-sm)' }}>
          Minimum allocation {money(rule.minAllocation, 'CHF', 0)} — below that, everything stays in Banking. A negative
          Banking balance can never be created by an allocation.
        </p>
      </section>

      {/* Monthly overview — §29 */}
      <section className="card card--subtle" aria-label="Monthly overview">
        <h2 className="section-title m-0" style={{ marginBottom: 'var(--space-xs)' }}>This month</h2>
        <dl className="m-0 grid grid-cols-2" style={{ gap: 'var(--space-2xs) var(--space-sm)', fontSize: 'var(--font-size-caption)' }}>
          <dt className="caption m-0">Salary received</dt>
          <dd className="m-0 amount">{money(monthSalary)}</dd>
          <dt className="caption m-0">Automatically allocated</dt>
          <dd className="m-0 amount">{money(monthAllocated)}</dd>
          <dt className="caption m-0">Kept available</dt>
          <dd className="m-0 amount">{money(state.accounts.everyday)}</dd>
        </dl>
        <p className="caption m-0" style={{ marginTop: 'var(--space-sm)' }}>
          Automatically saved/invested since tracking began: <strong className="amount">{money(yearAllocated, 'CHF', 0)}</strong>
        </p>
      </section>

      {/* Allocation history — §30/§31 */}
      <section aria-label="Allocation history">
        <h2 className="section-title" style={{ margin: '0 0 var(--space-xs)' }}>Allocation history</h2>
        <div className="flex flex-col" style={{ gap: 'var(--space-xs)' }}>
          {history.map(([day, txns]) => {
            const ok = txns.filter((t) => t.status === 'booked');
            const failed = txns.filter((t) => t.status === 'failed');
            const total = ok.reduce((a, t) => a + -t.amount, 0);
            return (
              <button key={day} type="button" className="card" style={{ width: '100%', textAlign: 'left' }} onClick={() => { nav.go('transactions'); }}>
                <div className="flex items-baseline justify-between">
                  <span style={{ fontWeight: 'var(--font-weight-semibold)' }}>{shortDate(day)}</span>
                  <span className="amount" style={{ fontWeight: 'var(--font-weight-semibold)' }}>{money(total)}</span>
                </div>
                <p className="caption m-0" style={{ marginTop: 'var(--space-2xs)' }}>
                  {ok.map((t) => `${t.smart?.destination ? t.smart.title.replace('Smart Salary Allocation · to ', '') : ''} ${money(-t.amount, 'CHF', 0)} ✓`).join(' · ')}
                  {failed.length > 0 && ` · ${failed.map((t) => `${t.smart?.title.replace('Smart Salary Allocation · to ', '')} ${money(-t.amount, 'CHF', 0)} not completed`).join(' · ')}`}
                </p>
                <span className="caption link">Why this amount? View details</span>
              </button>
            );
          })}
          {history.length === 0 && <p className="caption m-0">No allocations yet — the first runs one business day after your salary.</p>}
        </div>
      </section>

      <p className="micro m-0">
        Trigger: confirmed salary from {CLIENT.employer} (any credit ≥ CHF 5'000 recognised as recurring income
        ⟨threshold TO CONFIRM⟩). Executes on income + 1 business day. Changes apply from your next salary allocation.
        Each destination keeps its own product, suitability and disclosure requirements.
      </p>
    </div>
  );
}
