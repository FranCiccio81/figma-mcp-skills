/**
 * PLAN tab — the destination behind the fifth bottom-tab item.
 *
 * Deliberately plain: it exists so both Home concepts have a real place to
 * send "Plan", and it reads the same engine state as everything else. It is
 * not part of the Home redesign and is not styled to compete with it.
 */
import { swissNumber } from '../../lib/format';
import {
  INVEST_EASY_PERF_PCT,
  PILLAR_3A,
  PILLAR_3A_ALLOWANCE,
  PILLAR_3A_PAID_IN,
  PILLAR_3A_PERF_PCT,
} from '../../data/mockLedger';
import { AmountXL, Delta } from '../../app-shell/shell';
import { useStore } from '../../state/store';

export function PlanTab() {
  const { state, nav } = useStore();
  const a = state.accounts;
  const total = a.saveEasy + a.investEasy + a.savingPlan + PILLAR_3A;
  const room = Math.max(0, PILLAR_3A_ALLOWANCE - PILLAR_3A_PAID_IN);

  const investEasyGain = a.investEasy - a.investEasy / (1 + INVEST_EASY_PERF_PCT / 100);
  const pillarGain = PILLAR_3A - PILLAR_3A / (1 + PILLAR_3A_PERF_PCT / 100);

  const rows: { name: string; amount: number; note?: React.ReactNode }[] = [
    {
      name: 'Invest Easy 291034',
      amount: a.investEasy,
      note: <>Performance <Delta pct={INVEST_EASY_PERF_PCT} amount={investEasyGain} /></>,
    },
    { name: 'Save Easy 517823', amount: a.saveEasy, note: 'Interest paid yearly' },
    { name: 'Global ETF Saving Plan', amount: a.savingPlan, note: 'Funded monthly by your Smart Salary Allocation' },
  ];

  return (
    <div className="screen">
      <div className="flex flex-col items-center" style={{ gap: 'var(--space-2xs)' }}>
        <span className="caption">What you're building</span>
        <AmountXL value={total} />
        <span className="micro">Saving, investing and retirement</span>
      </div>

      <section className="card">
        <div className="product-row">
          <span className="flex-1 min-w-0">
            <span className="block" style={{ fontWeight: 'var(--font-weight-semibold)' }}>3A</span>
            <span className="caption">Performance</span> <Delta pct={PILLAR_3A_PERF_PCT} amount={pillarGain} />
          </span>
          <span className="amount" style={{ fontWeight: 'var(--font-weight-bold)' }}>
            {swissNumber(PILLAR_3A)} <span className="caption">CHF</span>
          </span>
        </div>
        <div
          className="progress"
          style={{ marginTop: 'var(--space-sm)' }}
          role="img"
          aria-label={`${swissNumber(PILLAR_3A_PAID_IN, 0)} of ${swissNumber(PILLAR_3A_ALLOWANCE, 0)} CHF annual allowance paid in`}
        >
          <div className="progress__fill" style={{ width: `${(PILLAR_3A_PAID_IN / PILLAR_3A_ALLOWANCE) * 100}%` }} />
        </div>
        <p className="m-0 caption amount" style={{ marginTop: 'var(--space-2xs)' }}>
          <strong style={{ color: 'var(--color-text-primary)' }}>{swissNumber(PILLAR_3A_PAID_IN, 0)} CHF</strong> /{' '}
          {swissNumber(PILLAR_3A_ALLOWANCE, 0)} annual allowance
        </p>
        {room > 0 && (
          <p className="m-0 caption" style={{ marginTop: 'var(--space-2xs)' }}>
            {swissNumber(room, 0)} CHF still open this year.
          </p>
        )}
      </section>

      {rows.map((r) => (
        <section key={r.name} className="card">
          <div className="product-row">
            <span className="flex-1 min-w-0">
              <span className="block" style={{ fontWeight: 'var(--font-weight-semibold)' }}>{r.name}</span>
              {r.note && <span className="caption block">{r.note}</span>}
            </span>
            <span className="amount" style={{ fontWeight: 'var(--font-weight-bold)' }}>
              {swissNumber(r.amount)} <span className="caption">CHF</span>
            </span>
          </div>
        </section>
      ))}

      <button type="button" className="settings-row" style={{ borderBottom: 'none' }} onClick={() => nav.go('allocation')}>
        <span className="flex-1">
          <span className="block" style={{ fontWeight: 'var(--font-weight-medium)' }}>Smart Salary Allocation</span>
          <span className="caption block">What funds all of this, every month</span>
        </span>
        <span className="product-row__chevron" aria-hidden="true">›</span>
      </button>
    </div>
  );
}
