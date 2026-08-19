/**
 * Wealth analysis — the AI tile on the analytical Home (Variant D).
 *
 * Three levels of disclosure, and each one is a deliberate cost/benefit:
 *
 *   1. Closed  — one headline and a count. Costs a line of the screen.
 *   2. Open    — the findings, one sentence each, with the action beside them.
 *   3. Proof   — per finding, the figures it was computed from.
 *
 * The findings themselves are computed in the adapter, from the same numbers
 * the charts plot. The service re-words them. It cannot add a finding, drop
 * one, reorder them, or move money: every action here opens a screen where
 * the client decides, with the normal confirmation flow behind it.
 *
 * It is an observation surface, not advice: it says what is true of this
 * position and what the client could look at — never what they should buy.
 */
import { useState } from 'react';
import { useGoTo, SparkIcon } from './shared';
import type { Finding } from './homeData';
import type { AiAnalysis } from './ai';
import type { AiStatus } from './useHomeAi';

function FindingRow({
  finding,
  text,
  index,
}: {
  finding: Finding;
  text: string;
  index: number;
}) {
  const [proofOpen, setProofOpen] = useState(false);
  const goTo = useGoTo();

  return (
    <li className="finding">
      <span className="finding__rank" aria-hidden="true">{index + 1}</span>
      <div className="finding__body">
        <h3 className="finding__headline m-0">{finding.headline}</h3>
        <p className="finding__detail m-0">{text}</p>

        <div className="finding__foot">
          {finding.cta && (
            <button
              type="button"
              className="btn btn--secondary btn--compact"
              onClick={() => goTo(finding.cta!.destination)}
            >
              {finding.cta.label}
            </button>
          )}
          <button
            type="button"
            className="disclosure disclosure--start"
            aria-expanded={proofOpen}
            onClick={() => setProofOpen((v) => !v)}
          >
            <span className="disclosure__chevron" aria-hidden="true">›</span>
            The figures
          </button>
        </div>

        {proofOpen && (
          <dl className="proof">
            {finding.evidence.map((e) => (
              <div key={e.label} className="proof__row">
                <dt className="proof__label">{e.label}</dt>
                <dd className="proof__value amount m-0">{e.value}</dd>
              </div>
            ))}
          </dl>
        )}
      </div>
    </li>
  );
}

/** Three is the tile's job. A fourth finding is a feed, and the charts
 *  below already carry the structural ones. */
const MAX_FINDINGS = 3;

export function WealthAnalysis({
  findings: all,
  analysis,
  status,
}: {
  findings: Finding[];
  analysis: AiAnalysis | null;
  status: AiStatus;
}) {
  const [open, setOpen] = useState(false);
  const findings = all.slice(0, MAX_FINDINGS);
  const rest = all.length - findings.length;
  if (findings.length === 0) return null;

  const textFor = (id: string) =>
    analysis?.statements.find((s) => s.itemId === id)?.text ??
    findings.find((f) => f.id === id)!.detail;

  return (
    <section className={`analysis ${open ? 'analysis--open' : ''}`} aria-label="Wealth analysis">
      {/* Level 1 — the whole tile is the control while it is closed. */}
      <button
        type="button"
        className="analysis__head"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
      >
        <span className="analysis__mark" aria-hidden="true">
          <SparkIcon size={14} />
        </span>
        <span className="flex-1 min-w-0">
          <span className="analysis__title">Wealth analysis</span>
          {/* The teaser is the closed state's whole job; once open, the
              service's summary takes over and this would only repeat it. */}
          {!open && (
            <span className="analysis__summary">
              {status === 'loading'
                ? 'Reading your position…'
                : `${findings.length} things stand out — starting with ${findings[0].teaser}.`}
            </span>
          )}
        </span>
        <span className="analysis__chevron" aria-hidden="true">⌄</span>
      </button>

      {/* Level 2 — the findings themselves. */}
      {open && (
        <div className="analysis__body">
          {status === 'unavailable' && (
            <p className="micro m-0 analysis__degraded">
              The assistant is unavailable. These are the same findings, in the app's own words — they are computed
              from your accounts, not by it.
            </p>
          )}
          {status !== 'loading' && analysis && (
            <p className="m-0 caption">{analysis.summary}</p>
          )}
          <ol className="analysis__list">
            {findings.map((f, i) => (
              <FindingRow key={f.id} finding={f} text={textFor(f.id)} index={i} />
            ))}
          </ol>
          {rest > 0 && (
            <p className="micro m-0">
              {rest} more {rest === 1 ? 'observation is' : 'observations are'} visible in the charts below.
            </p>
          )}
          <p className="micro m-0">
            AI-assisted wording. The findings come from your own balances and history, ranked by what you could act
            on. Nothing here moves money, and none of it is investment advice.
          </p>
        </div>
      )}
    </section>
  );
}
