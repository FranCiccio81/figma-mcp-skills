/**
 * BuyingPowerBar — new component introduced by this concept (§7).
 *
 * A single horizontal segmented bar: own funds left of a hard structural
 * divider, Lombard credit right of it. Never renders a summed total that
 * includes credit (§9.1). Segments are distinguishable by label and pattern
 * as well as hue; each carries a text amount for screen readers.
 */
import { money, swissNumber } from '../lib/format';
import { useStore } from '../state/store';

const SWATCH_CLASS: Record<string, string> = {
  cash: 'bp-bar__segment--cash',
  fx: 'bp-bar__segment--fx',
  save: 'bp-bar__segment--save',
  trading: 'bp-bar__segment--trading',
  credit: 'bp-bar__segment--credit',
};

export function BuyingPowerBar({ onOpen }: { onOpen: () => void }) {
  const { buyingPower } = useStore();
  const { ownSegments, credit, ownTotal } = buyingPower;
  const scale = ownTotal + credit.amountChf;

  return (
    <button type="button" className="bp-bar" onClick={onOpen} aria-haspopup="dialog">
      <span className="sr-only">
        Buying power breakdown.{' '}
        {ownSegments.map((s) => `${s.label} ${money(s.amountChf)}. `).join('')}
        Own funds total {money(ownTotal)}. Separately: {credit.label} {money(credit.amountChf)},
        borrowing against your portfolio. Opens details.
      </span>
      <span className="bp-bar__track" aria-hidden="true">
        {ownSegments.map((s, i) => (
          <span
            key={s.key}
            className={`bp-bar__segment ${SWATCH_CLASS[s.key]}`}
            style={{
              width: `${Math.max(1.5, (s.amountChf / scale) * 100)}%`,
              animationDelay: `calc(var(--motion-duration-fast) * ${i})`,
            }}
          />
        ))}
        <span className="bp-bar__divider" />
        <span
          className={`bp-bar__segment ${SWATCH_CLASS.credit}`}
          style={{
            width: `${Math.max(1.5, (credit.amountChf / scale) * 100)}%`,
            animationDelay: `calc(var(--motion-duration-fast) * ${ownSegments.length})`,
          }}
        />
      </span>
      <span className="flex items-baseline justify-between" style={{ marginTop: 'var(--space-2xs)' }} aria-hidden="true">
        <span className="caption">
          Own funds <strong className="amount" style={{ color: 'var(--color-text-primary)' }}>CHF {swissNumber(ownTotal)}</strong>
        </span>
        <span className="caption">
          Lombard <span className="amount">CHF {swissNumber(credit.amountChf)}</span> · credit
        </span>
      </span>
      <span className="bp-legend" style={{ marginTop: 'var(--space-2xs)' }} aria-hidden="true">
        {[...ownSegments, credit].map((s) => (
          <span key={s.key} className="bp-legend__item">
            <span className={`bp-legend__swatch ${SWATCH_CLASS[s.key]}`} />
            {s.label}
          </span>
        ))}
      </span>
    </button>
  );
}
