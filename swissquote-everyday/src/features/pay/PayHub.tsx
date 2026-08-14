/**
 * Pay — every way money leaves Everyday, in one place.
 *
 * Grouped by how the client thinks about paying: sending money, paying with
 * the card or phone, and spending in another currency. Wallets live here
 * (not on the card screen) because adding Apple Pay is a payment setup task.
 */
import { money, swissNumber } from '../../lib/format';
import { FX } from '../../data/mockLedger';
import { useStore } from '../../state/store';

interface Row {
  label: string;
  hint: string;
  meta?: string;
}

function Group({ title, rows, footer }: { title: string; rows: Row[]; footer?: string }) {
  return (
    <section className="card" aria-label={title}>
      <h2 className="section-title m-0" style={{ marginBottom: 'var(--space-2xs)' }}>{title}</h2>
      {rows.map((r) => (
        <button key={r.label} type="button" className="settings-row" style={{ width: '100%' }}>
          <span className="flex-1 min-w-0">
            <span className="block" style={{ fontWeight: 'var(--font-weight-medium)' }}>{r.label}</span>
            <span className="caption block">{r.hint}</span>
          </span>
          {r.meta && <span className="caption">{r.meta}</span>}
          <span className="product-row__chevron" aria-hidden="true">›</span>
        </button>
      ))}
      {footer && <p className="micro m-0" style={{ marginTop: 'var(--space-xs)' }}>{footer}</p>}
    </section>
  );
}

export function PayHub() {
  const { state, card } = useStore();
  const a = state.accounts;

  return (
    <div className="screen">
      <p className="caption m-0">
        Paying from Everyday · {money(a.everyday)} available
      </p>

      <Group
        title="Send money"
        rows={[
          { label: 'Standard payment', hint: 'Arrives in 1–2 business days', meta: 'Free' },
          { label: 'Instant payment', hint: 'Arrives in seconds, 24/7' },
          { label: 'Scan a QR-bill', hint: 'Pay a Swiss QR invoice with your camera' },
          { label: 'Standing orders', hint: 'Rent, savings and other repeating payments', meta: '2 active' },
          { label: 'eBill', hint: 'Invoices delivered straight to the app', meta: '1 pending' },
        ]}
      />

      <Group
        title="Card & phone"
        rows={[
          {
            label: 'Debit card payments',
            hint: card.frozen ? 'Card blocked — payments are declined' : 'Elite card •••• 1234',
            meta: card.frozen ? 'Blocked' : 'Active',
          },
          { label: 'Apple Pay', hint: 'Pay with your iPhone or Watch', meta: 'Add' },
          { label: 'Google Pay', hint: 'Pay with your Android phone', meta: 'Add' },
          { label: 'TWINT', hint: 'Swiss mobile payments and P2P', meta: 'Connected' },
        ]}
      />

      <Group
        title="Spending in other currencies"
        rows={[
          { label: 'EUR', hint: 'Spend directly from your EUR balance', meta: `${swissNumber(a.eurWallet, 0)} EUR` },
          { label: 'USD', hint: 'Spend directly from your USD balance', meta: `${swissNumber(a.usdWallet, 0)} USD` },
          {
            label: 'Auto FX',
            hint: 'Convert automatically when you pay in a currency you don’t hold',
            meta: 'Off',
          },
        ]}
        footer={`Conversions use the applicable rate plus a spread of about ${FX.spreadPct}%, always shown before you pay.`}
      />
    </div>
  );
}
