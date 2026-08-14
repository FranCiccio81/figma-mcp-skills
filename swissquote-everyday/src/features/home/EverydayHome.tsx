/**
 * §5.1 Everyday Home — the account hub.
 * One unambiguous balance (money in the account right now, nothing added),
 * the Buying Power strip beneath it, Smart Liquidity status, forecast teaser,
 * quick actions and recent activity.
 */
import { useState } from 'react';
import { money } from '../../lib/format';
import { CLIENT } from '../../data/mockLedger';
import { AmountXL } from '../../app-shell/shell';
import { AutomationStatusCard } from '../../components/AutomationStatusCard';
import { BuyingPowerBar } from '../../components/BuyingPowerBar';
import { ForecastSparkline } from '../../components/LiquidityForecastChart';
import { Sheet } from '../../components/ui';
import { useStore } from '../../state/store';
import { TxnRow } from '../transactions/TxnRow';

export function EverydayHome() {
  const { state, dispatch, forecast, nav } = useStore();
  const [ibanRevealed, setIbanRevealed] = useState(false);
  const [copied, setCopied] = useState(false);
  const [detailsOpen, setDetailsOpen] = useState(false);

  const recent = [...state.txns].sort((a, b) => b.day - a.day || b.id.localeCompare(a.id)).slice(0, 5);
  const failNotices = state.notices.filter((n) => n.kind === 'error' || n.kind === 'warning').slice(0, 2);

  return (
    <div className="screen">
      {/* Bank-section tabs, as in the production app; Everyday is the Overview. */}
      <div className="chip-row" role="tablist" aria-label="Bank sections">
        {['Overview', 'Save & Invest', 'Credits', 'Insurance'].map((t, i) => (
          <button key={t} type="button" role="tab" aria-selected={i === 0} className="chip">
            {t}
          </button>
        ))}
      </div>

      {/* The one number. Money in the account right now — nothing else added. */}
      <header className="flex flex-col items-center" style={{ gap: 'var(--space-2xs)' }} aria-label="Everyday balance">
        <span className="caption" style={{ fontWeight: 'var(--font-weight-semibold)', color: 'var(--color-text-primary)' }}>
          Everyday
        </span>
        <AmountXL value={state.accounts.everyday} />
        <p className="micro m-0 text-center">Yours, right now</p>
      </header>

      <BuyingPowerBar onOpen={() => nav.setBuyingPowerOpen(true)} />

      <AutomationStatusCard />

      {/* Forecast teaser → AI Budgeting */}
      <button type="button" className="ai-card" onClick={() => nav.go('budgeting')}>
        <span className="flex-1 min-w-0">
          <span className="ai-card__eyebrow" style={{ marginBottom: 'var(--space-2xs)' }}>
            <svg width="12" height="12" viewBox="0 0 12 12" fill="currentColor" aria-hidden="true">
              <path d="M6 0c.5 3.2 2.3 5 5.5 5.5C8.3 6 6.5 7.8 6 11 5.5 7.8 3.7 6 .5 5.5 3.7 5 5.5 3.2 6 0z" />
            </svg>
            AI Budgeting
          </span>
          <span className="block amount" style={{ fontSize: 'var(--font-size-title)', fontWeight: 'var(--font-weight-bold)', lineHeight: 'var(--line-height-tight)' }}>
            {money(forecast.buffer)}
          </span>
          <span className="caption block" style={{ marginTop: 'var(--space-2xs)' }}>
            What you'll likely need before your next salary
          </span>
        </span>
        <ForecastSparkline forecast={forecast} />
        <span className="product-row__chevron" aria-hidden="true">›</span>
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

      {/* Quick actions — app-style circular icon buttons */}
      <nav className="grid grid-cols-4" style={{ gap: 'var(--space-xs)' }} aria-label="Quick actions">
        {[
          {
            label: 'Pay',
            to: 'pay' as const,
            icon: <path d="M11 17V5M5.5 10.5 11 5l5.5 5.5" strokeLinecap="round" strokeLinejoin="round" />,
          },
          {
            label: 'Scan QR-bill',
            to: null,
            icon: (
              <path d="M4 8V4h4M14 4h4v4M18 14v4h-4M8 18H4v-4M4 11h14" strokeLinecap="round" strokeLinejoin="round" />
            ),
          },
          {
            label: 'Move money',
            to: 'autoCover' as const,
            icon: <path d="M4 8h12l-3-3M18 14H6l3 3" strokeLinecap="round" strokeLinejoin="round" />,
          },
          {
            label: 'Card',
            to: 'card' as const,
            icon: (
              <>
                <rect x="3" y="5.5" width="16" height="11" rx="2" />
                <path d="M3 9.5h16" />
              </>
            ),
          },
        ].map((a) => (
          <button
            key={a.label}
            type="button"
            className="quick-action"
            onClick={() => (a.to ? nav.go(a.to) : undefined)}
            aria-disabled={a.to === null}
          >
            <span className="quick-action__icon" aria-hidden="true">
              <svg width="22" height="22" viewBox="0 0 22 22" fill="none" stroke="currentColor" strokeWidth="1.6">
                {a.icon}
              </svg>
            </span>
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

      {/* Account details — the IBAN's home, out of the header (§5.1 revisited) */}
      <button type="button" className="settings-row" style={{ borderBottom: 'none' }} onClick={() => setDetailsOpen(true)}>
        <span className="flex-1">
          <span className="block" style={{ fontWeight: 'var(--font-weight-medium)' }}>Account details</span>
          <span className="caption block amount">IBAN {CLIENT.ibanMasked} · statements</span>
        </span>
        <span className="product-row__chevron" aria-hidden="true">›</span>
      </button>

      {detailsOpen && (
        <Sheet title="Account details" onClose={() => setDetailsOpen(false)}>
          <div className="settings-row">
            <span className="flex-1">
              <span className="caption block">IBAN</span>
              <span className="amount" style={{ fontWeight: 'var(--font-weight-medium)' }}>
                {ibanRevealed ? CLIENT.ibanFull : CLIENT.ibanMasked}
              </span>
            </span>
            <button
              type="button"
              className="btn btn--ghost"
              onClick={() => {
                if (!ibanRevealed) {
                  setIbanRevealed(true);
                } else {
                  setCopied(true);
                  setTimeout(() => setCopied(false), 1500);
                }
              }}
            >
              {copied ? 'Copied' : ibanRevealed ? 'Copy' : 'Show'}
            </button>
          </div>
          <div className="settings-row">
            <span className="flex-1">
              <span className="caption block">Account holder</span>
              <span style={{ fontWeight: 'var(--font-weight-medium)' }}>{CLIENT.name}</span>
            </span>
          </div>
          <div className="settings-row">
            <span className="flex-1">
              <span className="caption block">Deposit protection</span>
              <span>Protected by esisuisse up to CHF 100'000 ⟨TO CONFIRM⟩</span>
            </span>
          </div>
          <div className="settings-row">
            <span className="flex-1" style={{ fontWeight: 'var(--font-weight-medium)' }}>Statements</span>
            <span className="product-row__chevron" aria-hidden="true">›</span>
          </div>
        </Sheet>
      )}
    </div>
  );
}
