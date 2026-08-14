/**
 * HOME tab — the wealth overview, in the production app's layout.
 *
 * Products that also exist in the Bank tab (Everyday cash and its wallets,
 * Save Easy, Invest Easy, the Saving Plan, Lombard) read from the same engine
 * state, so a balance never disagrees with itself across the app. Total wealth
 * is the roll-up of what is listed below it, minus what is borrowed.
 */
import type { ReactNode } from 'react';
import { swissNumber } from '../../lib/format';
import {
  FX,
  INVEST_EASY_PERF_PCT,
  LOMBARD_LIMIT,
  PILLAR_3A,
  PILLAR_3A_ALLOWANCE,
  PILLAR_3A_PAID_IN,
  PILLAR_3A_PERF_PCT,
  TRADING_DAY_CHANGE_PCT,
  TRADING_ORDERS_RESERVED,
  TRADING_PERIOD_GAIN,
  TRADING_POSITIONS,
} from '../../data/mockLedger';
import { AmountXL, Delta } from '../../app-shell/shell';
import { useStore } from '../../state/store';

function WealthChart() {
  const d = 'M0,58 L18,52 L36,55 L54,44 L72,47 L90,38 L108,42 L126,30 L144,34 L162,24 L180,28 L198,18 L216,24 L234,14 L252,20 L270,10 L288,14 L306,6 L324,10 L340,4';
  return (
    <svg viewBox="0 0 340 64" style={{ width: '100%', height: 'auto', display: 'block' }} role="img" aria-label="Trading account performance over the past week, rising steadily">
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
  onOpen,
  children,
}: {
  name: string;
  amount: number;
  onOpen?: () => void;
  children?: ReactNode;
}) {
  return (
    <section className="card">
      <button type="button" className="product-row" onClick={onOpen} style={{ cursor: onOpen ? 'pointer' : 'default' }}>
        <span className="flex-1 min-w-0">
          <span className="block" style={{ fontWeight: 'var(--font-weight-semibold)' }}>{name}</span>
        </span>
        <span className="amount" style={{ fontWeight: 'var(--font-weight-bold)' }}>
          {swissNumber(amount)} <span className="caption">CHF</span>
        </span>
        <span className="product-row__chevron" aria-hidden="true">›</span>
      </button>
      {children}
    </section>
  );
}

export function HomeTab() {
  const { state, nav } = useStore();
  const a = state.accounts;

  // Everyday is a multi-currency account: CHF balance plus the FX wallets.
  const eurChf = a.eurWallet * FX.eurToChf;
  const usdChf = a.usdWallet * FX.usdToChf;
  const cashAccount = a.everyday + eurChf + usdChf;

  // Trading = securities held + uninvested cash; part of that cash is committed.
  const tradingTotal = TRADING_POSITIONS + a.tradingCash;
  const tradingBuyingPower = a.tradingCash - TRADING_ORDERS_RESERVED;
  const tradingDayChange = tradingTotal - tradingTotal / (1 + TRADING_DAY_CHANGE_PCT / 100);
  const periodStart = tradingTotal - TRADING_PERIOD_GAIN;

  const totalWealth =
    cashAccount + tradingTotal + a.investEasy + a.saveEasy + a.savingPlan + PILLAR_3A - a.lombardDrawn;

  const investEasyGain = a.investEasy - a.investEasy / (1 + INVEST_EASY_PERF_PCT / 100);
  const pillar3aGain = PILLAR_3A - PILLAR_3A / (1 + PILLAR_3A_PERF_PCT / 100);

  return (
    <div className="screen">
      <div className="flex flex-col items-center" style={{ gap: 'var(--space-2xs)' }}>
        <span className="caption">Total wealth</span>
        <AmountXL value={totalWealth} />
        <span className="micro">Across all your Swissquote products{a.lombardDrawn > 0 ? ', after Lombard borrowing' : ''}</span>
      </div>

      <section className="card">
        <div className="product-row">
          <span className="flex-1 min-w-0">
            <span className="block" style={{ fontWeight: 'var(--font-weight-semibold)' }}>Trading 784521</span>
            <span className="caption">Daily change</span>{' '}
            <Delta pct={TRADING_DAY_CHANGE_PCT} amount={tradingDayChange} />
          </span>
          <span className="amount" style={{ fontWeight: 'var(--font-weight-bold)' }}>
            {swissNumber(tradingTotal)} <span className="caption">CHF</span>
          </span>
          <span className="product-row__chevron" aria-hidden="true">›</span>
        </div>
        <div className="flex justify-center" style={{ margin: 'var(--space-sm) 0' }}>
          <span className="chip">Absolute performance ▾</span>
        </div>
        <p className="m-0 text-center amount" style={{ fontSize: 'var(--font-size-caption)', fontWeight: 'var(--font-weight-semibold)', color: 'var(--color-text-positive)', marginBottom: 'var(--space-xs)' }}>
          + {swissNumber(TRADING_PERIOD_GAIN)} CHF <span className="caption">over the period</span>
        </p>
        <WealthChart />
        <div className="flex justify-between caption amount" style={{ marginBottom: 'var(--space-sm)' }}>
          <span>{swissNumber(periodStart)} CHF</span>
          <span>{swissNumber(tradingTotal)} CHF</span>
        </div>
        <RangeChips />
        <dl className="m-0" style={{ marginTop: 'var(--space-sm)' }}>
          <div className="flex justify-between" style={{ padding: 'var(--space-2xs) 0' }}>
            <dt className="caption m-0">Securities</dt>
            <dd className="m-0 amount">{swissNumber(TRADING_POSITIONS)} CHF</dd>
          </div>
          <div className="flex justify-between" style={{ padding: 'var(--space-2xs) 0' }}>
            <dt className="caption m-0">Buying power</dt>
            <dd className="m-0 amount">{swissNumber(tradingBuyingPower)} CHF</dd>
          </div>
          <p className="micro m-0">
            {swissNumber(TRADING_ORDERS_RESERVED, 0)} CHF of your cash is reserved for open orders.
          </p>
        </dl>
      </section>

      {/* The same account the Bank tab calls Everyday. */}
      <ProductCard name="Everyday 123456" amount={cashAccount} onOpen={() => nav.setTab('bank')}>
        <div className="flex" style={{ gap: 'var(--space-xs)', marginTop: 'var(--space-sm)' }}>
          {[
            { flag: '🇨🇭', code: 'CHF', value: swissNumber(a.everyday) },
            { flag: '🇪🇺', code: 'EUR', value: swissNumber(a.eurWallet) },
            { flag: '🇺🇸', code: 'USD', value: swissNumber(a.usdWallet) },
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

      <ProductCard name="Invest Easy 291034" amount={a.investEasy}>
        <p className="m-0 caption" style={{ marginTop: 'var(--space-2xs)' }}>
          Performance <Delta pct={INVEST_EASY_PERF_PCT} amount={investEasyGain} />
        </p>
      </ProductCard>

      <ProductCard name="Save Easy 517823" amount={a.saveEasy} />

      <ProductCard name="Global ETF Saving Plan" amount={a.savingPlan}>
        <p className="m-0 caption" style={{ marginTop: 'var(--space-2xs)' }}>
          Funded monthly by your Smart Salary Allocation
        </p>
      </ProductCard>

      <ProductCard name="3A" amount={PILLAR_3A}>
        <p className="m-0 caption" style={{ marginTop: 'var(--space-2xs)' }}>
          Performance <Delta pct={PILLAR_3A_PERF_PCT} amount={pillar3aGain} />
        </p>
        <div
          className="progress"
          style={{ marginTop: 'var(--space-sm)' }}
          role="img"
          aria-label={`${swissNumber(PILLAR_3A_PAID_IN, 0)} of ${swissNumber(PILLAR_3A_ALLOWANCE, 0)} CHF annual allowance paid in`}
        >
          <div className="progress__fill" style={{ width: `${(PILLAR_3A_PAID_IN / PILLAR_3A_ALLOWANCE) * 100}%` }} />
        </div>
        <p className="m-0 caption amount" style={{ marginTop: 'var(--space-2xs)' }}>
          <strong style={{ color: 'var(--color-text-primary)' }}>{swissNumber(PILLAR_3A_PAID_IN, 0)} CHF</strong> /{' '}
          {swissNumber(PILLAR_3A_ALLOWANCE, 0)} Annual allowance
        </p>
      </ProductCard>

      <ProductCard name="Lombard Loan" amount={a.lombardDrawn}>
        <p className="m-0 caption" style={{ marginTop: 'var(--space-2xs)' }}>
          {a.lombardDrawn > 0 ? 'Borrowed' : 'Nothing borrowed'} · {swissNumber(a.lombardAvailable, 0)} CHF currently
          drawable of a {swissNumber(LOMBARD_LIMIT, 0)} CHF limit
        </p>
      </ProductCard>
    </div>
  );
}
