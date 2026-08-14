/** §5.6 Transactions list + detail. A Smart Liquidity movement explains which
 * rule fired, why, the balance before and after, and links to edit the rule. */
import { longDate, money, shortDate, signedMoney } from '../../lib/format';
import { SOURCE_LABELS } from '../../state/liquidityEngine';
import { useStore } from '../../state/store';
import { TxnRow } from './TxnRow';

export function Transactions() {
  const { state, nav } = useStore();
  const detail = nav.txnDetailId ? state.txns.find((t) => t.id === nav.txnDetailId) : null;

  if (detail) {
    const smart = detail.smart;
    return (
      <div className="screen">
        <section className="card">
          <p className="caption m-0">{longDate(detail.day)}</p>
          <p className="m-0" style={{ fontSize: 'var(--font-size-heading)', fontWeight: 'var(--font-weight-semibold)' }}>
            {smart?.title ?? detail.label}
          </p>
          <p className="m-0 amount" style={{ fontSize: 'var(--font-size-display)', fontWeight: 'var(--font-weight-bold)' }}>
            {signedMoney(detail.amount, detail.currency)}
          </p>
          <p className="caption m-0">
            {detail.status === 'pending' && 'Pending — settles T+2. Not spendable until settled.'}
            {detail.status === 'failed' && 'Failed — the amount was not paid.'}
            {detail.status === 'booked' && 'Booked'}
          </p>
        </section>

        {smart && (
          <section className="card" aria-label="Why this happened">
            <h2 className="section-title m-0" style={{ marginBottom: 'var(--space-xs)' }}>
              Why this happened
            </h2>
            <p className="m-0" style={{ marginBottom: 'var(--space-sm)' }}>{smart.reason}</p>
            <dl className="m-0 grid grid-cols-2" style={{ gap: 'var(--space-2xs) var(--space-sm)', fontSize: 'var(--font-size-caption)' }}>
              <dt className="caption m-0">Rule</dt>
              <dd className="m-0">{smart.engine === 'autoCover' ? 'Auto Cover' : 'Smart Salary Allocation'}</dd>
              {smart.source && (
                <>
                  <dt className="caption m-0">From</dt>
                  <dd className="m-0">{SOURCE_LABELS[smart.source]}</dd>
                </>
              )}
              {smart.destination && (
                <>
                  <dt className="caption m-0">To</dt>
                  <dd className="m-0">{SOURCE_LABELS[smart.destination]}</dd>
                </>
              )}
              <dt className="caption m-0">Balance before</dt>
              <dd className="m-0 amount">{money(smart.balanceBefore)}</dd>
              <dt className="caption m-0">Balance after</dt>
              <dd className="m-0 amount">{money(smart.balanceAfter)}</dd>
              {smart.settlesOnDay !== undefined && detail.status === 'pending' && (
                <>
                  <dt className="caption m-0">Settles</dt>
                  <dd className="m-0">{shortDate(smart.settlesOnDay)}</dd>
                </>
              )}
              {smart.fxCostChf !== undefined && (
                <>
                  <dt className="caption m-0">Conversion cost</dt>
                  <dd className="m-0 amount">{money(smart.fxCostChf)}</dd>
                </>
              )}
              {smart.interestRatePa !== undefined && (
                <>
                  <dt className="caption m-0">Interest</dt>
                  <dd className="m-0">{smart.interestRatePa}% p.a.</dd>
                </>
              )}
            </dl>
            <button
              type="button"
              className="btn btn--secondary"
              style={{ marginTop: 'var(--space-sm)' }}
              onClick={() => nav.go(smart.engine === 'autoCover' ? 'autoCover' : 'allocation')}
            >
              Edit the rule that caused this
            </button>
          </section>
        )}
      </div>
    );
  }

  const txns = [...state.txns].sort((a, b) => b.day - a.day || b.id.localeCompare(a.id)).slice(0, 60);
  return (
    <div className="screen">
      <ul className="m-0 list-none" style={{ padding: 0 }}>
        {txns.map((t) => (
          <TxnRow key={t.id} txn={t} onOpen={() => nav.openTxn(t.id)} />
        ))}
      </ul>
    </div>
  );
}
