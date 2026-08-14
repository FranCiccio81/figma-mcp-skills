/**
 * §5.4 AI Budgeting — the 30-day liquidity forecast with explainability.
 * Probabilistic language only. The "How this is calculated" panel is
 * mandatory; the client can always override the buffer, with the consequence
 * shown live.
 */
import { money } from '../../lib/format';
import { LiquidityForecastChart } from '../../components/LiquidityForecastChart';
import { useStore } from '../../state/store';

export function AiBudgeting() {
  const { state, dispatch, forecast } = useStore();
  const rule = state.allocation;
  const activeBuffer = rule.bufferMode === 'ai' ? forecast.buffer : rule.manualBuffer;
  const delta = activeBuffer - forecast.buffer;
  const f = forecast.factors;

  return (
    <div className="screen">
      <section aria-label="Recommended buffer">
        <p className="caption m-0">Liquidity you'll likely need over the next 30 days</p>
        <p className="m-0 amount" style={{ fontSize: 'var(--font-size-display)', fontWeight: 'var(--font-weight-bold)', lineHeight: 'var(--line-height-tight)' }}>
          {money(forecast.bufferLow)} – {money(forecast.bufferHigh)}
        </p>
        <p className="caption m-0">
          Best estimate {money(forecast.buffer)} — an estimate, based on your last 3 months, not a guarantee.
          {f.widened && ' Your income is irregular, so the range is wider than usual.'}
        </p>
      </section>

      <section className="card" aria-label="30-day projection">
        <h2 className="section-title m-0" style={{ marginBottom: 'var(--space-xs)' }}>Projected balance, next 30 days</h2>
        <LiquidityForecastChart forecast={forecast} minBalance={state.autoCover.minBalance} />
        <p className="micro m-0" style={{ marginTop: 'var(--space-xs)' }}>
          Shaded band = typical to high-spend scenario. Marked points: rent, insurance, salary.
        </p>
      </section>

      <section className="card" aria-label="How this is calculated">
        <h2 className="section-title m-0" style={{ marginBottom: 'var(--space-xs)' }}>How this is calculated</h2>
        <ul className="m-0" style={{ paddingLeft: 'var(--space-md)', display: 'flex', flexDirection: 'column', gap: 'var(--space-2xs)' }}>
          <li>
            <strong>Recurring debits detected</strong> (largest weight): {f.recurring.map((r) => `${r.label.split(' — ')[0]} ${money(r.amount)}`).join(', ')} — {money(f.recurringMonthlyTotal)}/month in total.
          </li>
          <li>
            <strong>Average card spend</strong> over the last {f.monthsOfHistory} months: about {money(Math.round(f.avgDailyCardSpend * 30))}/month, varying day to day (±{money(Math.round(f.dailyStdDev))} per day).
          </li>
          <li>
            <strong>One-off items excluded</strong>: {f.oneOffsExcluded.length > 0 ? f.oneOffsExcluded.map((o) => `${o.label} (${money(o.amount)})`).join(', ') : 'none in this period'} — single large payments don't inflate your estimate.
          </li>
          <li>
            <strong>Seasonal effects</strong>: {f.seasonalNote ?? 'no seasonal adjustment applies right now (December and holiday periods raise the estimate).'}
          </li>
        </ul>
        <p className="micro m-0" style={{ marginTop: 'var(--space-sm)' }}>
          The estimate uses only your Swissquote account and card history. That data stays within Swissquote. You can
          turn AI Budgeting off in settings at any time — your buffer then becomes a fixed amount you choose.
        </p>
      </section>

      <section className="card" aria-label="Your override">
        <h2 className="section-title m-0" style={{ marginBottom: 'var(--space-xs)' }}>Your buffer</h2>
        <label className="block">
          <span className="caption">
            {money(activeBuffer)}
            {rule.bufferMode === 'ai' ? ' · following the estimate' : delta === 0 ? ' · equal to the estimate' : delta > 0 ? ` · ${money(delta)} above the estimate` : ` · ${money(-delta)} below the estimate`}
          </span>
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
        </label>
        <p className="caption m-0" aria-live="polite">
          {delta < 0
            ? 'Lower buffer → more gets invested, and Auto Cover is more likely to trigger.'
            : delta > 0
              ? 'Higher buffer → more cash stays idle in Everyday, and Auto Cover is less likely to trigger.'
              : 'The allocation rule keeps this amount in Everyday each month.'}
        </p>
        {rule.bufferMode === 'manual' && (
          <button type="button" className="btn btn--ghost" onClick={() => dispatch({ type: 'setBufferMode', mode: 'ai' })}>
            Follow the AI estimate again
          </button>
        )}
      </section>
    </div>
  );
}
