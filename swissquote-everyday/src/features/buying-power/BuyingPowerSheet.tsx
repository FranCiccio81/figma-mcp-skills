/**
 * §5.2 Buying Power detail — bottom sheet.
 * Every segment with time-to-availability and cost. Lombard is visually
 * separated, opt-in, and always carries the risk line. Own funds and credit
 * are never summed (§9.1).
 */
import { money, swissNumber } from '../../lib/format';
import { LOMBARD_RATE_PA } from '../../data/mockLedger';
import { Sheet } from '../../components/ui';
import { useStore } from '../../state/store';

const SWATCH_CLASS: Record<string, string> = {
  cash: 'bp-bar__segment--cash',
  fx: 'bp-bar__segment--fx',
  save: 'bp-bar__segment--save',
  trading: 'bp-bar__segment--trading',
  credit: 'bp-bar__segment--credit',
};

export function BuyingPowerSheet() {
  const { state, buyingPower, nav } = useStore();
  if (!nav.buyingPowerOpen) return null;
  const { ownSegments, credit, ownTotal } = buyingPower;

  return (
    <Sheet title="Buying power" onClose={() => nav.setBuyingPowerOpen(false)}>
      <p className="caption" style={{ marginTop: 0 }}>
        What you could spend, source by source. Own money first — credit is listed separately and never added in.
      </p>

      <ul className="m-0 list-none" style={{ padding: 0 }}>
        {ownSegments.map((s) => (
          <li key={s.key} className="bp-row">
            <span className={`bp-row__swatch ${SWATCH_CLASS[s.key]}`} aria-hidden="true" />
            <span className="flex-1 min-w-0">
              <span className="block" style={{ fontWeight: 'var(--font-weight-medium)' }}>{s.label}</span>
              <span className="caption block">
                {s.availability}
                {s.cost ? ` · ${s.cost}` : ''}
                {s.indicative ? ' · indicative, before conversion' : ''}
              </span>
            </span>
            <span className="amount" style={{ fontWeight: 'var(--font-weight-semibold)' }}>
              CHF {swissNumber(s.amountChf)}
            </span>
          </li>
        ))}
        <li className="bp-row" style={{ borderBottom: 'none' }}>
          <span className="bp-row__swatch" aria-hidden="true" />
          <span className="flex-1" style={{ fontWeight: 'var(--font-weight-semibold)' }}>Own funds — available</span>
          <span className="amount" style={{ fontWeight: 'var(--font-weight-bold)' }}>CHF {swissNumber(ownTotal)}</span>
        </li>
      </ul>

      <div className="card card--subtle" style={{ marginTop: 'var(--space-xs)' }}>
        <div className="flex items-start justify-between" style={{ gap: 'var(--space-sm)' }}>
          <span className="flex-1">
            <span className="block" style={{ fontWeight: 'var(--font-weight-medium)' }}>Invest Easy — sell to spend</span>
            <span className="caption block">T+2 settlement · positions are sold · not part of buying power until settled</span>
          </span>
          <span className="amount">CHF {swissNumber(state.accounts.investEasy)}</span>
        </div>
        <div className="flex items-start justify-between" style={{ gap: 'var(--space-sm)', marginTop: 'var(--space-sm)' }}>
          <span className="flex-1">
            <span className="block" style={{ fontWeight: 'var(--font-weight-medium)' }}>Global ETF Saving Plan</span>
            <span className="caption block">Invested via your plan · product withdrawal conditions apply</span>
          </span>
          <span className="amount">CHF {swissNumber(state.accounts.savingPlan)}</span>
        </div>
      </div>

      <div className="lombard-block" style={{ marginTop: 'var(--space-md)' }}>
        <div className="flex items-start justify-between" style={{ gap: 'var(--space-sm)' }}>
          <span className="flex-1">
            <span className="block" style={{ fontWeight: 'var(--font-weight-semibold)' }}>
              Lombard available <span className="micro">· credit, not your money</span>
            </span>
            <span className="caption block">
              {credit.availability} · {LOMBARD_RATE_PA}% p.a. ⟨rate TO CONFIRM⟩
            </span>
          </span>
          <span className="amount" style={{ fontWeight: 'var(--font-weight-semibold)' }}>
            CHF {swissNumber(credit.amountChf)}
          </span>
        </div>
        <p className="caption m-0" style={{ marginTop: 'var(--space-xs)', color: 'var(--color-text-primary)' }}>
          Borrowing against your portfolio. If markets fall, Swissquote may require you to add funds or may sell
          positions.
        </p>
        {state.accounts.lombardDrawn > 0 && (
          <p className="caption m-0 amount" style={{ marginTop: 'var(--space-2xs)' }}>
            Currently drawn: {money(state.accounts.lombardDrawn)}
          </p>
        )}
        <a className="link caption" href="#lombard" onClick={(e) => e.preventDefault()}>
          Learn how Lombard works
        </a>
      </div>
    </Sheet>
  );
}
