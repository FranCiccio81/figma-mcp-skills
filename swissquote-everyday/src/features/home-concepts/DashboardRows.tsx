/**
 * "My dashboard" — the analytical Home's metric list, and the monitors above
 * it.
 *
 * The rows follow the health-dashboard pattern: one metric per line, today's
 * figure large, **what it usually is** underneath. A number without its
 * baseline is trivia; with one it is a judgement the client can make in a
 * second.
 *
 * Two departures, both required by the domain:
 *   • Direction is not sentiment. Spending up is not good news, so the arrow
 *     shows the move and the colour shows whether it is welcome — with the
 *     accessible name saying both, since colour alone never carries meaning.
 *   • Which rows appear is a preset, not a preference buried in settings: an
 *     everyday client and a trader want different dashboards from one account.
 *
 * Structure: the rows are grouped into the dashboard's three subjects, each
 * one headed by its own ring and carrying the colour of the space it belongs
 * to — Bank orange, Trade blue, Plan green, the same three hues used in the
 * allocation bar and on every other Home. That is what makes the list
 * scannable: you find the section by colour, then the row by label.
 */
import { useState } from 'react';
import { RingGauge } from './charts';
import type { Metric, MetricPreset, Monitor, Ring, SectionKey } from './homeData';
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

/** Section order is fixed: cash first, because it is what constrains you. */
const SECTIONS: { key: SectionKey; title: string }[] = [
  { key: 'cash', title: 'Cash & everyday' },
  { key: 'markets', title: 'Markets' },
  { key: 'longterm', title: 'The long view' },
];

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

/**
 * One section: its ring, its rows, and — where there is one — the chart that
 * belongs to this subject rather than floating in a stack of its own.
 */
function Section({
  section,
  ring,
  metrics,
  children,
}: {
  section: { key: SectionKey; title: string };
  ring?: Ring;
  metrics: Metric[];
  children?: React.ReactNode;
}) {
  const goTo = useGoTo();
  if (metrics.length === 0 && !children) return null;

  return (
    <section className={`dsection dsection--${section.key}`} aria-label={section.title}>
      <header className="dsection__head">
        {ring && <RingGauge ring={ring} onOpen={() => goTo(ring.destination)} />}
        <span className="flex-1 min-w-0">
          <h3 className="dsection__title m-0">{section.title}</h3>
          {/* The ring's own label lives here rather than under the dial, so
              the header stays one line tall and reads as a sentence. */}
          {ring && (
            <span className="dsection__caption">
              {ring.label} · {ring.caption}
            </span>
          )}
        </span>
      </header>
      {metrics.length > 0 && (
        <div className="dsection__rows">
          {metrics.map((m) => (
            <MetricRow key={m.id} metric={m} />
          ))}
        </div>
      )}
      {children && <div className="dsection__extra">{children}</div>}
    </section>
  );
}

export function MetricSections({
  metrics,
  rings,
  presets,
  preset,
  onPreset,
  extras,
}: {
  metrics: Metric[];
  rings: Ring[];
  presets: MetricPreset[];
  preset: MetricPreset;
  onPreset: (p: MetricPreset) => void;
  /** A chart to hang under a given section, keyed by section. */
  extras?: Partial<Record<SectionKey, React.ReactNode>>;
}) {
  const rows = metrics.filter((m) => m.presets.includes(preset));

  return (
    <section aria-label="My dashboard">
      <div className="flex items-center justify-between" style={{ marginBottom: 'var(--space-sm)' }}>
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

      <div className="flex flex-col" style={{ gap: 'var(--space-md)' }}>
        {SECTIONS.map((sec) => (
          <Section
            key={sec.key}
            section={sec}
            ring={rings.find((r) => r.section === sec.key)}
            metrics={rows.filter((m) => m.section === sec.key)}
          >
            {extras?.[sec.key]}
          </Section>
        ))}
      </div>
    </section>
  );
}

/**
 * A monitor: several checks reduced to one state, with the checks one tap
 * away. The state is a word first, never a colour alone.
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
