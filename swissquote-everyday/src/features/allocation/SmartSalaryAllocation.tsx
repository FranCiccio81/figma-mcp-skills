/**
 * Smart Salary Allocation — §27 management view, kept deliberately simple.
 *
 * Default = a glance: status, anything needing action, the plan at a glance
 * (§28 visual, % and CHF), and recent activity. Everything configurable
 * (splits, buffer, execution mode, guardrails) lives behind "Edit plan" —
 * editing is a task (§32), not the default reading of the page.
 */
import { useState } from 'react';
import { money, roundTo, shortDate, swissNumber } from '../../lib/format';
import { CLIENT } from '../../data/mockLedger';
import { PlanBar, PLAN_SWATCH } from '../../components/PlanBar';
import { nextSalaryDayAfter } from '../../state/forecast';
import { useStore } from '../../state/store';
import { Toggle } from '../../components/ui';
import type { AllocationSplit, Txn } from '../../state/types';

export function SmartSalaryAllocation() {
  const { state, dispatch, forecast, nav } = useStore();
  const [editing, setEditing] = useState(false);
  const rule = state.allocation;
  const pending = state.pendingAllocation;
  const buffer = rule.bufferMode === 'ai' ? forecast.buffer : rule.manualBuffer;

  // §22 estimate for the next run, from today's balance + the expected salary.
  const estTotal = Math.min(Math.max(0, state.accounts.everyday + CLIENT.salaryNet - buffer), rule.maxPerSalary);

  return (
    <div className="screen">
      {/* Anything that needs the client's decision always comes first. */}
      {pending && (
        <section className={`notice ${pending.anomaly ? 'notice--warning' : 'notice--info'}`} aria-label="Allocation awaiting approval">
          <strong>{pending.anomaly ? 'This payment looks different' : 'Your salary plan is ready'}</strong>
          <p className="m-0 caption" style={{ color: 'var(--color-text-primary)', marginTop: 'var(--space-2xs)' }}>
            {pending.anomaly ?? `${money(pending.total)} ready to move, exactly as your plan says.`}
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
              Not this time
            </button>
          </div>
        </section>
      )}

      {editing ? <PlanEditor onDone={() => setEditing(false)} /> : <PlanSummary onEdit={() => setEditing(true)} estTotal={estTotal} buffer={buffer} />}

      {!editing && <ActivityCard onOpenTransactions={() => nav.go('transactions')} />}

      <p className="micro m-0">
        Runs one business day after your salary from {CLIENT.employer} lands. Every destination keeps its own product,
        suitability and disclosure rules — we don't bend those.
      </p>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Glance view                                                         */
/* ------------------------------------------------------------------ */

function PlanSummary({ onEdit, estTotal, buffer }: { onEdit: () => void; estTotal: number; buffer: number }) {
  const { state, dispatch } = useStore();
  const rule = state.allocation;

  return (
    <section className="card" aria-label="Your salary plan">
      <div className="flex items-center justify-between" style={{ marginBottom: 'var(--space-2xs)' }}>
        <span className="section-title" style={{ textTransform: 'uppercase', letterSpacing: '0.05em' }}>
          {rule.paused ? 'Paused' : 'Active'}
        </span>
        <span className="caption">Next salary ~{shortDate(nextSalaryDayAfter(state.day))}</span>
      </div>
      <p className="m-0" style={{ fontWeight: 'var(--font-weight-medium)', marginBottom: 'var(--space-sm)' }}>
        Keep {money(buffer, 'CHF', 0)}. Put ≈ {money(estTotal, 'CHF', 0)} to work.
      </p>

      <PlanBar buffer={buffer} estTotal={estTotal} splits={rule.splits} />

      <div style={{ marginTop: 'var(--space-sm)' }}>
        <div className="plan-row" style={{ padding: 'var(--space-2xs) 0' }}>
          <span className="plan-row__swatch plan-bar__segment--keep" aria-hidden="true" />
          <span className="flex-1 caption" style={{ color: 'var(--color-text-primary)' }}>Stays in Banking</span>
          <span className="amount caption" style={{ fontWeight: 'var(--font-weight-semibold)', color: 'var(--color-text-primary)' }}>
            ≥ {swissNumber(buffer, 0)}
          </span>
        </div>
        {rule.splits.map((s) => (
          <div key={s.destination} className="plan-row" style={{ padding: 'var(--space-2xs) 0' }}>
            <span className={`plan-row__swatch ${PLAN_SWATCH[s.destination]}`} aria-hidden="true" />
            <span className="flex-1 caption" style={{ color: 'var(--color-text-primary)' }}>{s.label}</span>
            <span className="caption amount">{s.percent}%</span>
            <span className="amount caption" style={{ fontWeight: 'var(--font-weight-semibold)', color: 'var(--color-text-primary)', minWidth: 'var(--space-2xl)', textAlign: 'right' }}>
              ≈ {swissNumber(roundTo((estTotal * s.percent) / 100, 10), 0)}
            </span>
          </div>
        ))}
      </div>

      <p className="micro m-0" style={{ marginTop: 'var(--space-xs)' }}>
        {rule.mode === 'automatic' ? 'Runs on its own' : 'Asks you first, every time'} · never more than {money(rule.maxPerSalary, 'CHF', 0)} a salary
      </p>

      <div className="flex items-center flex-wrap" style={{ gap: 'var(--space-xs)', marginTop: 'var(--space-sm)' }}>
        <button type="button" className="btn btn--primary" onClick={onEdit}>
          Edit plan
        </button>
        <button type="button" className="btn btn--secondary" onClick={() => dispatch({ type: 'setAllocationPaused', paused: !rule.paused })}>
          {rule.paused ? 'Resume' : 'Pause'}
        </button>
        <button type="button" className="btn btn--ghost" aria-pressed={rule.skipNext} onClick={() => dispatch({ type: 'skipNextAllocation' })}>
          {rule.skipNext ? 'Skipping next ✓' : 'Skip next'}
        </button>
      </div>
    </section>
  );
}

function ActivityCard({ onOpenTransactions }: { onOpenTransactions: () => void }) {
  const { state } = useStore();

  // §29/§30 — one compact card: latest runs, then the running total.
  const runs = new Map<number, Txn[]>();
  for (const t of state.txns) {
    if (t.smart?.engine !== 'allocation') continue;
    const list = runs.get(t.day) ?? [];
    list.push(t);
    runs.set(t.day, list);
  }
  const history = [...runs.entries()].sort((a, b) => b[0] - a[0]).slice(0, 2);
  const yearAllocated = state.txns
    .filter((t) => t.smart?.engine === 'allocation' && t.status === 'booked')
    .reduce((a, t) => a + -t.amount, 0);

  return (
    <section className="card" aria-label="Allocation activity">
      <div className="flex items-center justify-between" style={{ marginBottom: 'var(--space-xs)' }}>
        <h2 className="section-title m-0">Activity</h2>
        <button type="button" className="btn btn--ghost" onClick={onOpenTransactions}>
          All transactions
        </button>
      </div>
      {history.map(([day, txns]) => {
        const ok = txns.filter((t) => t.status === 'booked');
        const failed = txns.filter((t) => t.status === 'failed');
        const total = ok.reduce((a, t) => a + -t.amount, 0);
        return (
          <button key={day} type="button" className="flex items-baseline justify-between" style={{ width: '100%', padding: 'var(--space-2xs) 0', minHeight: 'var(--space-xl)' }} onClick={onOpenTransactions}>
            <span className="caption" style={{ color: 'var(--color-text-primary)' }}>
              {shortDate(day)} · {ok.length} destination{ok.length === 1 ? '' : 's'}
              {failed.length > 0 && <span style={{ color: 'var(--color-text-warning)' }}> · {failed.length} not completed</span>}
            </span>
            <span className="amount caption" style={{ fontWeight: 'var(--font-weight-semibold)', color: 'var(--color-text-primary)' }}>{money(total, 'CHF', 0)}</span>
          </button>
        );
      })}
      {history.length === 0 && <p className="caption m-0">Nothing yet. The first runs a business day after your salary.</p>}
      <p className="caption m-0" style={{ marginTop: 'var(--space-xs)', borderTop: '1px solid var(--color-border-subtle)', paddingTop: 'var(--space-xs)' }}>
        Put to work so far: <strong className="amount">{money(yearAllocated, 'CHF', 0)}</strong>
      </p>
    </section>
  );
}

/* ------------------------------------------------------------------ */
/* Edit mode — §32                                                     */
/* ------------------------------------------------------------------ */

function PlanEditor({ onDone }: { onDone: () => void }) {
  const { state, dispatch, forecast } = useStore();
  const rule = state.allocation;
  const buffer = rule.bufferMode === 'ai' ? forecast.buffer : rule.manualBuffer;
  const estTotal = Math.min(Math.max(0, state.accounts.everyday + CLIENT.salaryNet - buffer), rule.maxPerSalary);
  const splitTotal = rule.splits.reduce((a, s) => a + s.percent, 0);
  const remainder = 100 - splitTotal;

  const setSplit = (i: number, percent: number) => {
    const splits: AllocationSplit[] = rule.splits.map((s, j) => (j === i ? { ...s, percent } : s));
    dispatch({ type: 'setSplits', splits });
  };

  return (
    <>
      <div className="flex items-center justify-between">
        <h2 className="m-0" style={{ fontSize: 'var(--font-size-heading)', fontWeight: 'var(--font-weight-bold)' }}>Edit plan</h2>
        <button type="button" className="btn btn--primary" onClick={onDone}>
          Done
        </button>
      </div>
      <p className="caption m-0" style={{ marginTop: 'calc(-1 * var(--space-sm))' }}>
        Changes count from your next salary.
      </p>

      <section className="card" aria-label="Split the excess">
        <h3 className="section-title m-0" style={{ marginBottom: 'var(--space-xs)' }}>Split the excess</h3>
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
          Left in Banking: <strong className="amount">{remainder}%</strong>
          {remainder < 0 && ' — splits cannot exceed 100%'}
        </p>
      </section>

      <section className="card" aria-label="Cash Safety Buffer">
        <h3 className="section-title m-0" style={{ marginBottom: 'var(--space-xs)' }}>Cash Safety Buffer</h3>
        <p className="m-0 amount" style={{ fontSize: 'var(--font-size-title)', fontWeight: 'var(--font-weight-bold)' }}>{money(buffer)}</p>
        <p className="caption m-0">
          {rule.bufferMode === 'ai'
            ? `Recommended from your recent Banking activity (range ${money(forecast.bufferLow, 'CHF', 0)}–${money(forecast.bufferHigh, 'CHF', 0)}). Smart Liquidity only allocates money above this amount.`
            : 'Your number. Nothing below it ever moves.'}
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

      <section className="card" aria-label="Execution preference">
        <h3 className="section-title m-0" style={{ marginBottom: 'var(--space-sm)' }}>Execution</h3>
        <div className="flex flex-col" style={{ gap: 'var(--space-xs)' }} role="radiogroup" aria-label="Execution preference">
          <button type="button" className="choice-row" role="radio" aria-checked={rule.mode === 'automatic'} onClick={() => dispatch({ type: 'setAllocationMode', mode: 'automatic' })}>
            <span className="choice-row__dot" aria-hidden="true" />
            <span>
              <span className="block" style={{ fontWeight: 'var(--font-weight-medium)' }}>Automatic</span>
              <span className="caption block">It just happens when your salary lands. You're told every time.</span>
            </span>
          </button>
          <button type="button" className="choice-row" role="radio" aria-checked={rule.mode === 'review'} onClick={() => dispatch({ type: 'setAllocationMode', mode: 'review' })}>
            <span className="choice-row__dot" aria-hidden="true" />
            <span>
              <span className="block" style={{ fontWeight: 'var(--font-weight-medium)' }}>Review before allocation</span>
              <span className="caption block">We prepare it, you approve it. No approval, no movement.</span>
            </span>
          </button>
        </div>
      </section>

      <section className="card" aria-label="Guardrails">
        <h3 className="section-title m-0" style={{ marginBottom: 'var(--space-xs)' }}>Guardrails</h3>
        <label className="block" style={{ marginBottom: 'var(--space-sm)' }}>
          <span className="caption">
            Maximum per salary: <strong className="amount">{money(rule.maxPerSalary, 'CHF', 0)}</strong>
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
            <span className="caption block">More than ±{rule.variancePct}% off your usual salary? Ask me first.</span>
          </span>
          <Toggle checked={rule.askOnVariance} onChange={(v) => dispatch({ type: 'setAskOnVariance', value: v })} label="Ask first on unusual salary" />
        </label>
        <p className="caption m-0" style={{ marginTop: 'var(--space-sm)' }}>
          Below {money(rule.minAllocation, 'CHF', 0)}, nothing moves. An allocation can never push your balance negative.
        </p>
      </section>
    </>
  );
}
