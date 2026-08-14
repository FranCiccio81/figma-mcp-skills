/**
 * Pay — every way money leaves Everyday, in one place.
 *
 * Grouped by how the client thinks about paying: sending money, paying with
 * the card or phone, and spending in another currency. Wallets live here
 * (not on the card screen) because adding Apple Pay is a payment setup task.
 */
import { money, swissNumber } from '../../lib/format';
import { FX, RECURRING_DEBITS } from '../../data/mockLedger';
import { useStore } from '../../state/store';

/** Which recurring debits are paid how — so the counts here match the ledger. */
const STANDING_ORDER_LABELS = ['Rent — Régie du Léman', 'Country Club Lausanne'];
const EBILL_LABELS = ['Sanitas — health insurance', 'Swisscom'];

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

  const standingOrders = RECURRING_DEBITS.filter((r) => STANDING_ORDER_LABELS.includes(r.label));
  const ebills = RECURRING_DEBITS.filter((r) => EBILL_LABELS.includes(r.label));
  const standingTotal = standingOrders.reduce((s, r) => s + r.amount, 0);
  const ebillTotal = ebills.reduce((s, r) => s + r.amount, 0);

  return (
    <div className="screen">
      <p className="caption m-0">
        From Everyday · {money(a.everyday)} ready
      </p>

      <Group
        title="Send money"
        rows={[
          { label: 'Standard payment', hint: 'There in 1–2 business days', meta: 'Free' },
          { label: 'Instant payment', hint: 'There in seconds. Any day, any hour.' },
          { label: 'Scan a QR-bill', hint: 'Point your camera at a Swiss QR invoice' },
          {
            label: 'Standing orders',
            hint: `${standingOrders.map((r) => r.label.split(' — ')[0]).join(', ')} · ${money(standingTotal, 'CHF', 0)}/month`,
            meta: `${standingOrders.length} active`,
          },
          {
            label: 'eBill',
            hint: `${ebills.map((r) => r.label.split(' — ')[0]).join(', ')} · ${money(ebillTotal, 'CHF', 0)}/month`,
            meta: `${ebills.length} due`,
          },
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
          { label: 'Apple Pay', hint: 'Your iPhone or Watch', meta: 'Add' },
          { label: 'Google Pay', hint: 'Your Android phone', meta: 'Add' },
          { label: 'TWINT', hint: 'Swiss mobile payments, and paying people back', meta: 'Connected' },
        ]}
      />

      <Group
        title="Spending in other currencies"
        rows={[
          { label: 'EUR', hint: 'Spend it as it is. No conversion.', meta: `${swissNumber(a.eurWallet, 0)} EUR` },
          { label: 'USD', hint: 'Spend it as it is. No conversion.', meta: `${swissNumber(a.usdWallet, 0)} USD` },
          {
            label: 'Auto FX',
            hint: "Converts for you when you pay in a currency you don't hold",
            meta: 'Off',
          },
        ]}
        footer={`Conversions carry a spread of about ${FX.spreadPct}%. You see it before you pay, not after.`}
      />
    </div>
  );
}
