/**
 * HOME tab — static replica of the production app's wealth overview
 * (values copied from the reference screenshots). Untouched by the
 * Everyday concept except that the Everyday account is reachable from Bank.
 */
import { swissNumber } from '../../lib/format';
import { AmountXL, Delta } from '../../app-shell/shell';

function WealthChart() {
  // Static portfolio-evolution curve in the app's blue-line / soft-fill style.
  const d = 'M0,58 L18,52 L36,55 L54,44 L72,47 L90,38 L108,42 L126,30 L144,34 L162,24 L180,28 L198,18 L216,24 L234,14 L252,20 L270,10 L288,14 L306,6 L324,10 L340,4';
  return (
    <svg viewBox="0 0 340 64" style={{ width: '100%', height: 'auto', display: 'block' }} role="img" aria-label="Performance over the period, rising from 38'750.00 to 45'218.30 CHF">
      <path d={`${d} L340,64 L0,64 Z`} fill="var(--color-chart-fill)" />
      <path d={d} fill="none" stroke="var(--color-chart-line)" strokeWidth="2" />
    </svg>
  );
}

function RangeChips() {
  return (
    <div className="chip-row" role="tablist" aria-label="Time range">
      {['1W', '1M', '6M', '1Y', 'YTD', 'All'].map((r, i) => (
        <button key={r} type="button" role="tab" aria-selected={i === 0} className="chip">
          {r}
        </button>
      ))}
    </div>
  );
}

function ProductCard({
  name,
  amount,
  children,
}: {
  name: string;
  amount: number;
  children?: React.ReactNode;
}) {
  return (
    <section className="card">
      <div className="product-row">
        <span className="flex-1 min-w-0">
          <span className="block" style={{ fontWeight: 'var(--font-weight-semibold)' }}>{name}</span>
        </span>
        <span className="amount" style={{ fontWeight: 'var(--font-weight-bold)' }}>
          {swissNumber(amount)} <span className="caption">CHF</span>
        </span>
        <span className="product-row__chevron" aria-hidden="true">›</span>
      </div>
      {children}
    </section>
  );
}

export function HomeTab() {
  return (
    <div className="screen">
      <div className="flex flex-col items-center" style={{ gap: 'var(--space-2xs)' }}>
        <span className="caption">Total wealth</span>
        <AmountXL value={87_432.65} />
      </div>

      <section className="card">
        <div className="product-row">
          <span className="flex-1 min-w-0">
            <span className="block" style={{ fontWeight: 'var(--font-weight-semibold)' }}>Trading 784521</span>
            <span className="caption">Daily change</span> <Delta pct={3.24} amount={1_418.3} />
          </span>
          <span className="amount" style={{ fontWeight: 'var(--font-weight-bold)' }}>
            45'218.30 <span className="caption">CHF</span>
          </span>
          <span className="product-row__chevron" aria-hidden="true">›</span>
        </div>
        <div className="flex justify-center" style={{ margin: 'var(--space-sm) 0' }}>
          <span className="chip">Absolute performance ▾</span>
        </div>
        <p className="m-0 text-center amount" style={{ fontSize: 'var(--font-size-caption)', fontWeight: 'var(--font-weight-semibold)', color: 'var(--color-text-positive)', marginBottom: 'var(--space-xs)' }}>
          45'218.30 CHF <span className="caption">over the period</span>
        </p>
        <WealthChart />
        <div className="flex justify-between caption amount" style={{ marginBottom: 'var(--space-sm)' }}>
          <span>38'750.00 CHF</span>
          <span>45'218.30 CHF</span>
        </div>
        <RangeChips />
        <dl className="m-0" style={{ marginTop: 'var(--space-sm)' }}>
          <div className="flex justify-between" style={{ padding: 'var(--space-2xs) 0' }}>
            <dt className="caption m-0">Assets</dt>
            <dd className="m-0 amount">15'789.15 CHF</dd>
          </div>
          <div className="flex justify-between" style={{ padding: 'var(--space-2xs) 0' }}>
            <dt className="caption m-0">Buying power</dt>
            <dd className="m-0 amount">15'789.15 CHF</dd>
          </div>
        </dl>
      </section>

      <ProductCard name="Cash account 123456" amount={24_837.5}>
        <div className="flex" style={{ gap: 'var(--space-xs)', marginTop: 'var(--space-sm)' }}>
          {[
            { flag: '🇨🇭', code: 'CHF', value: "18'542.30" },
            { flag: '🇪🇺', code: 'EUR', value: "3'876.40" },
            { flag: '🇺🇸', code: 'USD', value: "2'418.80" },
          ].map((c) => (
            <span key={c.code} className="currency-cell">
              <span className="currency-cell__code">
                <span aria-hidden="true">{c.flag}</span> {c.code}
              </span>
              <span className="currency-cell__value">{c.value}</span>
            </span>
          ))}
        </div>
      </ProductCard>

      <h2 className="section-title m-0">Other products</h2>

      <ProductCard name="Invest Easy 291034" amount={12_384.2}>
        <p className="m-0 caption" style={{ marginTop: 'var(--space-2xs)' }}>
          Performance <Delta pct={0.45} amount={56} />
        </p>
      </ProductCard>

      <ProductCard name="Save Easy 517823" amount={13_568.55} />

      <ProductCard name="3A" amount={42_180.0}>
        <p className="m-0 caption" style={{ marginTop: 'var(--space-2xs)' }}>
          Performance <Delta pct={7.83} amount={3_064} />
        </p>
        <div className="progress" style={{ marginTop: 'var(--space-sm)' }} role="img" aria-label="5'148 of 7'056 CHF annual allowance used">
          <div className="progress__fill" style={{ width: '73%' }} />
        </div>
        <p className="m-0 caption amount" style={{ marginTop: 'var(--space-2xs)' }}>
          <strong style={{ color: 'var(--color-text-primary)' }}>5'148 CHF</strong> / 7'056 Annual allowance
        </p>
      </ProductCard>

      <ProductCard name="Lombard Loan" amount={87_432.65} />
    </div>
  );
}
