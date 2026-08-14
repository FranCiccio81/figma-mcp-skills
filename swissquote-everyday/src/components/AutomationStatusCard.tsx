/**
 * AutomationStatusCard — the Smart Liquidity engine card on the Everyday hub.
 * Dark feature card: the one bold surface on the page. Current state in plain
 * language, next-run figures as stats, Review and Pause one tap away (§5.3).
 */
import { money, roundTo, shortDate, swissNumber } from '../lib/format';
import { CLIENT } from '../data/mockLedger';
import { nextSalaryDayAfter } from '../state/forecast';
import { useStore } from '../state/store';
import { PlanBar } from './PlanBar';
import { StatusPill } from './ui';

export function AutomationStatusCard() {
  const { state, dispatch, forecast, nav } = useStore();
  const { allocation, autoCover, status } = state;
  const paused = allocation.paused;

  const buffer = allocation.bufferMode === 'ai' ? forecast.buffer : allocation.manualBuffer;
  const estTotal = Math.min(
    Math.max(0, state.accounts.everyday + CLIENT.salaryNet - buffer),
    allocation.maxPerSalary,
  );
  const nextRunDay = allocation.scheduledForDay ?? nextSalaryDayAfter(state.day) + 1;

  let line: string;
  let stats: { label: string; value: string }[] | null = null;
  if (paused) {
    line = 'Paused. Nothing moves until you say so.';
  } else if (status === 'autoCoverFailed') {
    line = 'Auto Cover came up short. Your move.';
  } else if (state.pendingAllocation) {
    line = state.pendingAllocation.anomaly
      ? 'This payment looks different. Nothing moves until you check it.'
      : `${money(state.pendingAllocation.total)} ready to go. Your call.`;
  } else if (state.pendingSettlements.length > 0) {
    const p = state.pendingSettlements[0];
    line = `${money(p.amount)} settles ${shortDate(p.settlesOnDay)}. Not spendable before then.`;
  } else if (allocation.enabled) {
    line =
      allocation.scheduledForDay !== null
        ? 'Salary in. Your plan runs tomorrow.'
        : 'Your salary lands. The rest goes to work.';
    stats = [
      { label: 'Next run', value: shortDate(nextRunDay) },
      { label: 'Keep in Banking', value: `≥ ${swissNumber(buffer, 0)}` },
      { label: 'Allocate excess', value: `≈ ${swissNumber(roundTo(estTotal, 50), 0)}` },
    ];
  } else {
    line = 'Allocation is off. Your salary sits still.';
  }
  const destinations = allocation.splits
    .map((s) => `${s.label.replace('Global ETF ', 'ETF ')} ${s.percent}%`)
    .join(' · ');

  return (
    <section className="sl-card" aria-label="Smart Liquidity status">
      <div className="flex items-center justify-between" style={{ marginBottom: 'var(--space-sm)' }}>
        <span className="sl-card__eyebrow">Smart Liquidity</span>
        <StatusPill status={status} />
      </div>
      <p className="m-0" style={{ fontSize: 'var(--font-size-heading)', fontWeight: 'var(--font-weight-medium)', lineHeight: 'var(--line-height-tight)' }}>
        {line}
      </p>
      {stats && (
        <div className="sl-card__stats">
          {stats.map((s) => (
            <div key={s.label} className="sl-card__stat">
              <span className="sl-card__muted block" style={{ fontSize: 'var(--font-size-micro)' }}>{s.label}</span>
              <span className="sl-card__stat-value block">{s.value}</span>
            </div>
          ))}
        </div>
      )}
      {stats && (
        <>
          <div style={{ marginTop: 'var(--space-sm)' }}>
            <PlanBar buffer={buffer} estTotal={estTotal} splits={allocation.splits} />
          </div>
          <p className="sl-card__muted m-0" style={{ marginTop: 'var(--space-xs)' }}>
            {destinations}
          </p>
        </>
      )}
      {autoCover.enabled && !paused && (
        <p className="sl-card__muted m-0" style={{ marginTop: 'var(--space-sm)' }}>
          Auto Cover is on. Short on a payment? We bring your cash back.
        </p>
      )}
      <div className="flex items-center" style={{ gap: 'var(--space-xs)', marginTop: 'var(--space-md)' }}>
        <button type="button" className="btn btn--inverse" onClick={() => nav.go('allocation')}>
          View plan
        </button>
        <button
          type="button"
          className="btn btn--ghost-inverse"
          onClick={() => dispatch({ type: paused ? 'resumeAll' : 'pauseAll' })}
        >
          {paused ? 'Resume automations' : 'Pause all'}
        </button>
      </div>
    </section>
  );
}
