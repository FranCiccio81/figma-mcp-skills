/**
 * §5.3 Smart Salary Allocation — rule builder + running state.
 * Buffer first (AI by default, overridable), then splits of the remainder.
 * Preview is neutral: what the rule WOULD HAVE moved, no performance claim.
 * Skip next and Pause are one tap away.
 */
import { money, shortDate } from '../../lib/format';
import { CLIENT } from '../../data/mockLedger';
import { nextSalaryDayAfter } from '../../state/forecast';
import { useStore } from '../../state/store';
import { ScreenHeader, Toggle } from '../../components/ui';
import type { AllocationSplit } from '../../state/types';

export function SmartSalaryAllocation() {
  const { state, dispatch, forecast, nav } = useStore();
  const rule = state.allocation;
  const buffer = rule.bufferMode === 'ai' ? forecast.buffer : rule.manualBuffer;
  const splitTotal = rule.splits.reduce((a, s) => a + s.percent, 0);
  const remainder = 100 - splitTotal;

  // Neutral preview: apply the rule to the last 3 salaries in the ledger.
  const salaries = state.txns.filter((t) => t.category === 'salary' && t.day < state.day).slice(-6);
  const wouldHaveMoved = salaries.reduce((sum, s) => {
    const movable = Math.max(0, s.amount - Math.min(buffer, s.amount));
    return sum + (movable * splitTotal) / 100;
  }, 0);

  const setSplit = (i: number, percent: number) => {
    const splits: AllocationSplit[] = rule.splits.map((s, j) => (j === i ? { ...s, percent } : s));
    dispatch({ type: 'setSplits', splits });
  };

  return (
    <div className="screen">
      <ScreenHeader title="Smart Salary Allocation" onBack={() => nav.go('home')} />

      <section className="card" aria-label="Running state">
        <h2 className="section-title m-0" style={{ marginBottom: 'var(--space-xs)' }}>Running state</h2>
        {rule.paused ? (
          <p className="m-0">Paused — nothing moves until you resume.</p>
        ) : rule.scheduledForDay !== null ? (
          <p className="m-0">Next run: {shortDate(rule.scheduledForDay)} (one business day after your salary).</p>
        ) : (
          <p className="m-0">
            Waiting for salary — expected around {shortDate(nextSalaryDayAfter(state.day))}. Any credit of
            CHF 2'000 or more recognised as recurring income triggers the rule. ⟨threshold TO CONFIRM⟩
          </p>
        )}
        {rule.lastRun && (
          <p className="caption m-0" style={{ marginTop: 'var(--space-2xs)' }}>
            Last run {shortDate(rule.lastRun.day)}:{' '}
            {rule.lastRun.moved.map((m) => `${money(m.amount)} to ${rule.splits.find((s) => s.destination === m.destination)?.label ?? m.destination}`).join(' · ')}
          </p>
        )}
        <div className="flex items-center" style={{ gap: 'var(--space-xs)', marginTop: 'var(--space-sm)' }}>
          <button
            type="button"
            className="btn btn--secondary"
            aria-pressed={rule.skipNext}
            onClick={() => dispatch({ type: 'skipNextAllocation' })}
          >
            {rule.skipNext ? 'Skip next: on' : 'Skip next'}
          </button>
          <button
            type="button"
            className="btn btn--secondary"
            onClick={() => dispatch({ type: 'setAllocationPaused', paused: !rule.paused })}
          >
            {rule.paused ? 'Resume' : 'Pause'}
          </button>
        </div>
      </section>

      <section className="card" aria-label="Buffer">
        <h2 className="section-title m-0" style={{ marginBottom: 'var(--space-xs)' }}>1 · Always keep in Everyday</h2>
        <p className="m-0 amount" style={{ fontSize: 'var(--font-size-title)', fontWeight: 'var(--font-weight-bold)' }}>
          {money(buffer)}
        </p>
        <p className="caption m-0">
          {rule.bufferMode === 'ai'
            ? `AI estimate for your next 30 days (range ${money(forecast.bufferLow)}–${money(forecast.bufferHigh)}). You can override it.`
            : 'Your manual buffer. The AI estimate updates monthly if you switch back.'}
        </p>
        <div className="flex items-center" style={{ gap: 'var(--space-xs)', marginTop: 'var(--space-sm)' }}>
          <button
            type="button"
            className={`btn ${rule.bufferMode === 'ai' ? 'btn--primary' : 'btn--secondary'}`}
            onClick={() => dispatch({ type: 'setBufferMode', mode: 'ai' })}
          >
            Use AI estimate
          </button>
          <button
            type="button"
            className={`btn ${rule.bufferMode === 'manual' ? 'btn--primary' : 'btn--secondary'}`}
            onClick={() => dispatch({ type: 'setBufferMode', mode: 'manual', manualBuffer: buffer })}
          >
            Set my own
          </button>
        </div>
        {rule.bufferMode === 'manual' && (
          <label className="block" style={{ marginTop: 'var(--space-sm)' }}>
            <span className="caption">Buffer: {money(rule.manualBuffer)}</span>
            <input
              type="range"
              className="slider"
              min={1000}
              max={8000}
              step={50}
              value={rule.manualBuffer}
              onChange={(e) => dispatch({ type: 'setBufferMode', mode: 'manual', manualBuffer: Number(e.target.value) })}
              aria-label="Manual buffer amount"
            />
          </label>
        )}
      </section>

      <section className="card" aria-label="Split of the remainder">
        <h2 className="section-title m-0" style={{ marginBottom: 'var(--space-xs)' }}>2 · Split what's above the buffer</h2>
        {rule.splits.map((s, i) => (
          <label key={s.destination} className="block" style={{ marginBottom: 'var(--space-sm)' }}>
            <span className="flex items-baseline justify-between">
              <span style={{ fontWeight: 'var(--font-weight-medium)' }}>{s.label}</span>
              <span className="amount caption">{s.percent}%</span>
            </span>
            <input
              type="range"
              className="slider"
              min={0}
              max={100}
              step={1}
              value={s.percent}
              onChange={(e) => setSplit(i, Number(e.target.value))}
              aria-label={`Share to ${s.label}, percent`}
            />
          </label>
        ))}
        <p className="caption m-0" role="status">
          Stays in Everyday: <strong className="amount">{remainder}%</strong>
          {remainder < 0 && ' — splits cannot exceed 100%'}
        </p>
        <label className="flex items-center justify-between" style={{ marginTop: 'var(--space-sm)', gap: 'var(--space-sm)' }}>
          <span>
            <span className="block" style={{ fontWeight: 'var(--font-weight-medium)' }}>Percentage of received</span>
            <span className="caption block">For irregular income: split a share of each credit instead of the surplus above a fixed buffer.</span>
          </span>
          <Toggle
            checked={rule.basis === 'percentOfReceived'}
            onChange={(v) => dispatch({ type: 'setBasis', basis: v ? 'percentOfReceived' : 'excess' })}
            label="Percentage of received mode"
          />
        </label>
      </section>

      <section className="card card--subtle" aria-label="Preview">
        <h2 className="section-title m-0" style={{ marginBottom: 'var(--space-xs)' }}>Before you rely on it</h2>
        <p className="m-0">
          Applied to your last {salaries.length} salary credits, this rule would have moved{' '}
          <strong className="amount">{money(Math.round(wouldHaveMoved / 100) * 100)}</strong> out of cash.
        </p>
        <p className="micro m-0" style={{ marginTop: 'var(--space-2xs)' }}>
          This describes past cash movements only. It is not investment advice and says nothing about returns.
        </p>
      </section>

      <p className="micro m-0">
        Trigger: any credit ≥ CHF 2'000 recognised as recurring income from {CLIENT.employer}, or a payer you nominate.
        Executes on income + 1 business day.
      </p>
    </div>
  );
}
