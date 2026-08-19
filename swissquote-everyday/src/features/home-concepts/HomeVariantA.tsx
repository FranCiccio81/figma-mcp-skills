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
import { useHomeData, type Universe } from './homeData';
import { AiLabel, Amount, BalanceVisibilityButton, BigAmount, HomeSkeleton, useGoTo } from './shared';
import { useHomeAiBrief } from './useHomeAi';

function UniverseCard({ universe, onOpen }: { universe: Universe; onOpen: () => void }) {
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

/**
 * Quick actions — the four things clients start from, not a feature menu.
 * `needs` keeps a client from being offered a space they do not have.
 */
const ACTIONS = [
  {
    label: 'Move money',
    needs: 'bank' as const,
    destination: { tab: 'bank' as const, screen: 'autoCover' as const },
    icon: (
      <>
        <path d="M7 3.5v15M7 18.5l-3-3M7 18.5l3-3" strokeLinecap="round" strokeLinejoin="round" />
        <path d="M15 18.5v-15M15 3.5l-3 3M15 3.5l3 3" strokeLinecap="round" strokeLinejoin="round" />
      </>
    ),
  },
  {
    label: 'Add money',
    needs: null,
    destination: { tab: 'bank' as const, screen: 'home' as const },
    icon: <path d="M11 4.5v13M4.5 11h13" strokeLinecap="round" />,
  },
  {
    label: 'Exchange',
    needs: 'bank' as const,
    destination: { tab: 'bank' as const, screen: 'pay' as const },
    icon: <path d="M4 8h11l-3-3M18 14H7l3 3" strokeLinecap="round" strokeLinejoin="round" />,
  },
  {
    label: 'Invest',
    needs: 'plan' as const,
    destination: { tab: 'plan' as const },
    icon: <path d="M4 15.5 9 10l3.5 3L18 6.5M18 6.5h-4M18 6.5v4" strokeLinecap="round" strokeLinejoin="round" />,
  },
];

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

  // A client without a Bank space is not offered bank actions.
  const has = (key: string) => data.universes.some((u) => u.key === key);
  const actions = ACTIONS.filter((a) => a.needs === null || has(a.needs)).map((a) =>
    a.label === 'Add money' && !has('bank')
      ? { ...a, destination: { tab: 'trade' as const, screen: undefined } }
      : a,
  );

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
        <span className="micro">
          Across {data.universes.length} {data.universes.length === 1 ? 'space' : 'spaces'} · see the breakdown{' '}
          <span aria-hidden="true">›</span>
        </span>
      </button>

      <nav className="flex flex-col" style={{ gap: 'var(--space-sm)' }} aria-label="Your Swissquote spaces">
        {data.universes.map((u) => (
          <UniverseCard key={u.key} universe={u} onOpen={() => goTo(u.destination)} />
        ))}
      </nav>

      <nav
        className="grid"
        style={{ gap: 'var(--space-xs)', gridTemplateColumns: `repeat(${Math.max(actions.length, 1)}, minmax(0, 1fr))` }}
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
