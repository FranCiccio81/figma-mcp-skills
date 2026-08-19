/**
 * Simulate rig — prototype control, deliberately OUTSIDE the phone frame.
 * Advances time so the full loop is demonstrable (salary → allocation →
 * spending → Auto Cover → transaction with explanation), and forces each
 * §6 failure state.
 */
import { longDate } from '../lib/format';
import { nextSalaryDayAfter } from '../state/forecast';
import { useStore, type HomeScenario, type HomeVariant } from '../state/store';
import type { SimFlags } from '../state/types';

/** Home redesign — development-only switch. Not a production surface. */
const HOME_VARIANTS: { value: HomeVariant; label: string }[] = [
  { value: 'A', label: 'A · Universe-first' },
  { value: 'B', label: 'B · Smart Today' },
  { value: 'C', label: 'C · Good to see you' },
];

const HOME_SCENARIOS: { value: HomeScenario; label: string }[] = [
  { value: 'full', label: 'Multi-product' },
  { value: 'tradeOnly', label: 'Trade only' },
  { value: 'bankOnly', label: 'Bank only' },
  { value: 'quiet', label: 'Nothing today' },
  { value: 'loading', label: 'Loading' },
  { value: 'aiError', label: 'AI unavailable' },
];

const FLAG_LABELS: { flag: keyof SimFlags; label: string }[] = [
  { flag: 'marketClosed', label: 'Market closed' },
  { flag: 'salaryDelayed', label: 'Salary late' },
  { flag: 'salaryMissing', label: 'Salary missing' },
  { flag: 'irregularIncome', label: 'Irregular income (Marc)' },
  { flag: 'sourcesExhausted', label: 'Sources exhausted' },
  { flag: 'savingPlanOutage', label: 'Saving Plan outage' },
  { flag: 'tradingUnavailable', label: 'Trading unavailable' },
];

export function SimulatePanel({ onReset }: { onReset: () => void }) {
  const { state, dispatch, nav, home } = useStore();
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
        <button
          type="button"
          className="btn btn--secondary"
          onClick={() =>
            dispatch({
              type: 'simulateLargePayment',
              label: 'Kitchen renovation — Cuisines Léman SA',
              amount: Math.round((state.accounts.everyday + 9_000) / 100) * 100,
            })
          }
        >
          Payment bigger than balance
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
      {/* ---- Home redesign: variant + states. Development only. ---- */}
      <div className="sim-panel__block">
        <div className="flex items-baseline justify-between">
          <strong>Home concept</strong>
          <button type="button" className="btn btn--ghost" onClick={() => nav.setTab('home')}>
            Go to Home
          </button>
        </div>
        <div className="flex flex-wrap" style={{ gap: 'var(--space-xs)' }} role="group" aria-label="Home variant">
          {HOME_VARIANTS.map((v) => (
            <button
              key={v.value}
              type="button"
              className="sim-panel__chip"
              aria-pressed={home.variant === v.value}
              onClick={() => home.setVariant(v.value)}
            >
              {v.label}
            </button>
          ))}
        </div>
        <div className="flex flex-wrap" style={{ gap: 'var(--space-xs)' }} role="group" aria-label="Home state">
          {HOME_SCENARIOS.map((s) => (
            <button
              key={s.value}
              type="button"
              className="sim-panel__chip"
              aria-pressed={home.scenario === s.value}
              onClick={() => home.setScenario(s.value)}
            >
              {s.label}
            </button>
          ))}
          <button
            type="button"
            className="sim-panel__chip"
            aria-pressed={home.balancesHidden}
            onClick={() => home.setBalancesHidden(!home.balancesHidden)}
          >
            Balances hidden
          </button>
        </div>
      </div>

      <p className="micro m-0">
        The demo loop: turn on a failure state (or none), then advance to salary + allocation and keep pressing
        +1 day — spending draws the balance down until Auto Cover fires and its transaction appears with an
        explanation. In-memory only; Reset restores 14 August 2026.
      </p>
    </aside>
  );
}
