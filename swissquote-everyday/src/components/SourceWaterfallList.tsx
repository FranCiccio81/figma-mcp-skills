/**
 * SourceWaterfallList — the client's Auto Cover funding order.
 *
 * Each row shows what the source can actually contribute right now (after
 * open orders, penalty-free limits and the client's own reserves), so the
 * order is never a promise the product can't keep. Lombard is pinned last
 * and marked as credit; Invest Easy appears only to say it is never sold.
 */
import { money } from '../lib/format';
import { LOMBARD_RATE_PA } from '../data/mockLedger';
import { SOURCE_LABELS, sourceCoverCapacity } from '../state/liquidityEngine';
import { useStore } from '../state/store';

export function SourceWaterfallList({ editing = false }: { editing?: boolean }) {
  const { state, dispatch } = useStore();
  const cfg = state.autoCover;

  return (
    <ol className="m-0 flex flex-col list-none" style={{ gap: 'var(--space-xs)', padding: 0 }} aria-label="Auto Cover sources, in order">
      {cfg.sources.map((src, i) => {
        const { amount, reason } = sourceCoverCapacity(state, src.source);
        return (
          <li key={src.source} className="waterfall-row" style={{ opacity: src.enabled ? 1 : 0.6 }}>
            <span className="waterfall-row__rank" aria-hidden="true">{i + 1}</span>
            <span className="flex-1 min-w-0">
              <span className="block" style={{ fontWeight: 'var(--font-weight-medium)' }}>
                {SOURCE_LABELS[src.source]}
              </span>
              <span className="caption block">
                {src.enabled ? (amount > 0 ? `${money(amount, 'CHF', 0)} eligible` : reason) : 'Not used'}
                {src.enabled && amount > 0 && ` · ${money(src.monthlyLimit - src.usedThisMonth, 'CHF', 0)} left this month`}
              </span>
            </span>
            {editing ? (
              <span className="flex" style={{ gap: 'var(--space-2xs)' }}>
                <button
                  type="button"
                  className="waterfall-row__move"
                  aria-label={`Move ${SOURCE_LABELS[src.source]} earlier`}
                  disabled={i === 0}
                  onClick={() => dispatch({ type: 'moveWaterfallSource', index: i, direction: -1 })}
                >
                  ↑
                </button>
                <button
                  type="button"
                  className="waterfall-row__move"
                  aria-label={`Move ${SOURCE_LABELS[src.source]} later`}
                  disabled={i === cfg.sources.length - 1}
                  onClick={() => dispatch({ type: 'moveWaterfallSource', index: i, direction: 1 })}
                >
                  ↓
                </button>
                <button
                  type="button"
                  className="waterfall-row__move"
                  aria-label={`${src.enabled ? 'Remove' : 'Add'} ${SOURCE_LABELS[src.source]}`}
                  onClick={() => dispatch({ type: 'toggleCoverSource', source: src.source, enabled: !src.enabled })}
                >
                  {src.enabled ? '−' : '+'}
                </button>
              </span>
            ) : (
              <span className="amount caption" style={{ fontWeight: 'var(--font-weight-semibold)', color: 'var(--color-text-primary)' }}>
                {src.enabled && amount > 0 ? money(amount, 'CHF', 0) : '—'}
              </span>
            )}
          </li>
        );
      })}

      <li className="waterfall-row waterfall-row--pinned" aria-label="Lombard credit, always last">
        <span className="waterfall-row__rank" aria-hidden="true">{cfg.sources.length + 1}</span>
        <span className="flex-1 min-w-0">
          <span className="block" style={{ fontWeight: 'var(--font-weight-medium)' }}>
            Lombard <span className="class-chip class-chip--credit">Credit</span>
          </span>
          <span className="caption block">
            {cfg.lombardEnabled && cfg.lombardAcknowledged
              ? `Up to ${money(cfg.lombardPerCoverMax, 'CHF', 0)} per cover · ${LOMBARD_RATE_PA}% p.a.`
              : 'Off — automatic borrowing is never on by default'}
          </span>
        </span>
      </li>

      <li className="waterfall-row waterfall-row--pinned" aria-label="Investments are never sold">
        <span className="waterfall-row__rank" aria-hidden="true">—</span>
        <span className="flex-1 min-w-0">
          <span className="block" style={{ fontWeight: 'var(--font-weight-medium)' }}>Invest Easy &amp; Saving Plan</span>
          <span className="caption block">Never used — Auto Cover doesn't sell your investments.</span>
        </span>
      </li>
    </ol>
  );
}
