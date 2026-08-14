/**
 * AI Budgeting — predicts the liquidity needed before the next salary, so
 * Smart Salary Allocation knows how much is genuinely surplus.
 *
 * Kept to a glance: the KEEP / GROW split (§59) with the forecast horizon,
 * the projection, and one control (safety level). The calculation breakdown,
 * boundaries and planned expenses sit behind "Adjust forecast" (§41).
 */
import { useState } from 'react';
import { money, shortDate, swissNumber } from '../../lib/format';
import { LiquidityForecastChart } from '../../components/LiquidityForecastChart';
import { useStore } from '../../state/store';
import type { SafetyLevel } from '../../state/types';

const SAFETY_LABELS: Record<SafetyLevel, { title: string; blurb: string }> = {
  efficient: { title: 'Efficient', blurb: 'Smaller cash reserve' },
  balanced: { title: 'Balanced', blurb: 'Recommended' },
  cautious: { title: 'Cautious', blurb: 'Larger cash reserve' },
};

export function AiBudgeting() {
  const { state, dispatch, forecast, buyingPower } = useStore();
  const [adjusting, setAdjusting] = useState(false);
  const rule = state.allocation;
  const f = forecast.factors;

  const grow = Math.max(0, buyingPower.availableNow - forecast.keep);

  return (
    <div className="screen">
      {/* KEEP / GROW — the whole idea in one card (§59) */}
      <section className="card" aria-label="Keep and grow">
        <div className="flex items-baseline justify-between">
          <span className="section-title">
            {shortDate(forecast.horizonStart)} → {shortDate(forecast.horizonEnd)}
          </span>
          <span className={`status-pill status-pill--${forecast.confidence === 'high' ? 'healthy' : forecast.confidence === 'medium' ? 'approachingMinimum' : 'autoCoverFailed'}`}>
            <span className="status-pill__dot" aria-hidden="true" />
            {forecast.confidence === 'high' ? 'Predictable' : forecast.confidence === 'medium' ? 'Varies' : 'Less predictable'}
          </span>
        </div>

        <div className="keep-grow" style={{ marginTop: 'var(--space-sm)' }}>
          <div className="keep-grow__side">
            <span className="keep-grow__label">Keep</span>
            <span className="keep-grow__value amount">CHF {swissNumber(forecast.keep, 0)}</span>
            <span className="caption">For spending &amp; safety until your next salary</span>
          </div>
          <div className="keep-grow__side keep-grow__side--grow">
            <span className="keep-grow__label">Grow</span>
            <span className="keep-grow__value amount">CHF {swissNumber(grow, 0)}</span>
            <span className="caption">Available for your financial plan</span>
          </div>
        </div>

        <p className="caption m-0" style={{ marginTop: 'var(--space-sm)' }}>
          We expect about {money(forecast.expectedRequirement, 'CHF', 0)} of spending before{' '}
          {shortDate(forecast.horizonEnd)} and added a {money(forecast.safetyMargin, 'CHF', 0)} safety margin.
          {forecast.confidence !== 'high' && ` ${forecast.confidenceNote}`}
        </p>
        {forecast.liftedByMin && (
          <p className="caption m-0" style={{ marginTop: 'var(--space-2xs)', color: 'var(--color-text-primary)' }}>
            Your own minimum of {money(rule.minKeep, 'CHF', 0)} applies — it is higher than the{' '}
            {money(forecast.keepRaw, 'CHF', 0)} we predicted.
          </p>
        )}
        {forecast.aboveMax && (
          <div className="notice notice--warning" style={{ marginTop: 'var(--space-xs)' }}>
            Your predicted expenses are above your preferred maximum of {money(rule.maxKeep, 'CHF', 0)}. We're keeping
            the higher amount so your payments are covered — review the forecast before your next allocation.
          </div>
        )}
        {forecast.fallbackUsed && (
          <div className="notice notice--info" style={{ marginTop: 'var(--space-xs)' }}>
            Using your fixed buffer of {money(rule.manualBuffer, 'CHF', 0)} instead of the prediction.
          </div>
        )}
      </section>

      {/* The projection */}
      <section className="card" aria-label="Projected balance">
        <h2 className="section-title m-0" style={{ marginBottom: 'var(--space-xs)' }}>
          Until your next salary
        </h2>
        <LiquidityForecastChart forecast={forecast} minBalance={forecast.keep} />
      </section>

      {/* One control by default; everything else behind Adjust */}
      {!adjusting ? (
        <button type="button" className="btn btn--secondary" onClick={() => setAdjusting(true)}>
          Adjust forecast
        </button>
      ) : (
        <>
          <section className="card" aria-label="Safety level">
            <h2 className="section-title m-0" style={{ marginBottom: 'var(--space-xs)' }}>
              How careful should we be?
            </h2>
            <div className="flex flex-col" style={{ gap: 'var(--space-xs)' }} role="radiogroup" aria-label="Safety level">
              {(Object.keys(SAFETY_LABELS) as SafetyLevel[]).map((level) => {
                // Show what each level would keep, in francs — never labels alone (§17).
                const factor = level === 'efficient' ? 0.08 : level === 'balanced' ? 0.16 : 0.3;
                const preview = Math.round((forecast.expectedRequirement * (1 + factor)) / 50) * 50;
                return (
                  <button
                    key={level}
                    type="button"
                    className="choice-row"
                    role="radio"
                    aria-checked={rule.safetyLevel === level}
                    onClick={() => dispatch({ type: 'setSafetyLevel', level })}
                  >
                    <span className="choice-row__dot" aria-hidden="true" />
                    <span className="flex-1 min-w-0">
                      <span className="block" style={{ fontWeight: 'var(--font-weight-medium)' }}>
                        {SAFETY_LABELS[level].title}
                      </span>
                      <span className="caption block">{SAFETY_LABELS[level].blurb}</span>
                    </span>
                    <span className="amount" style={{ fontWeight: 'var(--font-weight-semibold)' }}>
                      {swissNumber(Math.max(preview, rule.minKeep), 0)}
                    </span>
                  </button>
                );
              })}
            </div>
          </section>

          <section className="card" aria-label="Your limits">
            <h2 className="section-title m-0" style={{ marginBottom: 'var(--space-xs)' }}>Your limits</h2>
            <label className="block" style={{ marginBottom: 'var(--space-sm)' }}>
              <span className="caption">Never keep less than <strong className="amount">{money(rule.minKeep, 'CHF', 0)}</strong></span>
              <input
                type="range"
                className="slider"
                min={2000}
                max={20000}
                step={500}
                value={rule.minKeep}
                onChange={(e) => dispatch({ type: 'setKeepBoundaries', min: Number(e.target.value) })}
                aria-label="Minimum cash to keep"
              />
            </label>
            <label className="block">
              <span className="caption">Normal maximum <strong className="amount">{money(rule.maxKeep, 'CHF', 0)}</strong></span>
              <input
                type="range"
                className="slider"
                min={5000}
                max={40000}
                step={500}
                value={rule.maxKeep}
                onChange={(e) => dispatch({ type: 'setKeepBoundaries', max: Number(e.target.value) })}
                aria-label="Preferred maximum cash to keep"
              />
            </label>
            <div className="flex items-center" style={{ gap: 'var(--space-xs)', marginTop: 'var(--space-sm)' }}>
              <button
                type="button"
                className={`btn ${rule.bufferMode === 'ai' ? 'btn--primary' : 'btn--secondary'}`}
                onClick={() => dispatch({ type: 'setBufferMode', mode: 'ai' })}
              >
                Predict it
              </button>
              <button
                type="button"
                className={`btn ${rule.bufferMode === 'manual' ? 'btn--primary' : 'btn--secondary'}`}
                onClick={() => dispatch({ type: 'setBufferMode', mode: 'manual', manualBuffer: forecast.keepRaw })}
              >
                Fixed amount
              </button>
            </div>
          </section>

          <section className="card" aria-label="Planned expenses">
            <h2 className="section-title m-0" style={{ marginBottom: 'var(--space-xs)' }}>Planned expenses</h2>
            <p className="caption m-0" style={{ marginBottom: 'var(--space-xs)' }}>
              Tell us about spending we can't see in your history yet — we'll protect it.
            </p>
            {state.plannedExpenses.map((p) => (
              <div key={p.id} className="settings-row">
                <span className="flex-1">{p.label}</span>
                <span className="amount">{money(p.amount, 'CHF', 0)}</span>
                <button
                  type="button"
                  className="btn btn--ghost"
                  onClick={() => dispatch({ type: 'removePlannedExpense', id: p.id })}
                >
                  Remove
                </button>
              </div>
            ))}
            <div className="flex flex-wrap" style={{ gap: 'var(--space-xs)', marginTop: 'var(--space-xs)' }}>
              <button
                type="button"
                className="btn btn--secondary"
                onClick={() => dispatch({ type: 'addPlannedExpense', label: 'Summer holiday', amount: 8_000 })}
              >
                + Holiday 8'000
              </button>
              <button
                type="button"
                className="btn btn--secondary"
                onClick={() => dispatch({ type: 'addPlannedExpense', label: 'Cantonal taxes', amount: 24_000 })}
              >
                + Taxes 24'000
              </button>
            </div>
          </section>

          <button type="button" className="btn btn--primary" onClick={() => setAdjusting(false)}>
            Done
          </button>
        </>
      )}

      {/* Explainability — always reachable, never in the way (§54) */}
      <details className="card">
        <summary className="disclosure" style={{ listStyle: 'none', cursor: 'pointer' }}>
          How we calculated {money(forecast.keep, 'CHF', 0)}
          <span className="disclosure__chevron" aria-hidden="true">›</span>
        </summary>
        <div style={{ marginTop: 'var(--space-xs)' }}>
          {[
            { label: 'Confirmed upcoming', value: forecast.confirmedUpcoming, note: `incl. ${money(forecast.pendingCard, 'CHF', 0)} authorised card payments` },
            { label: 'Recurring bills', value: forecast.recurringPredicted, note: f.recurring.filter((r) => r.dueInCycle).map((r) => r.label.split(' — ')[0]).join(', ') || 'none due this cycle' },
            { label: 'Everyday spending', value: forecast.variablePredicted, note: `${money(Math.round(f.avgDailyCardSpend), 'CHF', 0)}/day over ${forecast.horizonDays} days` },
            { label: 'Safety margin', value: forecast.safetyMargin, note: `${SAFETY_LABELS[rule.safetyLevel].title} level` },
          ].map((row) => (
            <div key={row.label} className="factor-row" style={{ borderTop: '1px solid var(--color-border-subtle)' }}>
              <span className="factor-row__label">{row.label}</span>
              <span className="factor-row__value">
                <strong className="amount">{money(row.value, 'CHF', 0)}</strong>
                <span className="micro block">{row.note}</span>
              </span>
            </div>
          ))}
          <div className="factor-row" style={{ borderTop: '1px solid var(--color-border-default)' }}>
            <span className="factor-row__label" style={{ fontWeight: 'var(--font-weight-semibold)' }}>Recommended</span>
            <span className="factor-row__value amount" style={{ fontWeight: 'var(--font-weight-bold)' }}>
              {money(forecast.keep, 'CHF', 0)}
            </span>
          </div>
          <p className="micro m-0" style={{ marginTop: 'var(--space-xs)' }}>
            An estimate from your Swissquote account and card history only — that data stays within Swissquote.
            {f.oneOffsExcluded.length > 0 &&
              ` One-off payments (${f.oneOffsExcluded.map((o) => o.label).join(', ')}) are excluded so they don't inflate it.`}
          </p>
        </div>
      </details>
    </div>
  );
}
