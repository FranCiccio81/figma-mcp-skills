/**
 * Everyday Buying Power — detail sheet.
 *
 * The spec's hierarchy (§82), in order: available now → your accessible cash →
 * protected / flexible → Lombard credit → maximum. Own cash and credit are
 * never merged (§6.1), reservations are shown where they are deducted
 * (§18–§22), and invested money is listed as explicitly NOT included (§6.3).
 */
import { useState } from 'react';
import { money, swissNumber } from '../../lib/format';
import { LOMBARD_LIMIT, LOMBARD_RATE_PA } from '../../data/mockLedger';
import { Sheet, Toggle } from '../../components/ui';
import { useStore } from '../../state/store';
import type { BuyingPowerSegment } from '../../state/store';

const CLASS_LABEL: Record<BuyingPowerSegment['liquidityClass'], string> = {
  now: 'Now',
  transferable: 'Transferable',
  conditional: 'Conditions',
  credit: 'Credit',
};

function SourceRow({ segment }: { segment: BuyingPowerSegment }) {
  const [open, setOpen] = useState(false);
  const hasDetail = (segment.reserved?.length ?? 0) > 0 || segment.cost !== null;
  return (
    <li style={{ borderBottom: '1px solid var(--color-border-subtle)' }}>
      <button
        type="button"
        className="flex items-center"
        style={{ gap: 'var(--space-sm)', width: '100%', padding: 'var(--space-sm) 0', minHeight: 'var(--size-touch-target)' }}
        onClick={() => hasDetail && setOpen((v) => !v)}
        aria-expanded={hasDetail ? open : undefined}
      >
        <span className="flex-1 min-w-0">
          <span className="block" style={{ fontWeight: 'var(--font-weight-medium)' }}>{segment.label}</span>
          <span className="caption block">
            {segment.availability}
            {segment.indicative && ' · indicative'}
          </span>
        </span>
        <span className={`class-chip class-chip--${segment.liquidityClass}`}>{CLASS_LABEL[segment.liquidityClass]}</span>
        <span className="amount" style={{ fontWeight: 'var(--font-weight-semibold)' }}>
          {swissNumber(segment.amountChf, 0)}
        </span>
        {hasDetail && <span className="product-row__chevron" aria-hidden="true">{open ? '⌄' : '›'}</span>}
      </button>
      {open && (
        <div style={{ paddingBottom: 'var(--space-sm)' }}>
          {segment.reserved?.map((r) => (
            <div key={r.label} className="flex justify-between caption" style={{ padding: 'var(--space-2xs) 0' }}>
              <span>− {r.label}</span>
              <span className="amount">{swissNumber(r.amount, 0)}</span>
            </div>
          ))}
          {segment.cost && <p className="caption m-0">{segment.cost}</p>}
          {segment.liquidityClass === 'transferable' && (
            <button type="button" className="btn btn--secondary" style={{ marginTop: 'var(--space-xs)' }}>
              Move to Everyday
            </button>
          )}
        </div>
      )}
    </li>
  );
}

export function BuyingPowerSheet() {
  const { buyingPower: bp, nav, bpSettings, setBpSettings, state } = useStore();
  if (!nav.buyingPowerOpen) return null;

  return (
    <Sheet title="Everyday Buying Power" onClose={() => nav.setBuyingPowerOpen(false)}>
      <p className="caption" style={{ marginTop: 0 }}>
        Your money, wherever it sits. Credit kept separate — because it isn't yours.
      </p>

      {/* 1 & 2 — own cash, source by source */}
      <h3 className="section-title" style={{ margin: '0 0 var(--space-2xs)' }}>Your cash</h3>
      <ul className="m-0 list-none" style={{ padding: 0 }}>
        {bp.ownSegments.map((s) => (
          <SourceRow key={s.key} segment={s} />
        ))}
        <li className="flex items-baseline justify-between" style={{ padding: 'var(--space-sm) 0' }}>
          <span style={{ fontWeight: 'var(--font-weight-semibold)' }}>Own accessible cash</span>
          <span className="amount" style={{ fontWeight: 'var(--font-weight-bold)' }}>CHF {swissNumber(bp.ownTotal, 0)}</span>
        </li>
      </ul>

      {/* 3 — protected vs flexible, identified rather than deducted invisibly */}
      <div className="card card--subtle" style={{ marginBottom: 'var(--space-md)' }}>
        <div className="flex justify-between caption" style={{ marginBottom: 'var(--space-2xs)' }}>
          <span>Protected for upcoming needs (AI Budgeting)</span>
          <span className="amount">− {swissNumber(bp.protectedLiquidity, 0)}</span>
        </div>
        <div className="flex justify-between" style={{ fontWeight: 'var(--font-weight-semibold)' }}>
          <span>Flexible cash</span>
          <span className="amount">CHF {swissNumber(bp.flexible, 0)}</span>
        </div>
        <p className="micro m-0" style={{ marginTop: 'var(--space-2xs)' }}>
          Still yours, still reachable. Just spoken for, until your next salary.
        </p>
      </div>

      {/* 4 — credit, clearly a different thing */}
      <div className="lombard-block">
        <div className="flex items-center justify-between" style={{ gap: 'var(--space-sm)' }}>
          <span className="flex-1">
            <span className="block" style={{ fontWeight: 'var(--font-weight-semibold)' }}>Show Lombard credit</span>
            <span className="caption block">Capacity to borrow. Not money you own.</span>
          </span>
          <Toggle
            checked={bpSettings.showLombard}
            onChange={(v) => setBpSettings({ showLombard: v })}
            label="Show Lombard in Buying Power"
          />
        </div>
        {bpSettings.showLombard && (
          <>
            <div className="flex items-baseline justify-between" style={{ marginTop: 'var(--space-sm)' }}>
              <span>Currently drawable</span>
              <span className="amount" style={{ fontWeight: 'var(--font-weight-semibold)' }}>
                up to CHF {swissNumber(bp.credit.amountChf, 0)}
              </span>
            </div>
            <div className="flex justify-between caption">
              <span>Credit limit {money(LOMBARD_LIMIT, 'CHF', 0)} · used {money(state.accounts.lombardDrawn, 'CHF', 0)}</span>
              <span>{LOMBARD_RATE_PA}% p.a.</span>
            </div>
            <p className="caption m-0" style={{ marginTop: 'var(--space-2xs)', color: 'var(--color-text-primary)' }}>
              Borrowing against your portfolio. Capacity moves with the value of your pledged assets. Showing it here
              borrows nothing.
            </p>
          </>
        )}
      </div>

      {/* 5 — the maximum, secondary by design */}
      <div className="flex items-baseline justify-between" style={{ marginTop: 'var(--space-md)' }}>
        <span className="caption">The most you could reach {bpSettings.showLombard && '(cash + credit)'}</span>
        <span className="amount" style={{ fontWeight: 'var(--font-weight-semibold)' }}>CHF {swissNumber(bp.maximum, 0)}</span>
      </div>

      {/* Not included — stated, not hidden */}
      <h3 className="section-title" style={{ margin: 'var(--space-md) 0 var(--space-2xs)' }}>Not included</h3>
      <ul className="m-0 list-none" style={{ padding: 0 }}>
        {bp.notIncluded.map((n) => (
          <li key={n.label} className="flex items-baseline justify-between caption" style={{ padding: 'var(--space-2xs) 0' }}>
            <span>
              {n.label} <span className="micro">· {n.reason}</span>
            </span>
            <span className="amount">{swissNumber(n.amountChf, 0)}</span>
          </li>
        ))}
      </ul>
      <p className="micro m-0" style={{ marginTop: 'var(--space-xs)' }}>
        Invested money isn't cash. We count only what you can actually use.
      </p>
    </Sheet>
  );
}
