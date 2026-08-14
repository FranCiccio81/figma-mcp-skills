/**
 * TRADE tab — static replica of the production app's watchlist
 * (rows copied from the reference screenshots; logos are initials, no
 * external assets). Untouched by the Everyday concept.
 */

interface Row {
  name: string;
  ticker: string;
  price: string;
  change: string;
  up: boolean;
  bg: string; // token-backed swatch class for the initial dot
  initial: string;
}

const ROWS: Row[] = [
  { name: 'Apple Inc', ticker: 'APPL', price: '184.92', change: '−2.34 (−1.25%)', up: false, bg: 'var(--color-action-primary)', initial: '' },
  { name: 'Nike', ticker: 'NKE', price: '412.85', change: '+5.60 (+1.37%)', up: true, bg: 'var(--color-action-primary)', initial: '✓' },
  { name: 'Mulia Industrindo', ticker: 'MLIA', price: '267.40', change: '+3.15 (+1.19%)', up: true, bg: 'var(--color-dataviz-save)', initial: 'M' },
  { name: 'Target Corporation', ticker: 'TGT', price: "68'245.00", change: '+892.00 (+1.32%)', up: true, bg: 'var(--color-feedback-error)', initial: '◎' },
  { name: 'Vicore Pharma Holding AB', ticker: 'VICO', price: '0.9438', change: '−0.0012 (−0.13%)', up: false, bg: 'var(--color-dataviz-fx)', initial: 'V' },
  { name: 'Malindo Feedmill TBK…', ticker: 'MAIN', price: '532.60', change: '+8.40 (+1.60%)', up: true, bg: 'var(--color-dataviz-credit)', initial: 'M' },
  { name: 'Southern Copper Corpor…', ticker: 'SCCO', price: '78.56', change: '−0.92 (−1.16%)', up: false, bg: 'var(--color-chart-line)', initial: 'S' },
  { name: 'Lancartama Sejati TB…', ticker: 'TAMA', price: '156.30', change: '+1.85 (+1.20%)', up: true, bg: 'var(--color-dataviz-save)', initial: 'L' },
  { name: 'Pantai Indah Kapuk…', ticker: 'PANI', price: "68'245.00", change: '+892.00 (+1.32%)', up: true, bg: 'var(--color-dataviz-trading)', initial: 'P' },
  { name: 'Amazon.com', ticker: 'AMZN', price: '78.56', change: '−0.92 (−1.16%)', up: false, bg: 'var(--color-action-primary)', initial: 'a' },
];

export function TradeTab() {
  return (
    <div className="screen">
      <div className="chip-row" role="tablist" aria-label="Trade sections">
        {['Watchlists', 'Inspiration', 'Markets', 'News'].map((t, i) => (
          <button key={t} type="button" role="tab" aria-selected={i === 0} className="chip">
            {t}
          </button>
        ))}
      </div>

      <div className="flex items-center justify-between">
        <button type="button" className="chip">My favourite ▾</button>
        <span className="flex items-center caption" style={{ gap: 'var(--space-sm)', color: 'var(--color-text-accent)', fontWeight: 'var(--font-weight-semibold)' }}>
          <span>Edit</span>
          <span>↓ Sort</span>
          <span aria-hidden="true">⋮</span>
        </span>
      </div>

      <ul className="m-0 list-none" style={{ padding: 0 }}>
        {ROWS.map((r) => (
          <li key={r.ticker}>
            <button type="button" className="trade-row">
              <span className="logo-dot" style={{ background: r.bg }} aria-hidden="true">
                {r.initial}
              </span>
              <span className="flex-1 min-w-0">
                <span className="block truncate" style={{ fontWeight: 'var(--font-weight-semibold)' }}>{r.name}</span>
                <span className="caption block">{r.ticker}</span>
              </span>
              <span className="text-right">
                <span className="block amount" style={{ fontWeight: 'var(--font-weight-semibold)' }}>
                  {r.price} <span className="caption">USD</span>
                </span>
                <span className={`delta ${r.up ? 'delta--up' : 'delta--down'} amount`}>{r.change}</span>
              </span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
