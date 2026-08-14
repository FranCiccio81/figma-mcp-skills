/**
 * Card management — sub-level of the Bank tab.
 * The Elite debit card with block/unblock one tap away, payment limits,
 * details on demand (masked by default), and wallet rows. Frozen state is
 * visible on the card itself, never colour alone.
 */
import { useState } from 'react';
import { money } from '../../lib/format';
import { CLIENT } from '../../data/mockLedger';
import { useStore } from '../../state/store';
import { Toggle } from '../../components/ui';

export function BankCardVisual({ variant, frozen }: { variant: 'mini' | 'hero'; frozen?: boolean }) {
  return (
    <span className={`bank-card bank-card--${variant} ${frozen ? 'bank-card--frozen' : ''}`} aria-hidden="true">
      <span className="bank-card__brand">Swissquote</span>
      <span className="bank-card__chip" />
      <span className="bank-card__number">{variant === 'hero' ? '•••• •••• •••• 1234' : '•••• 1234'}</span>
      <span className="bank-card__scheme">
        <span />
        <span />
      </span>
    </span>
  );
}

export function CardManagement() {
  const { card, setCard, nav } = useStore();
  const [detailsRevealed, setDetailsRevealed] = useState(false);
  const [copied, setCopied] = useState(false);

  return (
    <div className="screen">
      <BankCardVisual variant="hero" frozen={card.frozen} />
      <div className="text-center">
        <p className="m-0" style={{ fontWeight: 'var(--font-weight-semibold)' }}>Elite card •••• 1234</p>
        <p className="caption m-0">
          Swiss Debit Mastercard · {card.frozen ? 'blocked — payments are declined' : 'active'}
        </p>
      </div>

      <button
        type="button"
        className={`btn ${card.frozen ? 'btn--primary' : 'btn--secondary'}`}
        onClick={() => setCard({ frozen: !card.frozen })}
      >
        {card.frozen ? 'Unblock card' : 'Block card'}
      </button>
      {card.frozen && (
        <p className="caption m-0 text-center" style={{ marginTop: 'calc(-1 * var(--space-xs))' }}>
          Blocked instantly. Recurring payments already authorised may still complete. Unblock any time.
        </p>
      )}

      <section className="card" aria-label="Payment limits">
        <h2 className="section-title m-0" style={{ marginBottom: 'var(--space-xs)' }}>Payment limits</h2>
        <label className="block" style={{ marginBottom: 'var(--space-sm)' }}>
          <span className="caption">
            Monthly spending limit: <strong className="amount">{money(card.monthlyLimit, 'CHF', 0)}</strong>
          </span>
          <input
            type="range"
            className="slider"
            min={1000}
            max={30000}
            step={500}
            value={card.monthlyLimit}
            onChange={(e) => setCard({ monthlyLimit: Number(e.target.value) })}
            aria-label="Monthly spending limit"
          />
        </label>
        <label className="block">
          <span className="caption">
            Contactless without PIN: <strong className="amount">{money(card.contactlessLimit, 'CHF', 0)}</strong> per payment
          </span>
          <input
            type="range"
            className="slider"
            min={0}
            max={300}
            step={20}
            value={card.contactlessLimit}
            onChange={(e) => setCard({ contactlessLimit: Number(e.target.value) })}
            aria-label="Contactless limit per payment"
          />
        </label>
        <div className="settings-row" style={{ marginTop: 'var(--space-2xs)' }}>
          <span className="flex-1">
            <span className="block" style={{ fontWeight: 'var(--font-weight-medium)' }}>Online payments</span>
            <span className="caption block">Turn off to decline e-commerce payments while keeping the card active in shops.</span>
          </span>
          <Toggle checked={card.onlinePayments} onChange={(v) => setCard({ onlinePayments: v })} label="Online payments" />
        </div>
      </section>

      <section className="card" aria-label="Card details">
        <h2 className="section-title m-0" style={{ marginBottom: 'var(--space-xs)' }}>Card details</h2>
        <div className="settings-row">
          <span className="flex-1">
            <span className="caption block">Card number</span>
            <span className="amount" style={{ fontWeight: 'var(--font-weight-medium)' }}>
              {detailsRevealed ? '5412 7534 9821 1234' : '•••• •••• •••• 1234'}
            </span>
          </span>
          <button
            type="button"
            className="btn btn--ghost"
            onClick={() => {
              if (!detailsRevealed) {
                setDetailsRevealed(true);
              } else {
                setCopied(true);
                setTimeout(() => setCopied(false), 1500);
              }
            }}
          >
            {copied ? 'Copied' : detailsRevealed ? 'Copy' : 'Show'}
          </button>
        </div>
        <div className="settings-row">
          <span className="flex-1">
            <span className="caption block">Expiry · CVV</span>
            <span className="amount" style={{ fontWeight: 'var(--font-weight-medium)' }}>
              {detailsRevealed ? '08/29 · 447' : '••/•• · •••'}
            </span>
          </span>
        </div>
        <div className="settings-row">
          <span className="flex-1">
            <span className="caption block">Cardholder</span>
            <span style={{ fontWeight: 'var(--font-weight-medium)' }}>{CLIENT.name}</span>
          </span>
        </div>
      </section>

      <button type="button" className="btn btn--ghost" style={{ alignSelf: 'flex-start' }} onClick={() => nav.go('pay')}>
        Apple Pay, Google Pay &amp; TWINT →
      </button>
      <button type="button" className="btn btn--ghost" style={{ alignSelf: 'flex-start' }}>
        Replace lost or damaged card
      </button>
    </div>
  );
}
