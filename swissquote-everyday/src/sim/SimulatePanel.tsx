/**
 * Simulate rig — prototype control, deliberately OUTSIDE the phone frame.
 * Advances time so the full loop is demonstrable (salary → allocation →
 * spending → Auto Cover → transaction with explanation), and forces each
 * §6 failure state.
 */
import { longDate } from '../lib/format';
import { nextSalaryDayAfter } from '../state/forecast';
import { useStore } from '../state/store';
import type { SimFlags } from '../state/types';

const FLAG_LABELS: { flag: keyof SimFlags; label: string }[] = [
  { flag: 'marketClosed', label: 'Market closed' },
  { flag: 'salaryDelayed', label: 'Salary late' },
  { flag: 'salaryMissing', label: 'Salary missing' },
  { flag: 'irregularIncome', label: 'Irregular income (Marc)' },
  { flag: 'sourcesExhausted', label: 'Sources exhausted' },
];

export function SimulatePanel({ onReset }: { onReset: () => void }) {
  const { state, dispatch } = useStore();
  const advance = (n: number) => {
    for (let i = 0; i < n; i += 1) dispatch({ type: 'advanceDay' });
  };
  const daysToAllocation = nextSalaryDayAfter(state.day) + 1 - state.day;

  return (
    <aside className="sim-panel" aria-label="Prototype simulation controls">
      <div className="flex items-baseline justify-between">
        <strong>Simulate</strong>
        <span className="caption">{longDate(state.day)} · day {state.day}</span>
      </div>
      <div className="flex flex-wrap" style={{ gap: 'var(--space-xs)' }}>
        <button type="button" className="btn btn--primary" onClick={() => advance(1)}>+1 day</button>
        <button type="button" className="btn btn--secondary" onClick={() => advance(7)}>+7 days</button>
        <button type="button" className="btn btn--secondary" onClick={() => advance(daysToAllocation)}>
          To salary + allocation
        </button>
        <button type="button" className="btn btn--secondary" onClick={() => dispatch({ type: 'triggerMarginCall' })}>
          Force margin call
        </button>
        <button type="button" className="btn btn--ghost" onClick={onReset}>Reset demo</button>
      </div>
      <div className="flex flex-wrap" style={{ gap: 'var(--space-xs)' }} role="group" aria-label="Failure states">
        {FLAG_LABELS.map(({ flag, label }) => (
          <button
            key={flag}
            type="button"
            className="sim-panel__chip"
            aria-pressed={state.flags[flag]}
            onClick={() => dispatch({ type: 'setFlag', flag, value: !state.flags[flag] })}
          >
            {label}
          </button>
        ))}
      </div>
      <p className="micro m-0">
        The demo loop: turn on a failure state (or none), then advance to salary + allocation and keep pressing
        +1 day — spending draws the balance down until Auto Cover fires and its transaction appears with an
        explanation. In-memory only; Reset restores 14 August 2026.
      </p>
    </aside>
  );
}
