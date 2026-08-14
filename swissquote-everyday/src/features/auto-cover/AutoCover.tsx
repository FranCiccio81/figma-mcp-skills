/**
 * Auto Cover — brings authorised liquidity back to Everyday when a payment
 * needs it. Kept to a glance: status + capacity, the funding order, and
 * recent covers. Rules and limits sit behind "Edit rules".
 *
 * Principles made visible: cash before credit, never sell investments,
 * all-or-nothing cover, and every limit is the client's own (§104).
 */
import { useState } from 'react';
import { money, shortDate, swissNumber } from '../../lib/format';
import { LOMBARD_RATE_PA } from '../../data/mockLedger';
import { SourceWaterfallList } from '../../components/SourceWaterfallList';
import { coverCapacity } from '../../state/liquidityEngine';
import { useStore } from '../../state/store';
import { Toggle } from '../../components/ui';
import type { Txn } from '../../state/types';

export function AutoCover() {
  const { state, dispatch } = useStore();
  const [editing, setEditing] = useState(false);
  const cfg = state.autoCover;
  const capacity = coverCapacity(state);
  const failed = state.status === 'autoCoverFailed';

  const health: { label: string; tone: string } = !cfg.enabled
    ? { label: 'Off', tone: 'rulesPaused' }
    : capacity.own <= 0 && capacity.credit <= 0
      ? { label: 'No cover available', tone: 'autoCoverFailed' }
      : capacity.own <= 0
        ? { label: 'Credit only', tone: 'approachingMinimum' }
        : capacity.own < cfg.perTransactionMax
          ? { label: 'Limited', tone: 'approachingMinimum' }
          : { label: 'Ready', tone: 'healthy' };

  const covers = state.txns.filter((t) => t.smart?.engine === 'autoCover');
  const recent = [...covers].sort((a, b) => b.day - a.day).slice(0, 3);
  const usedThisMonth = cfg.usedThisMonth;

  return (
    <div className="screen">
      {/* Status + what it can actually do */}
      <section className="card" aria-label="Auto Cover status">
        <div className="flex items-center justify-between">
          <label className="flex items-center" style={{ gap: 'var(--space-sm)' }}>
            <Toggle
              checked={cfg.enabled}
              onChange={(v) => dispatch({ type: 'setAutoCoverEnabled', enabled: v })}
              label="Auto Cover"
            />
            <span style={{ fontWeight: 'var(--font-weight-semibold)' }}>{cfg.enabled ? 'On' : 'Off'}</span>
          </label>
          <span className={`status-pill status-pill--${health.tone}`}>
            <span className="status-pill__dot" aria-hidden="true" />
            {health.label}
          </span>
        </div>
        <p className="m-0" style={{ marginTop: 'var(--space-xs)' }}>
          If a payment needs more than Everyday holds, we move money from your sources — in your order — so it goes
          through.
        </p>
        <div className="sl-card__stats" style={{ borderTopColor: 'var(--color-border-subtle)' }}>
          <div className="sl-card__stat">
            <span className="micro block" style={{ color: 'var(--color-text-secondary)' }}>Backup from your cash</span>
            <span className="amount block" style={{ fontWeight: 'var(--font-weight-bold)' }}>
              CHF {swissNumber(capacity.own, 0)}
            </span>
          </div>
          <div className="sl-card__stat" style={{ borderLeft: '1px solid var(--color-border-subtle)', paddingLeft: 'var(--space-md)' }}>
            <span className="micro block" style={{ color: 'var(--color-text-secondary)' }}>Lombard backup</span>
            <span className="amount block" style={{ fontWeight: 'var(--font-weight-bold)' }}>
              {cfg.lombardEnabled ? `CHF ${swissNumber(capacity.credit, 0)}` : 'Off'}
            </span>
          </div>
        </div>
        <p className="micro m-0" style={{ marginTop: 'var(--space-xs)' }}>
          Max {money(cfg.perTransactionMax, 'CHF', 0)} per payment · {money(usedThisMonth, 'CHF', 0)} of{' '}
          {money(cfg.monthlyCap, 'CHF', 0)} used this month
        </p>
      </section>

      {failed && (
        <section className="notice notice--error" aria-label="Auto Cover failure">
          <strong>Auto Cover couldn't fully fund a payment</strong>
          <p className="m-0 caption" style={{ color: 'var(--color-text-primary)', marginTop: 'var(--space-2xs)' }}>
            No money was moved — Auto Cover only acts when it can cover the whole amount. Add money to Everyday, or
            authorise another source below.
          </p>
          <div className="flex" style={{ gap: 'var(--space-xs)', marginTop: 'var(--space-xs)' }}>
            <button
              type="button"
              className="btn btn--primary"
              onClick={() => dispatch({ type: 'manualTransferIn', amount: 5_000 })}
            >
              Transfer in {money(5_000, 'CHF', 0)}
            </button>
            <button
              type="button"
              className="btn btn--secondary"
              onClick={() => dispatch({ type: 'setFlag', flag: 'sourcesExhausted', value: false })}
            >
              Retry sources
            </button>
          </div>
        </section>
      )}

      {/* Funding order */}
      <section aria-label="Funding order">
        <div className="flex items-center justify-between" style={{ marginBottom: 'var(--space-xs)' }}>
          <h2 className="section-title m-0">Funding order</h2>
          <button type="button" className="btn btn--ghost" onClick={() => setEditing((v) => !v)}>
            {editing ? 'Done' : 'Edit rules'}
          </button>
        </div>
        <SourceWaterfallList editing={editing} />
      </section>

      {editing && (
        <>
          <section className="card" aria-label="Cover amount">
            <h2 className="section-title m-0" style={{ marginBottom: 'var(--space-sm)' }}>How much to move</h2>
            <div className="flex flex-col" style={{ gap: 'var(--space-xs)' }} role="radiogroup" aria-label="Cover amount">
              <button
                type="button"
                className="choice-row"
                role="radio"
                aria-checked={cfg.coverMode === 'exact'}
                onClick={() => dispatch({ type: 'setCoverMode', mode: 'exact' })}
              >
                <span className="choice-row__dot" aria-hidden="true" />
                <span>
                  <span className="block" style={{ fontWeight: 'var(--font-weight-medium)' }}>Exact cover</span>
                  <span className="caption block">Move only what the payment is short.</span>
                </span>
              </button>
              <button
                type="button"
                className="choice-row"
                role="radio"
                aria-checked={cfg.coverMode === 'buffer'}
                onClick={() => dispatch({ type: 'setCoverMode', mode: 'buffer' })}
              >
                <span className="choice-row__dot" aria-hidden="true" />
                <span>
                  <span className="block" style={{ fontWeight: 'var(--font-weight-medium)' }}>
                    Cover + {money(cfg.bufferAmount, 'CHF', 0)} buffer
                  </span>
                  <span className="caption block">Leave a little in Everyday so small payments don't trigger it again.</span>
                </span>
              </button>
            </div>
          </section>

          <section className="card" aria-label="Limits">
            <h2 className="section-title m-0" style={{ marginBottom: 'var(--space-xs)' }}>Your limits</h2>
            <label className="block" style={{ marginBottom: 'var(--space-sm)' }}>
              <span className="caption">Maximum per payment: <strong className="amount">{money(cfg.perTransactionMax, 'CHF', 0)}</strong></span>
              <input
                type="range"
                className="slider"
                min={500}
                max={20000}
                step={500}
                value={cfg.perTransactionMax}
                onChange={(e) => dispatch({ type: 'setPerTransactionMax', value: Number(e.target.value) })}
                aria-label="Maximum per payment"
              />
            </label>
            <label className="block" style={{ marginBottom: 'var(--space-sm)' }}>
              <span className="caption">Maximum per month: <strong className="amount">{money(cfg.monthlyCap, 'CHF', 0)}</strong></span>
              <input
                type="range"
                className="slider"
                min={1000}
                max={50000}
                step={1000}
                value={cfg.monthlyCap}
                onChange={(e) => dispatch({ type: 'setCoverMonthlyCap', value: Number(e.target.value) })}
                aria-label="Maximum per month"
              />
            </label>
            <label className="block">
              <span className="caption">Always keep in Trading: <strong className="amount">{money(cfg.tradingReserve, 'CHF', 0)}</strong></span>
              <input
                type="range"
                className="slider"
                min={0}
                max={20000}
                step={1000}
                value={cfg.tradingReserve}
                onChange={(e) => dispatch({ type: 'setTradingReserve', value: Number(e.target.value) })}
                aria-label="Trading reserve"
              />
            </label>
            <label className="flex items-center justify-between" style={{ gap: 'var(--space-sm)', marginTop: 'var(--space-sm)' }}>
              <span>
                <span className="block" style={{ fontWeight: 'var(--font-weight-medium)' }}>
                  Also keep Everyday above {money(cfg.minBalance, 'CHF', 0)}
                </span>
                <span className="caption block">Advanced — tops up at the end of the day, not only for payments.</span>
              </span>
              <Toggle
                checked={cfg.keepMinimumEnabled}
                onChange={(v) => dispatch({ type: 'setKeepMinimum', enabled: v })}
                label="Keep a minimum Everyday balance"
              />
            </label>
          </section>

          <section className="lombard-block" aria-label="Lombard backup">
            <div className="flex items-center justify-between" style={{ gap: 'var(--space-sm)' }}>
              <span className="flex-1">
                <span className="block" style={{ fontWeight: 'var(--font-weight-semibold)' }}>Lombard as last resort</span>
                <span className="caption block">
                  Borrowing at {LOMBARD_RATE_PA}% p.a. — used only after your own cash, never before.
                </span>
              </span>
              <Toggle
                checked={cfg.lombardEnabled}
                onChange={(v) => dispatch({ type: 'setLombard', enabled: v, acknowledged: cfg.lombardAcknowledged })}
                label="Lombard as Auto Cover source"
              />
            </div>
            <label className="flex items-start" style={{ gap: 'var(--space-xs)', marginTop: 'var(--space-sm)' }}>
              <input
                type="checkbox"
                checked={cfg.lombardAcknowledged}
                style={{ width: 'var(--space-md)', height: 'var(--space-md)', marginTop: 'var(--space-2xs)', accentColor: 'var(--color-action-primary)' }}
                onChange={(e) =>
                  dispatch({ type: 'setLombard', enabled: cfg.lombardEnabled && e.target.checked, acknowledged: e.target.checked })
                }
              />
              <span className="caption">
                I understand Auto Cover may increase my Lombard borrowing, that interest applies, that my available
                capacity can change, and that it will never exceed the limits I set.
              </span>
            </label>
            {cfg.lombardEnabled && cfg.lombardAcknowledged && (
              <label className="block" style={{ marginTop: 'var(--space-sm)' }}>
                <span className="caption">
                  Borrow at most <strong className="amount">{money(cfg.lombardPerCoverMax, 'CHF', 0)}</strong> per cover ·{' '}
                  <strong className="amount">{money(cfg.lombardMonthlyMax, 'CHF', 0)}</strong> per month
                </span>
                <input
                  type="range"
                  className="slider"
                  min={0}
                  max={10000}
                  step={500}
                  value={cfg.lombardPerCoverMax}
                  onChange={(e) => dispatch({ type: 'setLombardCoverLimits', perCover: Number(e.target.value) })}
                  aria-label="Maximum Lombard borrowing per cover"
                />
              </label>
            )}
          </section>
        </>
      )}

      {/* What it actually did */}
      {!editing && (
        <section className="card" aria-label="Auto Cover history">
          <h2 className="section-title m-0" style={{ marginBottom: 'var(--space-xs)' }}>Recent covers</h2>
          {recent.map((t: Txn) => (
            <div key={t.id} className="flex items-baseline justify-between" style={{ padding: 'var(--space-2xs) 0' }}>
              <span className="caption" style={{ color: 'var(--color-text-primary)' }}>
                {shortDate(t.day)} · from {t.smart?.source === 'lombard' ? 'Lombard (credit)' : t.smart?.title.replace('Auto Cover · from ', '')}
              </span>
              <span className="amount caption" style={{ fontWeight: 'var(--font-weight-semibold)', color: 'var(--color-text-primary)' }}>
                {money(t.amount, 'CHF', 0)}
              </span>
            </div>
          ))}
          {recent.length === 0 && <p className="caption m-0">No covers yet — nothing has needed one.</p>}
        </section>
      )}

      <p className="micro m-0">
        Auto Cover moves cash only. It never sells your investments, and it never borrows unless you switch Lombard on
        yourself.
      </p>
    </div>
  );
}
