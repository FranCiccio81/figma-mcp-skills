/**
 * SourceWaterfallList — new component introduced by this concept (§7).
 * Client-ordered Auto Cover sources. Reordering uses accessible up/down
 * controls (the pointer-drag affordance of the final product maps to these).
 * Lombard is pinned last, opted into separately, behind an explicit risk
 * acknowledgement.
 */
import { money } from '../lib/format';
import { FX, LOMBARD_RATE_PA } from '../data/mockLedger';
import { SOURCE_LABELS } from '../state/liquidityEngine';
import { useStore } from '../state/store';
import type { MoneySource } from '../state/types';

function sourceMeta(state: ReturnType<typeof useStore>['state'], source: MoneySource): { availability: string; cost: string | null; balance: string } {
  const a = state.accounts;
  switch (source) {
    case 'saveEasy':
      return { availability: 'Instant', cost: null, balance: money(a.saveEasy) };
    case 'tradingCash':
      return {
        availability: state.flags.marketClosed ? 'Unavailable — market closed' : 'Same day',
        cost: null,
        balance: money(a.tradingCash),
      };
    case 'investEasy':
      return { availability: 'T+2 settlement (positions are sold)', cost: null, balance: money(a.investEasy) };
    case 'eurWallet':
      return { availability: 'Instant', cost: `FX spread ≈ ${FX.spreadPct}%`, balance: money(a.eurWallet, 'EUR') };
    case 'usdWallet':
      return { availability: 'Instant', cost: `FX spread ≈ ${FX.spreadPct}%`, balance: money(a.usdWallet, 'USD') };
    default:
      return { availability: 'Instant', cost: `${LOMBARD_RATE_PA}% p.a. interest`, balance: money(a.lombardAvailable) };
  }
}

export function SourceWaterfallList() {
  const { state, dispatch } = useStore();
  const { waterfall } = state.autoCover;

  return (
    <ol className="m-0 flex flex-col list-none" style={{ gap: 'var(--space-xs)', padding: 0 }} aria-label="Auto Cover sources, in order">
      {waterfall.map((source, i) => {
        const meta = sourceMeta(state, source);
        return (
          <li key={source} className="waterfall-row">
            <span className="waterfall-row__rank" aria-hidden="true">{i + 1}</span>
            <span className="flex-1 min-w-0">
              <span className="block" style={{ fontWeight: 'var(--font-weight-medium)' }}>
                {SOURCE_LABELS[source]} <span className="caption amount">· {meta.balance}</span>
              </span>
              <span className="caption block">
                {meta.availability}
                {meta.cost ? ` · ${meta.cost}` : ' · no cost'}
              </span>
            </span>
            <span className="flex" style={{ gap: 'var(--space-2xs)' }}>
              <button
                type="button"
                className="waterfall-row__move"
                aria-label={`Move ${SOURCE_LABELS[source]} earlier`}
                disabled={i === 0}
                onClick={() => dispatch({ type: 'moveWaterfallSource', index: i, direction: -1 })}
              >
                ↑
              </button>
              <button
                type="button"
                className="waterfall-row__move"
                aria-label={`Move ${SOURCE_LABELS[source]} later`}
                disabled={i === waterfall.length - 1}
                onClick={() => dispatch({ type: 'moveWaterfallSource', index: i, direction: 1 })}
              >
                ↓
              </button>
            </span>
          </li>
        );
      })}
      <li className="waterfall-row waterfall-row--pinned" aria-label="Lombard credit, always last">
        <span className="waterfall-row__rank" aria-hidden="true">{waterfall.length + 1}</span>
        <span className="flex-1 min-w-0">
          <span className="block" style={{ fontWeight: 'var(--font-weight-medium)' }}>
            Lombard credit <span className="caption amount">· {money(state.accounts.lombardAvailable)}</span>
          </span>
          <span className="caption block">
            Always last · {LOMBARD_RATE_PA}% p.a. · {state.autoCover.lombardEnabled ? 'opted in' : 'off — separate opt-in below'}
          </span>
        </span>
      </li>
    </ol>
  );
}
