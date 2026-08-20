/**
 * HOME — Variant D · "The dashboard"
 *
 * Hypothesis: a client with roughly a million francs across five products
 * does not want to be greeted, told what to do, or congratulated. They want
 * the position: what it is worth, how it got there, how it is split, and
 * whether the month was net positive.
 *
 * Structure, after a round of iteration: the screen is not a stack of cards
 * but **three subjects**, each with its own ring, its own colour and its own
 * chart —
 *
 *   Cash & everyday (Bank orange) · Markets (Trade blue) · The long view
 *   (Plan green)
 *
 * — under one headline (total wealth and its trend) and one summary (the
 * wealth-analysis tile). The rings used to sit in a sticky strip; they were
 * crowding the top and saying nothing about where to look, so each one now
 * heads the section it measures.
 *
 * Benchmarked on Empower, Fidelity Full View, Monarch and Copilot, with the
 * ring/row/monitor grammar taken from health dashboards — see BENCHMARK.md.
 * Charts follow the dataviz procedure: form by the data's job, validated
 * palettes, direct labels, a hover layer and a table view.
 *
 * See README.md in this folder for the full design note.
 */
import { useState } from 'react';
import { swissNumber } from '../../lib/format';
import { useStore } from '../../state/store';
import { AllocationBar, NetFlowBars, TrendChart } from './charts';
import { MetricSections, Monitors } from './DashboardRows';
import { useHomeData, type MetricPreset, type TrendPoint } from './homeData';
import { BalanceVisibilityButton, BigAmount, HomeSkeleton, useGoTo } from './shared';
import { useHomeAiAnalysis } from './useHomeAi';
import { WealthAnalysis } from './WealthAnalysis';

/** Windows the client can put the position in. Bounded by the history held. */
const RANGES = [
  { key: '1W', days: 7 },
  { key: '1M', days: 30 },
  { key: '3M', days: 90 },
] as const;

type RangeKey = (typeof RANGES)[number]['key'];

function Stat({ label, value, note }: { label: string; value: string; note: string }) {
  return (
    <div className="stat">
      <span className="stat__label">{label}</span>
      <span className="stat__value">{value}</span>
      <span className="stat__note">{note}</span>
    </div>
  );
}

export function HomeVariantD() {
  const data = useHomeData();
  const { nav } = useStore();
  const goTo = useGoTo();
  const [range, setRange] = useState<RangeKey>('3M');
  const [tableOpen, setTableOpen] = useState(false);
  const ai = useHomeAiAnalysis(data);

  const a = data.analytics;
  const days = RANGES.find((r) => r.key === range)!.days;
  const window: TrendPoint[] = a.trend.slice(Math.max(0, a.trend.length - days - 1));
  const first = window[0]?.value ?? data.totalWealth;
  const change = data.totalWealth - first;
  const changePct = first > 0 ? (change / first) * 100 : 0;

  // Which dashboard this client gets. Both are offered when they hold both.
  const presets: MetricPreset[] = [];
  if (a.metrics.some((m) => m.presets.includes('everyday'))) presets.push('everyday');
  if (a.metrics.some((m) => m.presets.includes('trader'))) presets.push('trader');
  const [preset, setPreset] = useState<MetricPreset>('everyday');
  const activePreset = presets.includes(preset) ? preset : (presets[0] ?? 'everyday');

  if (data.loading) return <HomeSkeleton rows={3} />;

  /* ---- The two charts that belong to a subject rather than to the page. */

  const cashFlow = a.months.length > 0 && (
    <>
      <h4 className="dsection__sub m-0">Net, by month</h4>
      <div className="flow-triad">
        <Stat
          label={`In · ${a.windowDays}d`}
          value={data.balancesHidden ? '•••' : swissNumber(data.snapshot.inflow, 0)}
          note="CHF"
        />
        <Stat
          label={`Out · ${a.windowDays}d`}
          value={data.balancesHidden ? '•••' : swissNumber(data.snapshot.outflow, 0)}
          note="CHF"
        />
        <Stat
          label="Net"
          value={
            data.balancesHidden
              ? '•••'
              : `${data.snapshot.inflow - data.snapshot.outflow >= 0 ? '+' : '−'}${swissNumber(
                  Math.abs(data.snapshot.inflow - data.snapshot.outflow),
                  0,
                )}`
          }
          note="CHF"
        />
      </div>
      <NetFlowBars months={a.months} hidden={data.balancesHidden} />
      <div className="flow-legend">
        <span className="flow-legend__item">
          <span className="flow-legend__swatch flow-legend__swatch--up" aria-hidden="true" />
          Above the line: more came in than went out
        </span>
        <span className="flow-legend__item">
          <span className="flow-legend__swatch flow-legend__swatch--down" aria-hidden="true" />
          Below: more went out
        </span>
      </div>
      {a.months.some((m) => m.partial) && (
        <p className="micro m-0">
          * Not a full month: the oldest one starts where your history does, and this one is still running.
        </p>
      )}
    </>
  );

  const allocation = (
    <>
      <h4 className="dsection__sub m-0" style={{ marginBottom: 'var(--space-sm)' }}>
        How it's split
      </h4>
      <AllocationBar slices={a.allocation} hidden={data.balancesHidden} />
      <div style={{ marginTop: 'var(--space-xs)' }}>
        {a.allocation.map((s) => (
          <button key={s.key} type="button" className="alloc-row" onClick={() => goTo(s.destination)}>
            <span className={`alloc-row__swatch alloc-row__swatch--${s.key}`} aria-hidden="true" />
            <span className="flex-1 min-w-0">{s.label}</span>
            <span className="alloc-row__pct amount">{s.pct.toFixed(1)}%</span>
            <span className="alloc-row__value amount">{data.chf(s.value, 0)}</span>
            <span className="product-row__chevron" aria-hidden="true">›</span>
          </button>
        ))}
      </div>
    </>
  );

  return (
    <div className="screen">
      {/* ---- Position: one number, its move, and the line behind it ---- */}
      <section className="card position" aria-label="Total wealth">
        <div className="flex items-start justify-between">
          <button
            type="button"
            className="flex flex-col items-start"
            style={{ gap: 'var(--space-2xs)' }}
            onClick={() => nav.setWealthOpen(true)}
            aria-label="Total wealth — see the full breakdown"
          >
            <span className="caption">Total wealth</span>
            <BigAmount value={data.totalWealth} />
            <span className={`amount delta ${change >= 0 ? 'delta--up' : 'delta--down'}`}>
              {change >= 0 ? '▲' : '▼'} {data.chf.signed(change)} · {changePct >= 0 ? '+' : '−'}
              {Math.abs(changePct).toFixed(2)}%{' '}
              {range === '1W' ? 'over 7 days' : range === '1M' ? 'over 30 days' : 'over 3 months'}
            </span>
          </button>
          <BalanceVisibilityButton />
        </div>

        <div className="chip-row" role="tablist" aria-label="Time range" style={{ margin: 'var(--space-sm) 0' }}>
          {RANGES.map((r) => (
            <button
              key={r.key}
              type="button"
              role="tab"
              aria-selected={range === r.key}
              className="chip"
              onClick={() => setRange(r.key)}
            >
              {r.key}
            </button>
          ))}
        </div>

        <TrendChart points={window} hidden={data.balancesHidden} label={`Total wealth over the last ${days} days`} />
        <p className="micro m-0">
          Built from money in and out of your accounts. Market performance before today is not in this line
          ⟨valuation history TO CONFIRM⟩.
        </p>
      </section>

      {/* ---- What stands out — the summary, before the evidence -------- */}
      <WealthAnalysis findings={a.findings} analysis={ai.analysis} status={ai.status} />

      {/* ---- Monitors: checks reduced to one state each ---------------- */}
      <Monitors monitors={a.monitors} />

      {/* ---- My dashboard: three coloured subjects, each headed by its
              own ring and carrying the chart that belongs to it. --------- */}
      <MetricSections
        metrics={a.metrics}
        rings={a.rings}
        presets={presets}
        preset={activePreset}
        onPreset={setPreset}
        extras={{ cash: cashFlow || undefined, longterm: allocation }}
      />

      {/* ---- The same numbers, as text -------------------------------- */}
      <section aria-label="The numbers as a table">
        <button
          type="button"
          className="disclosure disclosure--start"
          aria-expanded={tableOpen}
          onClick={() => setTableOpen((v) => !v)}
        >
          <span className="disclosure__chevron" aria-hidden="true">›</span>
          Show the numbers as a table
        </button>
        {tableOpen && (
          <div className="card" style={{ marginTop: 'var(--space-xs)' }}>
            <table className="data-table">
              <caption className="sr-only">Wealth split and monthly net cash flow</caption>
              <tbody>
                {a.allocation.map((s) => (
                  <tr key={s.key}>
                    <th scope="row">{s.label}</th>
                    <td className="amount">{data.chf(s.value, 0)}</td>
                    <td className="amount">{s.pct.toFixed(1)}%</td>
                  </tr>
                ))}
                {a.months.map((m) => (
                  <tr key={m.key}>
                    <th scope="row">
                      {m.label}
                      {m.partial ? ' (so far)' : ''}
                    </th>
                    <td className="amount">in {data.balancesHidden ? '•••' : swissNumber(m.inflow, 0)}</td>
                    <td className="amount">out {data.balancesHidden ? '•••' : swissNumber(m.outflow, 0)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
