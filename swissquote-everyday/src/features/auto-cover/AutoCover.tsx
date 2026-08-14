/**
 * §5.5 Auto Cover — toggle (off by default in the product), trigger threshold,
 * source waterfall, on-screen guardrails, separate Lombard opt-in behind an
 * explicit risk acknowledgement, and a failure state with two manual routes.
 */
import { useState } from 'react';
import { money } from '../../lib/format';
import { LOMBARD_RATE_PA } from '../../data/mockLedger';
import { SourceWaterfallList } from '../../components/SourceWaterfallList';
import { useStore } from '../../state/store';
import { ScreenHeader, Toggle } from '../../components/ui';

export function AutoCover() {
  const { state, dispatch, nav } = useStore();
  const cfg = state.autoCover;
  const [ackChecked, setAckChecked] = useState(cfg.lombardAcknowledged);
  const failed = state.status === 'autoCoverFailed';
  const shortfall = Math.max(0, cfg.minBalance - state.accounts.everyday);

  return (
    <div className="screen">
      <ScreenHeader title="Auto Cover" onBack={() => nav.go('home')} />

      <section className="card">
        <label className="flex items-center justify-between" style={{ gap: 'var(--space-sm)' }}>
          <span>
            <span className="block" style={{ fontWeight: 'var(--font-weight-semibold)' }}>Auto Cover</span>
            <span className="caption block">
              If Everyday runs short, it tops up automatically from your sources — in your order. Off by default; you
              are always notified when it runs.
            </span>
          </span>
          <Toggle checked={cfg.enabled} onChange={(v) => dispatch({ type: 'setAutoCoverEnabled', enabled: v })} label="Auto Cover" />
        </label>
      </section>

      {failed && (
        <section className="notice notice--error" aria-label="Auto Cover failure">
          <strong>All sources are exhausted.</strong>
          <p className="m-0" style={{ marginTop: 'var(--space-2xs)' }}>
            Your balance is {money(shortfall)} below your minimum and no source could cover it. Two ways forward:
          </p>
          <div className="flex" style={{ gap: 'var(--space-xs)', marginTop: 'var(--space-xs)' }}>
            <button
              type="button"
              className="btn btn--primary"
              onClick={() => dispatch({ type: 'manualTransferIn', amount: Math.ceil(shortfall / 50) * 50 })}
            >
              Transfer in {money(Math.ceil(shortfall / 50) * 50)}
            </button>
            <button type="button" className="btn btn--secondary" onClick={() => dispatch({ type: 'setFlag', flag: 'sourcesExhausted', value: false })}>
              Sell positions
            </button>
          </div>
        </section>
      )}

      <section className="card" aria-label="Trigger">
        <h2 className="section-title m-0" style={{ marginBottom: 'var(--space-xs)' }}>Trigger</h2>
        <label className="block">
          <span className="caption">Minimum balance: <strong className="amount">{money(cfg.minBalance)}</strong></span>
          <input
            type="range"
            className="slider"
            min={0}
            max={3000}
            step={50}
            value={cfg.minBalance}
            onChange={(e) => dispatch({ type: 'setMinBalance', value: Number(e.target.value) })}
            aria-label="Minimum balance"
          />
        </label>
        <p className="caption m-0">
          A top-up runs when your balance falls below this — or when an incoming debit would take it below.
        </p>
      </section>

      <section aria-label="Sources">
        <h2 className="section-title" style={{ margin: '0 0 var(--space-xs)' }}>Sources, in your order</h2>
        <SourceWaterfallList />
        {state.flags.marketClosed && (
          <p className="caption m-0" style={{ marginTop: 'var(--space-xs)' }}>
            Market closed right now: Trading cash is skipped and the waterfall moves to the next source.
          </p>
        )}
      </section>

      <section className="lombard-block" aria-label="Lombard opt-in">
        <label className="flex items-center justify-between" style={{ gap: 'var(--space-sm)' }}>
          <span>
            <span className="block" style={{ fontWeight: 'var(--font-weight-semibold)' }}>Use Lombard credit as last resort</span>
            <span className="caption block">Borrowing against your portfolio at {LOMBARD_RATE_PA}% p.a. ⟨rate TO CONFIRM⟩</span>
          </span>
          <Toggle
            checked={cfg.lombardEnabled}
            onChange={(v) => dispatch({ type: 'setLombard', enabled: v, acknowledged: ackChecked })}
            label="Lombard as Auto Cover source"
          />
        </label>
        <label className="flex items-start" style={{ gap: 'var(--space-xs)', marginTop: 'var(--space-sm)' }}>
          <input
            type="checkbox"
            checked={ackChecked}
            style={{ width: 'var(--space-md)', height: 'var(--space-md)', marginTop: 'var(--space-2xs)', accentColor: 'var(--color-action-primary)' }}
            onChange={(e) => {
              setAckChecked(e.target.checked);
              dispatch({ type: 'setLombard', enabled: cfg.lombardEnabled && e.target.checked, acknowledged: e.target.checked });
            }}
          />
          <span className="caption">
            I understand this is borrowing against my portfolio. If markets fall, Swissquote may require me to add
            funds or may sell positions.
          </span>
        </label>
        {cfg.lombardEnabled && !ackChecked && (
          <p className="caption m-0" style={{ color: 'var(--color-text-error)' }}>Acknowledge the risk to enable Lombard.</p>
        )}
      </section>

      <section className="card card--subtle" aria-label="Guardrails">
        <h2 className="section-title m-0" style={{ marginBottom: 'var(--space-xs)' }}>Guardrails</h2>
        <dl className="m-0 grid grid-cols-2" style={{ gap: 'var(--space-2xs) var(--space-sm)', fontSize: 'var(--font-size-caption)' }}>
          <dt className="caption m-0">Top-up increment</dt>
          <dd className="m-0 amount">{money(cfg.topUpIncrement)}</dd>
          <dt className="caption m-0">Monthly cap</dt>
          <dd className="m-0 amount">{money(cfg.monthlyCap)} · used {money(cfg.usedThisMonth)}</dd>
          <dt className="caption m-0">Cooldown</dt>
          <dd className="m-0">{cfg.cooldownDays} day between top-ups</dd>
          <dt className="caption m-0">Notification</dt>
          <dd className="m-0">On every execution</dd>
        </dl>
      </section>
    </div>
  );
}
