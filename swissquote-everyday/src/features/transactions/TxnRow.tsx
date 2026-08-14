/** Transaction row — §5.6. Smart Liquidity movements get a distinct inline treatment. */
import { shortDate, signedMoney } from '../../lib/format';
import type { Txn, TxnCategory } from '../../state/types';

const CATEGORY_ICONS: Record<TxnCategory, string> = {
  housing: '⌂',
  insurance: '✚',
  groceries: '🛒',
  dining: '🍽',
  transport: '🚆',
  shopping: '🛍',
  health: '✚',
  leisure: '✈',
  subscription: '↻',
  salary: '💼',
  transfer: '⇄',
  'smart-liquidity': '⚙',
};

export function TxnRow({ txn, onOpen }: { txn: Txn; onOpen: () => void }) {
  const smart = txn.category === 'smart-liquidity';
  return (
    <li>
      <button
        type="button"
        className={`txn-row ${smart ? 'txn-row--smart' : ''} ${txn.status === 'failed' ? 'txn-row--failed' : ''}`}
        onClick={onOpen}
      >
        <span className="txn-row__icon" aria-hidden="true">{CATEGORY_ICONS[txn.category]}</span>
        <span className="flex-1 min-w-0">
          <span className="txn-row__label block truncate" style={{ fontWeight: smart ? 'var(--font-weight-semibold)' : 'var(--font-weight-medium)' }}>
            {txn.smart?.title ?? txn.label}
          </span>
          <span className="caption block">
            {shortDate(txn.day)}
            {txn.status === 'pending' && ' · pending settlement'}
            {txn.status === 'failed' && ' · failed'}
          </span>
        </span>
        {txn.currency !== 'CHF' && <span className="currency-badge">{txn.currency}</span>}
        <span
          className="amount"
          style={{
            fontWeight: 'var(--font-weight-semibold)',
            color:
              txn.status === 'failed'
                ? 'var(--color-text-error)'
                : txn.amount > 0
                  ? 'var(--color-text-positive)'
                  : 'var(--color-text-primary)',
          }}
        >
          {signedMoney(txn.amount, txn.currency)}
        </span>
      </button>
    </li>
  );
}
