/**
 * HOME — Variant B · "Smart Today"
 *
 * Hypothesis: clients open the app with a question — "is anything wrong, and
 * is there anything I should do?" — so Home should answer it before showing
 * anything else. The top of the screen is a short, prioritised list of what
 * changed and what needs a decision; the spaces sit underneath in a fixed
 * order so the screen still has a floor that never moves.
 *
 * Priority is a product rule (needs you › changed › opportunity › good to
 * know), computed in the adapter. The AI layer re-words those items and
 * suggests questions; it never chooses them, and it never acts.
 *
 * See README.md in this folder for the full design note.
 */
import { useState } from 'react';
import { useStore } from '../../state/store';
import { TODAY_LABELS, useHomeData, type TodayItem } from './homeData';
/* The list is already prioritised by the adapter — this screen only cuts it. */
import { AiLabel, Amount, BalanceVisibilityButton, BigAmount, HomeSkeleton, SparkIcon, useGoTo } from './shared';
import { useHomeAiBrief, useHomeAiPrompts } from './useHomeAi';

/** At most three. A fourth item is a list, and a list is not a decision. */
const MAX_TODAY = 3;

function TodayCard({
  item,
  body,
  primary,
  onOpen,
}: {
  item: TodayItem;
  body: string;
  primary: boolean;
  onOpen: () => void;
}) {
  const [basisOpen, setBasisOpen] = useState(false);
  return (
    <article className={`today ${primary ? 'today--primary' : ''} today--${item.kind}`}>
      <span className={`today__badge today__badge--${item.kind}`}>{TODAY_LABELS[item.kind]}</span>
      <h3 className="today__title m-0">{item.title}</h3>
      <p className="today__body m-0">{body}</p>
      <div className="today__foot">
        {item.cta && (
          <button
            type="button"
            className={`btn ${primary ? 'btn--primary' : 'btn--secondary'}`}
            onClick={onOpen}
          >
            {item.cta.label}
          </button>
        )}
        <button
          type="button"
          className="disclosure"
          aria-expanded={basisOpen}
          onClick={() => setBasisOpen((v) => !v)}
        >
          <span className="disclosure__chevron" aria-hidden="true">›</span>
          Why you're seeing this
        </button>
      </div>
      {basisOpen && <p className="m-0 micro">{item.basis}. Nothing has been done for you.</p>}
    </article>
  );
}

export function HomeVariantB() {
  const data = useHomeData();
  const { nav } = useStore();
  const goTo = useGoTo();
  const ai = useHomeAiBrief(data);
  const askPrompts = useHomeAiPrompts(data);

  const items = data.today.slice(0, MAX_TODAY);
  const rest = data.today.length - items.length;
  // The service re-words an item; if it has nothing for one, the adapter's own
  // sentence is used. Either way the client reads the same facts.
  const aiText = (id: string) => ai.brief?.statements.find((s) => s.itemId === id)?.text;

  if (data.loading) return <HomeSkeleton rows={2} />;

  return (
    <div className="screen">
      {/* Compact by design: the balance is context here, not the headline. */}
      <div className="wealth-strip">
        <span className="flex-1 min-w-0">
          <span className="caption block">Total wealth</span>
          <button
            type="button"
            className="wealth-strip__amount"
            onClick={() => nav.setWealthOpen(true)}
            aria-label="Total wealth — see the full breakdown"
          >
            <BigAmount value={data.totalWealth} />
            <span className="product-row__chevron" aria-hidden="true">›</span>
          </button>
        </span>
        <BalanceVisibilityButton />
      </div>

      <section aria-label="Today">
        <div className="flex items-center justify-between" style={{ marginBottom: 'var(--space-xs)' }}>
          <h2 className="section-title m-0">Today</h2>
          {items.length > 0 && <AiLabel>AI-assisted wording</AiLabel>}
        </div>

        {ai.status === 'unavailable' && items.length > 0 && (
          <p className="micro m-0" style={{ marginBottom: 'var(--space-xs)' }}>
            The assistant is unavailable right now. What follows comes straight from your accounts.
          </p>
        )}

        {items.length === 0 ? (
          <div className="card today-empty">
            <p className="m-0" style={{ fontWeight: 'var(--font-weight-semibold)' }}>
              Nothing needs you today
            </p>
            <p className="m-0 caption">
              {data.chf(data.totalWealth)} across your products, and no payment, allocation or limit is waiting on a
              decision.
            </p>
            <button type="button" className="btn btn--secondary" onClick={() => goTo({ tab: 'bank', screen: 'transactions' })}>
              See recent activity
            </button>
          </div>
        ) : (
          <div className="flex flex-col" style={{ gap: 'var(--space-sm)' }}>
            {items.map((item, i) => (
              <TodayCard
                key={item.id}
                item={item}
                body={aiText(item.id) ?? item.body}
                primary={i === 0}
                onOpen={() => item.cta && goTo(item.cta.destination)}
              />
            ))}
            {rest > 0 && (
              <p className="micro m-0">
                {rest} more {rest === 1 ? 'thing' : 'things'} worth knowing, kept out of the way. They are in the
                space they belong to.
              </p>
            )}
          </div>
        )}
      </section>

      {/* The floor: same spaces, same order, whatever happened today. */}
      <section aria-label="Your Swissquote spaces">
        <h2 className="section-title m-0" style={{ marginBottom: 'var(--space-2xs)' }}>
          Your Swissquote spaces
        </h2>
        <div className="card" style={{ padding: '0 var(--space-md)' }}>
          {data.universes.map((u) => (
            <button key={u.key} type="button" className="space-row" onClick={() => goTo(u.destination)}>
              <span className="flex-1 min-w-0">
                <span className="space-row__title">{u.title}</span>
                <span className="caption block">{u.purpose}</span>
              </span>
              <span className="space-row__value">
                <Amount value={u.value} />
              </span>
              <span className="product-row__chevron" aria-hidden="true">›</span>
            </button>
          ))}
        </div>
      </section>

      {/* Ask — the entry point, with questions this client can actually ask today. */}
      <section className="ask" aria-label="Ask Swissquote">
        <div className="ask__head">
          <span className="ask__title">
            <SparkIcon size={14} /> Ask Swissquote
          </span>
        </div>
        <p className="m-0 caption">Answers about your own money. It explains and suggests — you decide.</p>
        <div className="ask__prompts">
          {askPrompts.status === 'loading' && <span className="caption">Thinking of what's relevant…</span>}
          {askPrompts.status !== 'loading' &&
            askPrompts.prompts.map((p) => (
              <button key={p} type="button" className="ask__chip" onClick={() => nav.ask(p)}>
                {p}
              </button>
            ))}
        </div>
        <button type="button" className="btn btn--primary" onClick={() => nav.setTab('search')}>
          Ask something else
        </button>
      </section>
    </div>
  );
}
