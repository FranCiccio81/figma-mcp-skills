/**
 * LiquidityForecastChart — new component introduced by this concept (§7).
 *
 * 30-day projected balance: one line (typical scenario) over a shaded
 * uncertainty band down to the high-spend scenario, with known events marked
 * on the x-axis. One series → no legend box; the title names it. Numbers are
 * never conveyed by chart position alone — key values are rendered as text.
 */
import { useState } from 'react';
import { money, shortDate, swissNumber } from '../lib/format';
import type { Forecast } from '../state/forecast';

const W = 340;
const H = 150;
const PAD_L = 8;
const PAD_R = 8;
const PAD_T = 10;
const PAD_B = 26;

export function LiquidityForecastChart({ forecast, minBalance }: { forecast: Forecast; minBalance: number }) {
  const [picked, setPicked] = useState<number | null>(null);
  const pts = forecast.points;
  const values = pts.flatMap((p) => [p.typical, p.high]);
  // Fit the domain to the projection so its shape stays readable; pull the
  // minimum-balance line in only when it is near the data, otherwise the
  // whole story flattens against an axis stretched to a far-away floor.
  const dataMin = Math.min(...values);
  const dataMax = Math.max(...values);
  const pad = Math.max((dataMax - dataMin) * 0.15, 300);
  const minRelevant = minBalance > dataMin - 3 * pad;
  const max = dataMax + pad;
  const min = (minRelevant ? Math.min(dataMin, minBalance) : dataMin) - pad;

  const x = (i: number) => PAD_L + (i / (pts.length - 1)) * (W - PAD_L - PAD_R);
  const y = (v: number) => PAD_T + (1 - (v - min) / (max - min)) * (H - PAD_T - PAD_B);

  const linePath = pts.map((p, i) => `${i === 0 ? 'M' : 'L'}${x(i).toFixed(1)},${y(p.typical).toFixed(1)}`).join(' ');
  const bandPath =
    pts.map((p, i) => `${i === 0 ? 'M' : 'L'}${x(i).toFixed(1)},${y(p.typical).toFixed(1)}`).join(' ') +
    ' ' +
    [...pts].reverse().map((p, i) => `${i === 0 ? 'L' : 'L'}${x(pts.length - 1 - i).toFixed(1)},${y(p.high).toFixed(1)}`).join(' ') +
    ' Z';

  const events = pts.map((p, i) => ({ ...p, i })).filter((p) => p.event);
  const lowestTypical = pts.reduce((a, b) => (b.typical < a.typical ? b : a));
  const sel = picked !== null ? pts[picked] : null;

  return (
    <figure className="m-0">
      <svg
        viewBox={`0 0 ${W} ${H}`}
        role="img"
        aria-label={`Projected Everyday balance over the next 30 days. Typical scenario reaches its lowest point, ${money(lowestTypical.typical)}, on ${shortDate(lowestTypical.day)}. In a high-spend scenario the balance runs lower — the shaded band shows the range.`}
        style={{ width: '100%', height: 'auto', display: 'block', touchAction: 'manipulation' }}
        onPointerMove={(e) => {
          const rect = e.currentTarget.getBoundingClientRect();
          const rel = ((e.clientX - rect.left) / rect.width) * W;
          const i = Math.round(((rel - PAD_L) / (W - PAD_L - PAD_R)) * (pts.length - 1));
          setPicked(Math.max(0, Math.min(pts.length - 1, i)));
        }}
        onPointerLeave={() => setPicked(null)}
      >
        {/* recessive grid + minimum-balance line (only when near the data) */}
        <line x1={PAD_L} x2={W - PAD_R} y1={H - PAD_B} y2={H - PAD_B} stroke="var(--color-dataviz-grid)" strokeWidth="1" />
        {minRelevant && (
          <line
            x1={PAD_L}
            x2={W - PAD_R}
            y1={y(minBalance)}
            y2={y(minBalance)}
            stroke="var(--color-feedback-warning)"
            strokeWidth="1"
            strokeDasharray="3 4"
          />
        )}
        <path d={bandPath} fill="var(--color-dataviz-band)" stroke="none" />
        <path d={linePath} fill="none" stroke="var(--color-dataviz-line)" strokeWidth="2" />
        {events.map((e) => (
          <g key={`${e.day}-${e.event}`}>
            <line x1={x(e.i)} x2={x(e.i)} y1={y(e.typical)} y2={H - PAD_B + 4} stroke="var(--color-dataviz-grid)" strokeWidth="1" />
            <circle cx={x(e.i)} cy={y(e.typical)} r="4" fill="var(--color-dataviz-line)" stroke="var(--color-surface-default)" strokeWidth="2" />
            <text
              x={x(e.i)}
              y={H - PAD_B + 16}
              textAnchor={e.i > pts.length - 6 ? 'end' : e.i < 5 ? 'start' : 'middle'}
              fontSize="9"
              fill="var(--color-text-secondary)"
            >
              {e.event}
            </text>
          </g>
        ))}
        {sel && picked !== null && (
          <g>
            <line x1={x(picked)} x2={x(picked)} y1={PAD_T} y2={H - PAD_B} stroke="var(--color-border-strong)" strokeWidth="1" />
            <circle cx={x(picked)} cy={y(sel.typical)} r="4" fill="var(--color-dataviz-line)" stroke="var(--color-surface-default)" strokeWidth="2" />
          </g>
        )}
      </svg>
      <figcaption className="caption" aria-live="polite">
        {sel
          ? `${shortDate(sel.day)} — likely around CHF ${swissNumber(sel.typical, 0)} (high-spend: CHF ${swissNumber(sel.high, 0)})`
          : minRelevant
            ? `Lowest likely point: ${money(lowestTypical.typical)} on ${shortDate(lowestTypical.day)} · dashed line = your CHF ${swissNumber(minBalance, 0)} minimum`
            : `Lowest likely point: ${money(lowestTypical.typical, 'CHF', 0)} on ${shortDate(lowestTypical.day)} — comfortably above your CHF ${swissNumber(minBalance, 0)} minimum`}
      </figcaption>
    </figure>
  );
}

/** Home-screen teaser sparkline of the typical path — decorative; the text beside it carries the value. */
export function ForecastSparkline({ forecast }: { forecast: Forecast }) {
  const pts = forecast.points;
  const values = pts.map((p) => p.typical);
  const max = Math.max(...values);
  const min = Math.min(...values, 0);
  const w = 92;
  const h = 40;
  const x = (i: number) => 2 + (i / (pts.length - 1)) * (w - 8);
  const y = (v: number) => 4 + (1 - (v - min) / (max - min || 1)) * (h - 8);
  const d = pts.map((p, i) => `${i === 0 ? 'M' : 'L'}${x(i).toFixed(1)},${y(p.typical).toFixed(1)}`).join(' ');
  const last = pts[pts.length - 1];
  return (
    <svg viewBox={`0 0 ${w} ${h}`} width={w} height={h} aria-hidden="true" style={{ flex: 'none' }}>
      <path d={d} fill="none" stroke="var(--color-chart-line)" strokeWidth="2" strokeLinecap="round" />
      <circle
        cx={x(pts.length - 1)}
        cy={y(last.typical)}
        r="3.5"
        fill="var(--color-chart-line)"
        stroke="var(--color-surface-default)"
        strokeWidth="2"
      />
    </svg>
  );
}
