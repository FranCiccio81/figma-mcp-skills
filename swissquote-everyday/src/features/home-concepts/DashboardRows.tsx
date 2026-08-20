/**
 * "My dashboard" — the metric list on the analytical Home, and the two
 * monitor cards above it.
 *
 * The pattern is borrowed wholesale from health dashboards, because it earns
 * its keep there for the same reason it would here: one row per metric,
 * today's figure large, **what it usually is** underneath it, and an arrow
 * for the direction. A number without its baseline is trivia; with one it is
 * a judgement the client can make in a second.
 *
 * Two departures from the fitness version, both required by the domain:
 *   • Direction is not sentiment. Spending up is not good news, so the arrow
 *     shows the move and the colour shows whether it is welcome — and the
 *     accessible name says both, since colour alone never carries meaning.
 *   • Which rows appear is a preset, not a preference buried in settings:
 *     an everyday client and a trader want different dashboards from the
 *     same account.
 */
import { useState } from 'react';
import type { Metric, MetricPreset, Monitor } from './homeData';
import { useGoTo } from './shared';

const TREND_GLYPH: Record<Metric['trend'], string> = { up: '▲', down: '▼', flat: '•' };
const TREND_WORD: Record<Metric['trend'], string> = {
  up: 'higher than',
  down: 'lower than',
  flat: 'in line with',
};

export const PRESET_LABELS: Record<MetricPreset, string> = {
  everyday: 'Everyday',
  trader: 'Trader',
};

function MetricRow({ metric }: { metric: Metric }) {
  const goTo = useGoTo();
  const name = [
    metric.label,
    metric.value,
    metric.baseline ? `${TREND_WORD[metric.trend]} ${metric.baseline}` : null,
    metric.baselineLabel,
  ]
    .filter(Boolean)
    .join(', ');

  return (
    <button
      type="button"
      className="metric"
      aria-label={name}
      onClick={() => metric.destination && goTo(metric.destination)}
    >
      <span className="metric__label">{metric.label}</span>
      <span className="metric__figures">
        <span className="metric__value amount">
          {metric.value}
          <span className={`metric__trend metric__trend--${metric.sentiment}`} aria-hidden="true">
            {TREND_GLYPH[metric.trend]}
          </span>
        </span>
        {metric.baseline && <span className="metric__baseline amount">{metric.baseline}</span>}
      </span>
    </button>
  );
}

export function MetricList({
  metrics,
  presets,
  preset,
  onPreset,
}: {
  metrics: Metric[];
  presets: MetricPreset[];
  preset: MetricPreset;
  onPreset: (p: MetricPreset) => void;
}) {
  const rows = metrics.filter((m) => m.presets.includes(preset));
  if (rows.length === 0) return null;

  return (
    <section aria-label="My dashboard">
      <div className="flex items-center justify-between" style={{ marginBottom: 'var(--space-xs)' }}>
        <h2 className="section-title m-0">My dashboard</h2>
        {presets.length > 1 && (
          <div className="seg-control" role="tablist" aria-label="Dashboard preset">
            {presets.map((p) => (
              <button
                key={p}
                type="button"
                role="tab"
                aria-selected={preset === p}
                className="seg-control__item"
                onClick={() => onPreset(p)}
              >
                {PRESET_LABELS[p]}
              </button>
            ))}
          </div>
        )}
      </div>
      <div className="metric-list">
        {rows.map((m) => (
          <MetricRow key={m.id} metric={m} />
        ))}
      </div>
    </section>
  );
}

/**
 * A monitor: several checks reduced to one state, with the checks one tap
 * away. The state is never colour alone — it is a word first.
 */
function MonitorCard({ monitor }: { monitor: Monitor }) {
  const [open, setOpen] = useState(false);
  return (
    <div className={`monitor monitor--${monitor.tone}`}>
      <button
        type="button"
        className="monitor__head"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
      >
        <span className="monitor__title">{monitor.title}</span>
        <span className="monitor__state">{monitor.state}</span>
        <span className="monitor__detail">{monitor.detail}</span>
      </button>
      {open && monitor.checks && (
        <ul className="monitor__checks">
          {monitor.checks.map((c) => (
            <li key={c.label} className="monitor__check">
              <span className={`monitor__dot ${c.ok ? 'monitor__dot--ok' : 'monitor__dot--flag'}`} aria-hidden="true">
                {c.ok ? '✓' : '!'}
              </span>
              <span className="flex-1 min-w-0">
                <span className="monitor__check-label">{c.label}</span>
                <span className="monitor__check-note">{c.note}</span>
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function Monitors({ monitors }: { monitors: Monitor[] }) {
  if (monitors.length === 0) return null;
  return (
    <div className="monitors" aria-label="Monitors">
      {monitors.map((m) => (
        <MonitorCard key={m.key} monitor={m} />
      ))}
    </div>
  );
}
