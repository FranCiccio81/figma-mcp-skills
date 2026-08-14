/**
 * AutomationStatusCard — new component introduced by this concept (§7).
 * Current Smart Liquidity state in plain language, with Review and a pause
 * control always one tap away (§5.3: an automation the client cannot stop
 * instantly is a design failure).
 */
import { money, shortDate } from '../lib/format';
import { nextSalaryDayAfter } from '../state/forecast';
import { useStore } from '../state/store';
import { StatusPill } from './ui';

export function AutomationStatusCard() {
  const { state, dispatch, forecast, nav } = useStore();
  const { allocation, autoCover, status } = state;
  const paused = allocation.paused;

  let line: string;
  if (paused) {
    line = 'All automations are paused. Nothing moves until you resume.';
  } else if (status === 'autoCoverFailed') {
    line = 'Auto Cover could not top up your balance — action needed below.';
  } else if (state.pendingSettlements.length > 0) {
    const p = state.pendingSettlements[0];
    line = `${money(p.amount)} from a sale settles on ${shortDate(p.settlesOnDay)} — not spendable until then.`;
  } else if (allocation.scheduledForDay !== null) {
    line = `Allocation runs on ${shortDate(allocation.scheduledForDay)}, one business day after your salary.`;
  } else if (allocation.enabled) {
    const salaryDay = nextSalaryDayAfter(state.day);
    const buffer = allocation.bufferMode === 'ai' ? forecast.buffer : allocation.manualBuffer;
    const surplusHint = Math.max(0, 8_400 - buffer);
    line = `Next allocation after salary on ${shortDate(salaryDay)}: roughly ${money(Math.round((surplusHint * (allocation.splits[0]?.percent ?? 0)) / 100 / 10) * 10)} to ${allocation.splits[0]?.label ?? 'Invest Easy'} and ${money(Math.round((surplusHint * (allocation.splits[1]?.percent ?? 0)) / 100 / 10) * 10)} to ${allocation.splits[1]?.label ?? 'Save Easy'}.`;
  } else {
    line = 'Smart Salary Allocation is off. Your salary stays in Everyday.';
  }

  return (
    <section className="card" aria-label="Smart Liquidity status">
      <div className="flex items-center justify-between" style={{ marginBottom: 'var(--space-xs)' }}>
        <span className="section-title">Smart Liquidity</span>
        <StatusPill status={status} />
      </div>
      <p className="m-0" style={{ marginBottom: 'var(--space-sm)' }}>{line}</p>
      {autoCover.enabled && !paused && (
        <p className="caption m-0" style={{ marginBottom: 'var(--space-sm)' }}>
          Auto Cover is on — below {money(autoCover.minBalance)}, Everyday tops up from your sources.
        </p>
      )}
      <div className="flex items-center" style={{ gap: 'var(--space-xs)' }}>
        <button type="button" className="btn btn--secondary" onClick={() => nav.go('allocation')}>
          Review
        </button>
        <button
          type="button"
          className="btn btn--ghost"
          onClick={() => dispatch({ type: paused ? 'resumeAll' : 'pauseAll' })}
        >
          {paused ? 'Resume automations' : 'Pause all'}
        </button>
      </div>
    </section>
  );
}
