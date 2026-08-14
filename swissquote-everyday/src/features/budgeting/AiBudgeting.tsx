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
import { PLAN_SWATCH } from '../../components/PlanBar';
import { keepForSafetyLevel } from '../../state/forecast';
import { useStore } from '../../state/store';
import type { SafetyLevel } from '../../state/types';

const SAFETY_LABELS: Record<SafetyLevel, { title: string; blurb: string }> = {
  efficient: { title: 'Efficient', blurb: 'Smaller cash reserve' },
  balanced: { title: 'Balanced', blurb: 'Recommended' },
  cautious: { title: 'Cautious', blurb: 'Larger cash reserve' },
};

/**
 * "Put it to work" — the action the GROW figure implies.
 *
 * It deploys through the allocation plan the client already approved, so the
 * app proposes an amount, never a product or a weighting: no new investment
 * decision is made here, and the protected liquidity is never touched.
 */
function PutToWorkCard({ grow }: { grow: number }) {
  const { state, dispatch, nav } = useStore();
  const rule = state.allocation;
  const [amount, setAmount] = useState(() => Math.floor(grow / 1_000) * 1_000);
  const [adjusting, setAdjusting] = useState(false);

  // Confirm what just happened before offering to do it again.
  const doneToday = state.txns.filter(
    (t) => t.day === state.day && t.smart?.title.startsWith('Surplus put to work'),
  );
  if (doneToday.length > 0) {
    const total = doneToday.reduce((s, t) => s + -t.amount, 0);
    return (
      <section className="card" aria-label="Surplus put to work">
        <div className="flex items-baseline justify-between" style={{ marginBottom: 'var(--space-2xs)' }}>
          <h2 className="section-title m-0">Done today</h2>
          <span className="status-pill status-pill--healthy">
            <span className="status-pill__dot" aria-hidden="true" />
            Working
          </span>
        </div>
        <p className="m-0">
          <strong className="amount">{money(total, 'CHF', 0)}</strong> went to work through your plan across{' '}
          {doneToday.length} destinations. {money(grow, 'CHF', 0)} of flexible cash remains.
        </p>
        <button
          type="button"
          className="btn btn--secondary"
          style={{ marginTop: 'var(--space-sm)' }}
          onClick={() => nav.go('transactions')}
        >
          See the movements
        </button>
      </section>
    );
  }

  // Keep the proposal within what is actually flexible as the balance moves.
  const capped = Math.min(amount, Math.floor(grow / 100) * 100);
  const splitTotal = rule.splits.reduce((s, x) => s + x.percent, 0) || 100;
  const step = grow > 50_000 ? 1_000 : 100;

  return (
    <section className="card" aria-label="Put your surplus to work">
      <div className="flex items-baseline justify-between" style={{ marginBottom: 'var(--space-2xs)' }}>
        <h2 className="section-title m-0">Put it to work</h2>
        <span className="caption">Your plan · unchanged</span>
      </div>
      <p className="m-0" style={{ marginBottom: 'var(--space-sm)' }}>
        {money(grow, 'CHF', 0)} is sitting above what you'll likely need. Your plan would send it here:
      </p>

      {rule.splits.map((s) => (
        <div key={s.destination} className="plan-row" style={{ padding: 'var(--space-2xs) 0' }}>
          <span className={`plan-row__swatch ${PLAN_SWATCH[s.destination]}`} aria-hidden="true" />
          <span className="flex-1 caption" style={{ color: 'var(--color-text-primary)' }}>{s.label}</span>
          <span className="caption amount">{s.percent}%</span>
          <span
            className="amount caption"
            style={{ fontWeight: 'var(--font-weight-semibold)', color: 'var(--color-text-primary)', minWidth: 'var(--space-2xl)', textAlign: 'right' }}
          >
            {swissNumber(Math.round((capped * s.percent) / splitTotal / 10) * 10, 0)}
          </span>
        </div>
      ))}

      {adjusting && (
        <label className="block" style={{ marginTop: 'var(--space-xs)' }}>
          <span className="caption">Amount: {money(capped, 'CHF', 0)}</span>
          <input
            type="range"
            className="slider"
            min={Math.min(rule.minAllocation, capped)}
            max={Math.floor(grow / 100) * 100}
            step={step}
            value={capped}
            onChange={(e) => setAmount(Number(e.target.value))}
            aria-label="Amount to put to work"
          />
        </label>
      )}

      <div className="flex items-center flex-wrap" style={{ gap: 'var(--space-xs)', marginTop: 'var(--space-sm)' }}>
        <button
          type="button"
          className="btn btn--primary"
          onClick={() => dispatch({ type: 'allocateSurplusNow', amount: capped })}
        >
          Put {money(capped, 'CHF', 0)} to work
        </button>
        <button type="button" className="btn btn--ghost" onClick={() => setAdjusting((v) => !v)}>
          {adjusting ? 'Done' : 'Change amount'}
        </button>
      </div>
      <p className="micro m-0" style={{ marginTop: 'var(--space-xs)' }}>
        Moves cash through the plan you already set — it doesn't choose investments for you, and the{' '}
        <button
          type="button"
          className="link micro"
          style={{ padding: 0 }}
          onClick={() => nav.go('allocation')}
        >
          plan is editable
        </button>{' '}
        at any time. Nothing happens automatically until your next salary.
      </p>
    </section>
  );
}

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

      {/* The action GROW implies — the client's own plan, one tap away */}
      {grow >= rule.minAllocation && <PutToWorkCard grow={grow} />}

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
                // Exactly what each level would protect — the engine's own
                // arithmetic, so the comparison is real (§17).
                const preview = keepForSafetyLevel(forecast, level, rule.minKeep);
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
                    <span className="text-right">
                      <span className="block amount" style={{ fontWeight: 'var(--font-weight-semibold)' }}>
                        {swissNumber(preview.amount, 0)}
                      </span>
                      {preview.clampedByMin && <span className="micro block">your minimum</span>}
                    </span>
                  </button>
                );
              })}
            </div>
            {(['efficient', 'balanced', 'cautious'] as SafetyLevel[]).every(
              (l) => keepForSafetyLevel(forecast, l, rule.minKeep).clampedByMin,
            ) && (
              <p className="caption m-0" style={{ marginTop: 'var(--space-xs)' }}>
                All three land on your {money(rule.minKeep, 'CHF', 0)} minimum right now — we predict less than that
                before your next salary. Lower your minimum below to let the estimate decide.
              </p>
            )}
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
