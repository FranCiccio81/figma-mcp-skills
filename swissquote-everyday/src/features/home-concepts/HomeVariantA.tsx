/**
 * HOME — Variant A · "Universe-first"
 *
 * Hypothesis: clients hold three different mental accounts — what I trade,
 * what I bank with, what I am building — and Home's job is to show each one's
 * state and get out of the way. The screen is a stable map: same three cards,
 * same order, every single day. Nothing here is ranked by a model, so the
 * client can learn the layout once and stop reading it.
 *
 * AI appears exactly once, at the bottom, as a removable insight — it earns
 * the space or it goes.
 *
 * See README.md in this folder for the full design note.
 */
import { useState } from 'react';
import { useStore } from '../../state/store';
import { availableActions, FIXED_ACTIONS } from './actions';
import { useHomeData, type Universe } from './homeData';
import { AiLabel, Amount, BalanceVisibilityButton, BigAmount, HomeSkeleton, useGoTo } from './shared';
import { useHomeAiBrief } from './useHomeAi';

function UniverseCard({ universe, onOpen }: { universe: Universe; onOpen: () => void }) {
  // A space the client has not opened keeps its position and its label, and
  // says so plainly — no balance, no invented number.
  if (!universe.owned) {
    return (
      <button
        type="button"
        className={`universe universe--${universe.key} universe--empty`}
        onClick={onOpen}
      >
        <span className="universe__head">
          <span className="universe__title">{universe.title}</span>
          <span className="universe__open">
            Discover <span aria-hidden="true">→</span>
          </span>
        </span>
        <span className="universe__purpose">{universe.signal.text}</span>
      </button>
    );
  }
  return (
    <button type="button" className={`universe universe--${universe.key}`} onClick={onOpen}>
      <span className="universe__head">
        <span className="universe__title">{universe.title}</span>
        <span className="universe__open">
          Open <span aria-hidden="true">→</span>
        </span>
      </span>
      <span className="universe__value">
        <Amount value={universe.value} />
      </span>
      <span className="universe__purpose">{universe.purpose}</span>
      <span className={`universe__signal universe__signal--${universe.signal.tone}`}>
        <span className="universe__dot" aria-hidden="true" />
        {universe.signal.text}
      </span>
    </button>
  );
}

export function HomeVariantA() {
  const data = useHomeData();
  const { nav } = useStore();
  const goTo = useGoTo();
  const [insightDismissed, setInsightDismissed] = useState(false);
  const [basisOpen, setBasisOpen] = useState(false);
  const ai = useHomeAiBrief(data, !insightDismissed);
  const statement = ai.brief?.statements[0] ?? null;
  // The headline always comes from the data, never from the service.
  const statementTitle = data.today.find((t) => t.id === statement?.itemId)?.title ?? null;

  const actions = availableActions(data, FIXED_ACTIONS);

  if (data.loading) return <HomeSkeleton rows={3} />;

  return (
    <div className="screen">
      <div className="flex items-center justify-between">
        <h1 className="home-greeting m-0">Good morning, {data.firstName}</h1>
        <BalanceVisibilityButton />
      </div>

      {/* One roll-up, and a way into the detail. Not a dashboard. */}
      <button
        type="button"
        className="wealth-summary"
        onClick={() => nav.setWealthOpen(true)}
        aria-label="Total wealth — see the full breakdown"
      >
        <span className="caption">Total wealth</span>
        <BigAmount value={data.totalWealth} />
        {data.dayChange && (
          <span className={`delta amount ${data.dayChange.amount >= 0 ? 'delta--up' : 'delta--down'}`}>
            {data.dayChange.amount >= 0 ? '▲' : '▼'} {data.chf.signed(data.dayChange.amount)} today ·{' '}
            {Math.abs(data.dayChange.pct).toFixed(2)}%
          </span>
        )}
        <span className="micro">
          See the breakdown <span aria-hidden="true">›</span>
        </span>
      </button>

      <nav className="flex flex-col" style={{ gap: 'var(--space-sm)' }} aria-label="Your Swissquote spaces">
        {data.universes.map((u) => (
          <UniverseCard key={u.key} universe={u} onOpen={() => goTo(u.destination)} />
        ))}
      </nav>

      <nav
        className="grid"
        /* Always a four-column grid, so a shorter row starts at the left edge. */
        style={{ gap: 'var(--space-xs)', gridTemplateColumns: 'repeat(4, minmax(0, 1fr))' }}
        aria-label="Quick actions"
      >
        {actions.map((a) => (
          <button key={a.label} type="button" className="quick-action" onClick={() => goTo(a.destination)}>
            <span className="quick-action__icon" aria-hidden="true">
              <svg width="22" height="22" viewBox="0 0 22 22" fill="none" stroke="currentColor" strokeWidth="1.6">
                {a.icon}
              </svg>
            </span>
            {a.label}
          </button>
        ))}
      </nav>

      {/* The one AI moment on this Home. Dismissible, and it stays dismissed. */}
      {!insightDismissed && (
        <section className="insight" aria-label="Today at Swissquote">
          <div className="insight__head">
            <span className="insight__title">Today at Swissquote</span>
            <AiLabel />
            <button
              type="button"
              className="insight__close"
              onClick={() => setInsightDismissed(true)}
              aria-label="Remove this card"
            >
              ×
            </button>
          </div>

          {ai.status === 'loading' && <p className="m-0 caption">Looking at your accounts…</p>}

          {ai.status !== 'loading' && statement && (
            <>
              <p className="m-0 insight__text">
                {statementTitle && <strong>{statementTitle}. </strong>}
                {statement.text}
              </p>
              {ai.status === 'unavailable' && (
                <p className="m-0 micro insight__degraded">
                  The assistant is unavailable right now. This is straight from your accounts instead.
                </p>
              )}
              <button
                type="button"
                className="disclosure"
                aria-expanded={basisOpen}
                onClick={() => setBasisOpen((v) => !v)}
              >
                <span className="disclosure__chevron" aria-hidden="true">›</span>
                Where this comes from
              </button>
              {basisOpen && (
                <p className="m-0 micro">
                  {statement.basis}. Nothing moves on its own — anything you decide to do goes through the usual
                  confirmation.
                </p>
              )}
            </>
          )}

          {ai.status !== 'loading' && !statement && (
            <p className="m-0 caption">
              Nothing to flag today. You hold {data.chf(data.totalWealth)} across your products.
            </p>
          )}
        </section>
      )}
    </div>
  );
}
