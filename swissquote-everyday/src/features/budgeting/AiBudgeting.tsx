/**
 * §5.4 AI Budgeting — simplified to a glance, like the allocation screen.
 *
 * One hero card (the 30-day range + projection chart), one action card (the
 * buffer, with its consequence shown live), and the mandatory "How this is
 * calculated" panel present but collapsed behind a disclosure — transparency
 * on demand, not as a wall of text. Probabilistic language throughout.
 */
import { useState } from 'react';
import { money } from '../../lib/format';
import { LiquidityForecastChart } from '../../components/LiquidityForecastChart';
import { useStore } from '../../state/store';

export function AiBudgeting() {
  const { state, dispatch, forecast } = useStore();
  const [showFactors, setShowFactors] = useState(false);
  const rule = state.allocation;
  const activeBuffer = rule.bufferMode === 'ai' ? forecast.buffer : rule.manualBuffer;
  const delta = activeBuffer - forecast.buffer;
  const f = forecast.factors;

  const factors: { label: string; value: string }[] = [
    {
      label: 'Recurring debits',
      value: `${f.recurring
        .slice(0, 3)
        .map((r) => r.label.split(' — ')[0])
        .join(', ')}${f.recurring.length > 3 ? '…' : ''} — ${money(f.recurringMonthlyTotal, 'CHF', 0)}/month. Largest weight.`,
    },
    {
      label: 'Card spend',
      value: `≈ ${money(Math.round(f.avgDailyCardSpend * 30), 'CHF', 0)}/month over the last ${f.monthsOfHistory} months, varying ±${money(Math.round(f.dailyStdDev), 'CHF', 0)} per day.`,
    },
    {
      label: 'One-offs excluded',
      value:
        f.oneOffsExcluded.length > 0
          ? `${f.oneOffsExcluded.map((o) => `${o.label} (${money(o.amount, 'CHF', 0)})`).join(', ')} — single large payments don't inflate the estimate.`
          : 'None in this period.',
    },
    {
      label: 'Seasonal effects',
      value: f.seasonalNote ?? 'None right now — December and holiday periods raise the estimate.',
    },
  ];

  return (
    <div className="screen">
      {/* Hero — the estimate and the projection, one card */}
      <section className="card" aria-label="30-day liquidity estimate">
        <p className="caption m-0">Liquidity you'll likely need, next 30 days</p>
        <p className="m-0 amount" style={{ fontSize: 'var(--font-size-display)', fontWeight: 'var(--font-weight-bold)', lineHeight: 'var(--line-height-tight)' }}>
          {money(forecast.bufferLow, 'CHF', 0)} – {money(forecast.bufferHigh, 'CHF', 0)}
        </p>
        <p className="caption m-0" style={{ marginBottom: 'var(--space-sm)' }}>
          Best estimate {money(forecast.buffer, 'CHF', 0)} · based on your last 3 months, not a guarantee.
          {f.widened && ' Your income is irregular, so the range is wider than usual.'}
        </p>
        <LiquidityForecastChart forecast={forecast} minBalance={state.autoCover.minBalance} />
        <p className="micro m-0" style={{ marginTop: 'var(--space-xs)' }}>
          Shaded band = typical to high-spend scenario · marked points: rent, insurance, salary.
        </p>
      </section>

      {/* The one control — your buffer */}
      <section className="card" aria-label="Your buffer">
        <div className="flex items-baseline justify-between">
          <h2 className="section-title m-0">Your buffer</h2>
          <span className="caption">
            {rule.bufferMode === 'ai' ? 'Following the estimate' : delta === 0 ? 'Equal to the estimate' : delta > 0 ? `${money(delta, 'CHF', 0)} above` : `${money(-delta, 'CHF', 0)} below`}
          </span>
        </div>
        <p className="m-0 amount" style={{ fontSize: 'var(--font-size-title)', fontWeight: 'var(--font-weight-bold)' }}>
          {money(activeBuffer, 'CHF', 0)}
        </p>
        <input
          type="range"
          className="slider"
          min={4000}
          max={24000}
          step={100}
          value={activeBuffer}
          onChange={(e) => dispatch({ type: 'setBufferMode', mode: 'manual', manualBuffer: Number(e.target.value) })}
          aria-label="Buffer override"
        />
        <p className="caption m-0" aria-live="polite">
          {delta < 0
            ? 'Lower buffer → more gets invested, and Auto Cover is more likely to trigger.'
            : delta > 0
              ? 'Higher buffer → more cash stays idle, and Auto Cover is less likely to trigger.'
              : 'Smart Salary Allocation keeps this amount in Banking each month.'}
        </p>
        {rule.bufferMode === 'manual' && (
          <button type="button" className="btn btn--ghost" onClick={() => dispatch({ type: 'setBufferMode', mode: 'ai' })}>
            Follow the AI estimate again
          </button>
        )}
      </section>

      {/* Mandatory explainability — present, but on demand */}
      <section className="card" aria-label="How this is calculated">
        <button type="button" className="disclosure" aria-expanded={showFactors} onClick={() => setShowFactors((v) => !v)}>
          How this is calculated
          <span className="disclosure__chevron" aria-hidden="true">›</span>
        </button>
        {showFactors && (
          <div style={{ marginTop: 'var(--space-2xs)' }}>
            {factors.map((row) => (
              <div key={row.label} className="factor-row" style={{ borderTop: '1px solid var(--color-border-subtle)' }}>
                <span className="factor-row__label">{row.label}</span>
                <span className="factor-row__value">{row.value}</span>
              </div>
            ))}
            <p className="micro m-0" style={{ marginTop: 'var(--space-xs)' }}>
              The estimate uses only your Swissquote account and card history — that data stays within Swissquote.
              Turn AI Budgeting off in settings at any time; your buffer then becomes a fixed amount you choose.
            </p>
          </div>
        )}
      </section>
    </div>
  );
}
