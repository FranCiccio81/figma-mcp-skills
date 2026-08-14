/**
 * §5.1 Everyday Home — the account hub.
 * One unambiguous balance (money in the account right now, nothing added),
 * the Buying Power strip beneath it, Smart Liquidity status, forecast teaser,
 * quick actions and recent activity.
 */
import { useState } from 'react';
import { money, swissNumber } from '../../lib/format';
import { CLIENT } from '../../data/mockLedger';
import { AutomationStatusCard } from '../../components/AutomationStatusCard';
import { BuyingPowerBar } from '../../components/BuyingPowerBar';
import { ForecastSparkline } from '../../components/LiquidityForecastChart';
import { useStore } from '../../state/store';
import { TxnRow } from '../transactions/TxnRow';

export function EverydayHome() {
  const { state, dispatch, forecast, nav } = useStore();
  const [ibanRevealed, setIbanRevealed] = useState(false);
  const [copied, setCopied] = useState(false);

  const recent = [...state.txns].sort((a, b) => b.day - a.day || b.id.localeCompare(a.id)).slice(0, 5);
  const failNotices = state.notices.filter((n) => n.kind === 'error' || n.kind === 'warning').slice(0, 2);

  return (
    <div className="screen">
      <header>
        <div className="flex items-center justify-between">
          <h1 className="m-0" style={{ fontSize: 'var(--font-size-heading)', fontWeight: 'var(--font-weight-semibold)' }}>
            Everyday
          </h1>
          <span className="sim-panel__chip" aria-label="Account currency">CHF ▾</span>
        </div>
        <button
          type="button"
          className="caption amount"
          style={{ minHeight: 'var(--size-touch-target)', display: 'inline-flex', alignItems: 'center' }}
          onClick={() => {
            if (!ibanRevealed) {
              setIbanRevealed(true);
            } else {
              setCopied(true);
              setTimeout(() => setCopied(false), 1500);
            }
          }}
          aria-label={ibanRevealed ? 'Copy IBAN' : 'Reveal IBAN'}
        >
          {ibanRevealed ? CLIENT.ibanFull : CLIENT.ibanMasked}
          <span style={{ marginLeft: 'var(--space-xs)', color: 'var(--color-text-link)' }}>
            {copied ? 'Copied' : ibanRevealed ? 'Copy' : 'Show'}
          </span>
        </button>
      </header>

      {/* The one number. Money in the account right now — nothing else added. */}
      <section aria-label="Everyday balance">
        <p className="m-0 caption">Balance</p>
        <p
          className="m-0 amount"
          style={{ fontSize: 'var(--font-size-display)', fontWeight: 'var(--font-weight-bold)', lineHeight: 'var(--line-height-tight)' }}
        >
          CHF {swissNumber(state.accounts.everyday)}
        </p>
        <p className="micro m-0">
          In the account now · protected by esisuisse up to CHF 100'000 ⟨TO CONFIRM⟩
        </p>
      </section>

      <BuyingPowerBar onOpen={() => nav.setBuyingPowerOpen(true)} />

      <AutomationStatusCard />

      {/* Forecast teaser → AI Budgeting */}
      <button type="button" className="card flex items-center" style={{ gap: 'var(--space-sm)', width: '100%' }} onClick={() => nav.go('budgeting')}>
        <span className="flex-1 min-w-0">
          <span className="block" style={{ fontWeight: 'var(--font-weight-medium)' }}>
            You'll likely need {money(forecast.buffer)} before your next salary.
          </span>
          <span className="caption block">Based on your last 3 months · tap for the forecast</span>
        </span>
        <ForecastSparkline forecast={forecast} />
      </button>

      {failNotices.length > 0 && (
        <div className="flex flex-col" style={{ gap: 'var(--space-xs)' }} aria-label="Notifications">
          {failNotices.map((n) => (
            <div key={n.id} className={`notice notice--${n.kind === 'error' ? 'error' : 'warning'}`}>
              <div className="flex items-start justify-between" style={{ gap: 'var(--space-xs)' }}>
                <strong>{n.title}</strong>
                <button type="button" className="btn btn--ghost" style={{ minHeight: 'var(--space-xl)' }} onClick={() => dispatch({ type: 'dismissNotice', id: n.id })}>
                  Dismiss
                </button>
              </div>
              <p className="m-0 caption" style={{ color: 'var(--color-text-primary)' }}>{n.body}</p>
              {n.kind === 'error' && n.shortfall !== undefined && (
                <div className="flex" style={{ gap: 'var(--space-xs)', marginTop: 'var(--space-xs)' }}>
                  <button
                    type="button"
                    className="btn btn--secondary"
                    onClick={() => dispatch({ type: 'manualTransferIn', amount: Math.ceil(n.shortfall! / 50) * 50 })}
                  >
                    Transfer in {money(Math.ceil(n.shortfall / 50) * 50)}
                  </button>
                  <button type="button" className="btn btn--ghost" onClick={() => nav.go('autoCover')}>
                    Sell positions
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Quick actions */}
      <nav className="grid grid-cols-4" style={{ gap: 'var(--space-xs)' }} aria-label="Quick actions">
        {[
          { label: 'Pay', to: null },
          { label: 'Scan QR-bill', to: null },
          { label: 'Move money', to: 'autoCover' as const },
          { label: 'Card', to: null },
        ].map((a) => (
          <button
            key={a.label}
            type="button"
            className="card--subtle card flex flex-col items-center justify-center"
            style={{ minHeight: 'var(--space-2xl)', padding: 'var(--space-xs)', fontSize: 'var(--font-size-caption)', fontWeight: 'var(--font-weight-medium)', textAlign: 'center' }}
            onClick={() => (a.to ? nav.go(a.to) : undefined)}
            aria-disabled={a.to === null}
          >
            {a.label}
          </button>
        ))}
      </nav>

      <section aria-label="Recent activity">
        <div className="flex items-center justify-between">
          <h2 className="section-title m-0">Recent activity</h2>
          <button type="button" className="btn btn--ghost" onClick={() => nav.go('transactions')}>
            All transactions
          </button>
        </div>
        <ul className="m-0 list-none" style={{ padding: 0 }}>
          {recent.map((t) => (
            <TxnRow key={t.id} txn={t} onOpen={() => { nav.go('transactions'); nav.openTxn(t.id); }} />
          ))}
        </ul>
      </section>
    </div>
  );
}
