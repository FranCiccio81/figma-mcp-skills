/**
 * Charts for the analytical Home (Variant D).
 *
 * Plain inline SVG on the project's tokens — no charting library, nothing
 * fetched. Three forms, each chosen for the job its data does:
 *
 *   • wealth over time      → area + line, one series, so no legend: the
 *                             title names it. Crosshair and tooltip.
 *   • allocation            → one 100% stacked bar, three categorical hues in
 *                             fixed order, 2px surface gaps, direct labels.
 *   • net cash flow         → diverging columns around a zero baseline. Cool
 *                             pole up, warm pole down — and direction carries
 *                             the meaning too, so it is never colour alone.
 *
 * Palettes were validated with the dataviz six-checks script, not eyeballed:
 * spaces trio (#3d7ff5,#ee4d22,#0f9d63) worst adjacent CVD ΔE 9.8, normal
 * 30.6; flow pair (#2a5cc0,#b4438f) ΔE 8.6 / 22.6; all ≥ 3:1 on white. Both
 * carry direct labels as secondary encoding.
 */
import { useState, type PointerEvent } from 'react';
import { shortDate, swissNumber } from '../../lib/format';
import type { AllocationSlice, MonthFlow, TrendPoint } from './homeData';

const W = 320;

/* ------------------------------------------------------------------ */
/* Wealth over time                                                    */
/* ------------------------------------------------------------------ */

export function TrendChart({
  points,
  hidden,
  label,
}: {
  points: TrendPoint[];
  hidden: boolean;
  label: string;
}) {
  const H = 120;
  const [active, setActive] = useState<number | null>(null);
  if (points.length < 2) return null;

  const values = points.map((p) => p.value);
  // Data-fitted domain with a little headroom: forcing zero would flatten a
  // line whose whole story is the last 8% of its range.
  const min = Math.min(...values);
  const max = Math.max(...values);
  const pad = (max - min) * 0.12 || 1;
  const lo = min - pad;
  const hi = max + pad;

  const x = (i: number) => (i / (points.length - 1)) * W;
  const y = (v: number) => H - ((v - lo) / (hi - lo)) * H;

  const line = points.map((p, i) => `${i === 0 ? 'M' : 'L'}${x(i).toFixed(1)},${y(p.value).toFixed(1)}`).join(' ');
  const area = `${line} L${W},${H} L0,${H} Z`;

  const onMove = (e: PointerEvent<HTMLDivElement>) => {
    const box = e.currentTarget.getBoundingClientRect();
    const ratio = Math.min(1, Math.max(0, (e.clientX - box.left) / box.width));
    setActive(Math.round(ratio * (points.length - 1)));
  };

  const p = active !== null ? points[active] : null;

  return (
    <div
      className="chart"
      onPointerMove={onMove}
      onPointerDown={onMove}
      onPointerLeave={() => setActive(null)}
    >
      <svg viewBox={`0 0 ${W} ${H}`} className="chart__svg" role="img" aria-label={label}>
        <path d={area} fill="var(--color-chart-fill)" />
        <path d={line} fill="none" stroke="var(--color-chart-line)" strokeWidth="2" strokeLinejoin="round" />
        {p && active !== null && (
          <g>
            <line
              x1={x(active)}
              x2={x(active)}
              y1="0"
              y2={H}
              stroke="var(--color-border-default)"
              strokeWidth="1"
            />
            {/* 2px surface ring so the marker reads over the fill */}
            <circle cx={x(active)} cy={y(p.value)} r="5" fill="var(--color-surface-default)" />
            <circle cx={x(active)} cy={y(p.value)} r="3.5" fill="var(--color-chart-line)" />
          </g>
        )}
      </svg>

      {p ? (
        <div className="chart__tip" style={{ left: `${(x(active!) / W) * 100}%` }}>
          <span className="chart__tip-date">{shortDate(p.day)}</span>
          <span className="chart__tip-value">{hidden ? 'CHF •••' : `CHF ${swissNumber(p.value, 0)}`}</span>
        </div>
      ) : (
        <div className="chart__axis">
          <span>{shortDate(points[0].day)}</span>
          <span>{shortDate(points[points.length - 1].day)}</span>
        </div>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Allocation                                                          */
/* ------------------------------------------------------------------ */

export function AllocationBar({ slices, hidden }: { slices: AllocationSlice[]; hidden: boolean }) {
  const total = slices.reduce((s, x) => s + x.value, 0);
  if (total <= 0) return null;
  return (
    <div
      className="alloc"
      role="img"
      aria-label={slices
        .map((s) => `${s.label} ${Math.round(s.pct)} per cent${hidden ? '' : `, ${swissNumber(s.value, 0)} francs`}`)
        .join('; ')}
    >
      {slices.map((s) => (
        <span
          key={s.key}
          className={`alloc__seg alloc__seg--${s.key}`}
          style={{ flexGrow: s.value }}
          title={`${s.label} ${Math.round(s.pct)}%`}
        />
      ))}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Net cash flow per month                                             */
/* ------------------------------------------------------------------ */

export function NetFlowBars({
  months,
  hidden,
}: {
  months: MonthFlow[];
  hidden: boolean;
}) {
  const [active, setActive] = useState<string | null>(null);
  if (months.length === 0) return null;

  const peak = Math.max(...months.map((m) => Math.abs(m.net)), 1);

  return (
    <div className="flowbars">
      {months.map((m) => {
        const share = Math.abs(m.net) / peak;
        const up = m.net >= 0;
        const open = active === m.key;
        return (
          <button
            key={m.key}
            type="button"
            className={`flowbar ${open ? 'flowbar--active' : ''}`}
            onPointerEnter={() => setActive(m.key)}
            onPointerLeave={() => setActive(null)}
            onClick={() => setActive(open ? null : m.key)}
            aria-label={`${m.label}${m.partial ? ', partial month' : ''}: ${
              hidden ? 'hidden' : `${up ? 'plus' : 'minus'} ${swissNumber(Math.abs(m.net), 0)} francs`
            }`}
          >
            <span className="flowbar__half flowbar__half--up">
              {up && (
                <span
                  className={`flowbar__mark flowbar__mark--up ${m.partial ? 'flowbar__mark--partial' : ''}`}
                  style={{ height: `${Math.max(share * 100, 4)}%` }}
                />
              )}
            </span>
            <span className="flowbar__zero" aria-hidden="true" />
            <span className="flowbar__half flowbar__half--down">
              {!up && (
                <span
                  className={`flowbar__mark flowbar__mark--down ${m.partial ? 'flowbar__mark--partial' : ''}`}
                  style={{ height: `${Math.max(share * 100, 4)}%` }}
                />
              )}
            </span>
            <span className="flowbar__label">
              {m.label}
              {m.partial && '*'}
            </span>
            {/* One month can dwarf the others — a bonus lands and the rest
                become slivers. The scale stays linear and honest; the value
                is written under every bar so the small ones still read. */}
            <span className="flowbar__value">
              {hidden ? '•••' : `${up ? '+' : '−'}${swissNumber(Math.abs(m.net), 0)}`}
            </span>
            {open && (
              <span className="flowbar__tip">
                {hidden ? 'CHF •••' : `${up ? '+' : '−'}${swissNumber(Math.abs(m.net), 0)}`}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Ring gauge — the daily state, one arc each                          */
/* ------------------------------------------------------------------ */

