/**
 * HOME — Variant D · "The dashboard"
 *
 * Hypothesis: a client with roughly a million francs across five products
 * does not want to be greeted, told what to do, or congratulated. They want
 * the position: what it is worth, how it got there, how it is split, and
 * whether the month was net positive. Home becomes an analytical cockpit
 * whose rows are also the way into Trade, Bank and Plan.
 *
 * Benchmarked on Empower's net-worth trajectory, Fidelity Full View's
 * customisable position dashboard, Monarch's dashboard composition and
 * Copilot's income / spending / net triad — see BENCHMARK.md.
 *
 * Every chart follows the dataviz procedure: form chosen by the data's job,
 * palettes run through the six-checks validator, direct labels as secondary
 * encoding, a hover layer, and a table view of the same numbers.
 *
 * See README.md in this folder for the full design note.
 */
import { useState } from 'react';
import { swissNumber } from '../../lib/format';
import { useStore } from '../../state/store';
import { AllocationBar, NetFlowBars, TrendChart } from './charts';
import { useHomeData, type TrendPoint } from './homeData';
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

function Stat({
  label,
  value,
  note,
}: {
  label: string;
  value: string;
  note: string;
}) {
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

  if (data.loading) return <HomeSkeleton rows={3} />;

  return (
    <div className="screen">
      {/* ---- Position ------------------------------------------------- */}
      <section aria-label="Total wealth">
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
          </button>
          <BalanceVisibilityButton />
        </div>
        <p className={`m-0 amount delta ${change >= 0 ? 'delta--up' : 'delta--down'}`}>
          {change >= 0 ? '▲' : '▼'} {data.chf.signed(change)} · {changePct >= 0 ? '+' : '−'}
          {Math.abs(changePct).toFixed(2)}% over {range === '1W' ? '7 days' : range === '1M' ? '30 days' : '3 months'}
        </p>
      </section>

      {/* ---- What stands out — closed by default, so density stays low.
              It reads as an executive summary: conclusions first, with the
              charts below as the evidence. ---------------------------------- */}
      <WealthAnalysis findings={a.findings} analysis={ai.analysis} status={ai.status} />

      {/* ---- Wealth over time ----------------------------------------- */}
      <section className="card" aria-label="Wealth over time">
        <div className="chip-row" role="tablist" aria-label="Time range" style={{ marginBottom: 'var(--space-sm)' }}>
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
        <TrendChart
          points={window}
          hidden={data.balancesHidden}
          label={`Total wealth over the last ${days} days`}
        />
        <p className="micro m-0" style={{ marginTop: 'var(--space-xs)' }}>
          Built from money in and out of your accounts. Market performance before today is not in this line
          ⟨valuation history TO CONFIRM⟩.
        </p>
      </section>

      {/* ---- How it is split ------------------------------------------ */}
      <section className="card" aria-label="How your wealth is split">
        <h2 className="section-title m-0" style={{ marginBottom: 'var(--space-sm)' }}>
          How it's split
        </h2>
        <AllocationBar slices={a.allocation} hidden={data.balancesHidden} />
        <div style={{ marginTop: 'var(--space-sm)' }}>
          {a.allocation.map((s) => (
            <button
              key={s.key}
              type="button"
              className="alloc-row"
              onClick={() => goTo(s.destination)}
            >
              <span className={`alloc-row__swatch alloc-row__swatch--${s.key}`} aria-hidden="true" />
              <span className="flex-1 min-w-0">{s.label}</span>
              <span className="alloc-row__pct amount">{s.pct.toFixed(1)}%</span>
              <span className="alloc-row__value amount">{data.chf(s.value, 0)}</span>
              <span className="product-row__chevron" aria-hidden="true">›</span>
            </button>
          ))}
        </div>
      </section>

      {/* ---- Cash flow ------------------------------------------------- */}
      {a.months.length > 0 && (
        <section className="card" aria-label="Money in and out, by month">
          <h2 className="section-title m-0">Net, by month</h2>
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
        </section>
      )}

      {/* ---- Ratios ---------------------------------------------------- */}
      <section className="card" aria-label="Ratios">
        <h2 className="section-title m-0" style={{ marginBottom: 'var(--space-sm)' }}>
          Where you stand
        </h2>
        <div className="ratio-grid">
          <Stat
            label="Invested"
            value={`${a.investedShare.toFixed(0)}%`}
            note="of your wealth, rather than held as cash"
          />
          <Stat
            label="Months of cover"
            value={a.monthsOfCover.toFixed(1)}
            note={`liquid cash ÷ ${data.chf(a.typicalSpend, 0)} typical monthly spending`}
          />
          <Stat
            label="Put to work"
            value={`${a.putToWorkRate.toFixed(0)}%`}
            note={`of what came in over ${a.windowDays} days went to savings or investments`}
          />
        </div>
      </section>

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
                    <td className="amount">
                      in {data.balancesHidden ? '•••' : swissNumber(m.inflow, 0)}
                    </td>
                    <td className="amount">
                      out {data.balancesHidden ? '•••' : swissNumber(m.outflow, 0)}
                    </td>
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
