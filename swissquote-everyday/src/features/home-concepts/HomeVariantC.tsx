/**
 * HOME — Variant C · "Good to see you"
 *
 * Hypothesis: people do not open a banking app to read a report. They open it
 * to feel in control. So Home opens warmly — by name, on one confident hero
 * — and then talks about momentum: what you put to work, what you are working
 * towards, how long you have kept it up. The three spaces stay one tap away
 * underneath, in the same order, so warmth never costs navigation.
 *
 * The benchmark behind it, and the line this variant deliberately does not
 * cross, are in BENCHMARK.md. The short version: the celebrated things here
 * are saving, contributing and keeping a habit — never trading, never
 * activity for its own sake. No points, no badges, no leaderboards.
 *
 * See README.md in this folder for the full design note.
 */
import { useState } from 'react';
import { swissNumber } from '../../lib/format';
import { useStore } from '../../state/store';
import { availableActions, MOVE_MONEY, ADD_MONEY } from './actions';
import { useHomeData, type Goal } from './homeData';
import { AiLabel, BalanceVisibilityButton, BigAmount, HomeSkeleton, SparkIcon, useGoTo } from './shared';
import { useHomeAiBrief } from './useHomeAi';

const SPACE_ICONS: Record<string, string> = { trade: '↗', bank: '◈', plan: '◎' };

function GoalCard({ goal, onOpen, hidden }: { goal: Goal; onOpen: () => void; hidden: boolean }) {
  const pct = goal.target > 0 ? Math.min(100, (goal.current / goal.target) * 100) : 0;
  return (
    <button type="button" className={`goal ${goal.done ? 'goal--done' : ''}`} onClick={onOpen}>
      <span className="goal__head">
        <span className="goal__title">{goal.title}</span>
        {goal.done ? (
          <span className="goal__badge">Done</span>
        ) : (
          <span className="goal__pct">{Math.round(pct)}%</span>
        )}
      </span>
      <span
        className="progress"
        role="img"
        aria-label={
          hidden
            ? `${Math.round(pct)} per cent there`
            : `${swissNumber(goal.current, 0)} of ${swissNumber(goal.target, 0)} francs`
        }
      >
        <span className="progress__fill" style={{ width: `${pct}%` }} />
      </span>
      <span className="goal__note">{goal.note}</span>
    </button>
  );
}

export function HomeVariantC() {
  const data = useHomeData();
  const { nav } = useStore();
  const goTo = useGoTo();
  const [celebrationOpen, setCelebrationOpen] = useState(true);
  const ai = useHomeAiBrief(data);
  const statement = ai.brief?.statements[0] ?? null;

  // Two actions on the hero, the way most banking apps open. More than two
  // and the hero stops being a hero.
  const heroActions = availableActions(data, [MOVE_MONEY, ADD_MONEY]);
  // A finished goal is celebrated once, at the top. It rejoins the list below
  // as soon as the client dismisses it — the same thing is never said twice.
  const justFinished = data.goals.find((g) => g.done);
  const goals = celebrationOpen ? data.goals.filter((g) => g !== justFinished) : data.goals;
  // The subject of the AI line always comes from the data, never the service.
  const statementTitle = data.today.find((t) => t.id === statement?.itemId)?.title ?? null;
  const { inflow, outflow, putToWork } = data.snapshot;
  const hasMomentum = inflow + outflow + putToWork > 0 || data.streak !== null;

  if (data.loading) return <HomeSkeleton rows={3} />;

  return (
    <div className="screen screen--c">
      {/* ---- Hero: greeting, one number, two actions ------------------ */}
      <section className="hero" aria-label="Your money">
        <div className="hero__top">
          <span className="hero__greeting">
            Good morning, {data.firstName}
            <span className="hero__sub">Here's where you stand</span>
          </span>
        </div>

        <button
          type="button"
          className="hero__amount"
          onClick={() => nav.setWealthOpen(true)}
          aria-label="Total wealth — see the full breakdown"
        >
          <span className="hero__label">Everything, together</span>
          <BigAmount value={data.totalWealth} />
          {data.dayChange && (
            <span className={`hero__delta ${data.dayChange.amount >= 0 ? 'hero__delta--up' : 'hero__delta--down'}`}>
              {data.dayChange.amount >= 0 ? '▲' : '▼'} {data.chf.signed(data.dayChange.amount)} today
            </span>
          )}
        </button>

        <div className="hero__actions">
          {heroActions.map((a) => (
            <button key={a.label} type="button" className="btn btn--inverse" onClick={() => goTo(a.destination)}>
              {a.label}
            </button>
          ))}
          <BalanceVisibilityButton />
        </div>
      </section>

      {/* ---- A moment worth marking. Saving, never trading. ----------- */}
      {justFinished && celebrationOpen && (
        <section className="celebrate" aria-label="Something you finished">
          <span className="celebrate__mark" aria-hidden="true">✓</span>
          <span className="flex-1 min-w-0">
            <span className="celebrate__title">{justFinished.title} — you're there</span>
            <span className="celebrate__body">{justFinished.note}</span>
          </span>
          <button
            type="button"
            className="insight__close"
            onClick={() => setCelebrationOpen(false)}
            aria-label="Dismiss"
          >
            ×
          </button>
        </section>
      )}

      {/* ---- Momentum: the last 30 days, in three numbers ------------- */}
      {hasMomentum && (
      <section className="card momentum" aria-label={`Your last ${data.snapshot.days} days`}>
        <h2 className="section-title m-0">Your last {data.snapshot.days} days · CHF</h2>
        <div className="momentum__row">
          {[
            { label: 'Came in', value: data.snapshot.inflow, key: 'in' },
            { label: 'Went out', value: data.snapshot.outflow, key: 'out' },
            { label: 'Put to work', value: data.snapshot.putToWork, key: 'work' },
          ].map((m) => (
            <span key={m.key} className={`momentum__stat momentum__stat--${m.key}`}>
              <span className="momentum__value">
                {data.balancesHidden ? '•••' : swissNumber(m.value, 0)}
              </span>
              <span className="momentum__label">{m.label}</span>
            </span>
          ))}
        </div>
        {data.streak && (
          <p className="momentum__streak m-0">
            <strong>{data.streak.months} months running</strong>, your salary has gone to work on its own. The next
            one is set for {data.streak.nextRun}.
          </p>
        )}
      </section>
      )}

      {/* ---- What you're working towards ------------------------------ */}
      {goals.length > 0 && (
        <section aria-label="What you're working towards">
          <h2 className="section-title m-0" style={{ marginBottom: 'var(--space-xs)' }}>
            What you're working towards
          </h2>
          <div className="flex flex-col" style={{ gap: 'var(--space-sm)' }}>
            {goals.map((g) => (
              <GoalCard
                key={g.id}
                goal={g}
                hidden={data.balancesHidden}
                onOpen={() => goTo(g.destination)}
              />
            ))}
          </div>
        </section>
      )}

      {/* ---- The three spaces: warm, but in the same place every day --- */}
      <section aria-label="Your Swissquote spaces">
        <h2 className="section-title m-0" style={{ marginBottom: 'var(--space-xs)' }}>
          Where it all sits
        </h2>
        <div className="space-tiles">
          {data.universes.map((u) => (
            <button
              key={u.key}
              type="button"
              className={`space-tile space-tile--${u.key} ${u.owned ? '' : 'space-tile--empty'}`}
              onClick={() => goTo(u.destination)}
            >
              <span className="space-tile__icon" aria-hidden="true">{SPACE_ICONS[u.key]}</span>
              <span className="space-tile__name">{u.title}</span>
              <span className="space-tile__value">
                {u.owned ? data.chf(u.value, 0) : 'Discover'}
              </span>
            </button>
          ))}
        </div>
      </section>

      {/* ---- One friendly line, and a way to ask ---------------------- */}
      <section className="ask" aria-label="Ask Swissquote">
        <div className="ask__head">
          <span className="ask__title">
            <SparkIcon size={14} /> Anything on your mind?
          </span>
          <AiLabel />
        </div>
        {ai.status === 'loading' ? (
          <p className="m-0 caption">One moment…</p>
        ) : (
          <p className="m-0 caption">
            {statement ? (
              <>
                {statementTitle && <strong>{statementTitle}. </strong>}
                {statement.text}
              </>
            ) : (
              `Nothing needs you today — ${data.chf(data.totalWealth)} across your products.`
            )}
          </p>
        )}
        <button type="button" className="btn btn--primary" onClick={() => nav.setTab('search')}>
          Ask Swissquote
        </button>
      </section>
    </div>
  );
}
