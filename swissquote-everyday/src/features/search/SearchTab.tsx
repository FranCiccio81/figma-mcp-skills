/**
 * SEARCH tab — the production app's search screen, with the two modes live.
 *
 * Typing (physical keyboard or the on-screen one) filters suggestions as you
 * go: instruments in Search mode, questions in Ask AI mode. Suggestions are
 * what make Ask AI feel answerable rather than an empty box.
 */
import { useMemo, useRef, useState } from 'react';
import { useStore } from '../../state/store';

const RECENT: { query: string; type: string }[] = [
  { query: 'BTC', type: 'Crypto' },
  { query: 'SQN', type: 'Shares' },
  { query: 'APPL', type: 'Shares' },
];

/** Instruments for Search mode. */
const INSTRUMENTS: { name: string; ticker: string; type: string }[] = [
  { name: 'Apple Inc', ticker: 'APPL', type: 'Shares' },
  { name: 'Amazon.com', ticker: 'AMZN', type: 'Shares' },
  { name: 'Nike', ticker: 'NKE', type: 'Shares' },
  { name: 'Swissquote Group', ticker: 'SQN', type: 'Shares' },
  { name: 'Target Corporation', ticker: 'TGT', type: 'Shares' },
  { name: 'Southern Copper', ticker: 'SCCO', type: 'Shares' },
  { name: 'Bitcoin', ticker: 'BTC', type: 'Crypto' },
  { name: 'Ethereum', ticker: 'ETH', type: 'Crypto' },
  { name: 'iShares Core MSCI World', ticker: 'IWDA', type: 'ETF' },
  { name: 'Vanguard S&P 500', ticker: 'VUSA', type: 'ETF' },
];

/** Questions for Ask AI mode — mostly about the client's own money. */
const QUESTIONS: string[] = [
  'How much can I invest this month?',
  'How much will I need before my next salary?',
  'Why did Auto Cover move money?',
  'What is my buying power right now?',
  'How much did I spend on restaurants last month?',
  'Can I afford a CHF 20’000 payment this week?',
  'What happens if I lower my safety buffer?',
  'How much have I saved and invested automatically?',
  'When does my next salary allocation run?',
  'What is my Lombard credit costing me?',
  'Which subscriptions am I paying for?',
  'Is my spending higher than usual?',
];

function SearchIcon({ size = 16 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden="true">
      <circle cx="8.5" cy="8.5" r="5.5" />
      <path d="m13 13 4.5 4.5" strokeLinecap="round" />
    </svg>
  );
}

function SparkIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 12 12" fill="currentColor" aria-hidden="true">
      <path d="M6 0c.5 3.2 2.3 5 5.5 5.5C8.3 6 6.5 7.8 6 11 5.5 7.8 3.7 6 .5 5.5 3.7 5 5.5 3.2 6 0z" />
    </svg>
  );
}

function ShiftIcon() {
  return (
    <svg width="18" height="16" viewBox="0 0 18 16" fill="none" stroke="currentColor" strokeWidth="1.5">
      <path d="M9 1.5 2 8.5h3.5V14h7V8.5H16L9 1.5z" strokeLinejoin="round" />
    </svg>
  );
}

function BackspaceIcon() {
  return (
    <svg width="20" height="15" viewBox="0 0 20 15" fill="none" stroke="currentColor" strokeWidth="1.5">
      <path d="M6.6 1h11.2a1 1 0 0 1 1 1v11a1 1 0 0 1-1 1H6.6a1 1 0 0 1-.74-.33L1 7.5l4.86-6.17A1 1 0 0 1 6.6 1z" strokeLinejoin="round" />
      <path d="m9.5 5 5 5m0-5-5 5" strokeLinecap="round" />
    </svg>
  );
}

function EmojiIcon() {
  return (
    <svg width="22" height="22" viewBox="0 0 22 22" fill="none" stroke="currentColor" strokeWidth="1.5">
      <circle cx="11" cy="11" r="9" />
      <path d="M7.5 13a4.5 4.5 0 0 0 7 0" strokeLinecap="round" />
      <circle cx="8" cy="8.5" r="0.6" fill="currentColor" stroke="none" />
      <circle cx="14" cy="8.5" r="0.6" fill="currentColor" stroke="none" />
    </svg>
  );
}

function MicIcon() {
  return (
    <svg width="16" height="22" viewBox="0 0 16 22" fill="none" stroke="currentColor" strokeWidth="1.5">
      <rect x="5" y="1" width="6" height="11" rx="3" />
      <path d="M2 10a6 6 0 0 0 12 0M8 16v4" strokeLinecap="round" />
    </svg>
  );
}

/** The on-screen keyboard actually types — it drives the same query state. */
function Keyboard({ onKey }: { onKey: (key: string) => void }) {
  const row1 = ['Q', 'W', 'E', 'R', 'T', 'Y', 'U', 'I', 'O', 'P'];
  const row2 = ['A', 'S', 'D', 'F', 'G', 'H', 'J', 'K', 'L'];
  const row3 = ['Z', 'X', 'C', 'V', 'B', 'N', 'M'];
  return (
    <div className="keyboard">
      <div className="keyboard__row">
        {row1.map((k) => (
          <button key={k} type="button" className="keyboard__key" onClick={() => onKey(k)} aria-label={k}>
            {k}
          </button>
        ))}
      </div>
      <div className="keyboard__row keyboard__row--inset">
        {row2.map((k) => (
          <button key={k} type="button" className="keyboard__key" onClick={() => onKey(k)} aria-label={k}>
            {k}
          </button>
        ))}
      </div>
      <div className="keyboard__row">
        <span className="keyboard__key keyboard__key--mod" aria-hidden="true"><ShiftIcon /></span>
        {row3.map((k) => (
          <button key={k} type="button" className="keyboard__key" onClick={() => onKey(k)} aria-label={k}>
            {k}
          </button>
        ))}
        <button type="button" className="keyboard__key keyboard__key--mod" onClick={() => onKey('⌫')} aria-label="Backspace">
          <BackspaceIcon />
        </button>
      </div>
      <div className="keyboard__row" style={{ marginBottom: 0 }}>
        <span className="keyboard__key keyboard__key--sys keyboard__key--edge" aria-hidden="true">123</span>
        <button type="button" className="keyboard__key keyboard__key--space" onClick={() => onKey(' ')} aria-label="Space">
          space
        </button>
        <span className="keyboard__key keyboard__key--sys keyboard__key--edge" aria-hidden="true">return</span>
      </div>
      <div className="keyboard__footer" aria-hidden="true">
        <EmojiIcon />
        <MicIcon />
      </div>
      <div className="keyboard__home-indicator" aria-hidden="true" />
    </div>
  );
}

export function SearchTab() {
  const { nav } = useStore();
  const [mode, setMode] = useState<'search' | 'ai'>('ai');
  // A question tapped on Home arrives already typed.
  const [query, setQuery] = useState(nav.askPrefill ?? '');
  const inputRef = useRef<HTMLInputElement>(null);

  const onKey = (key: string) => {
    setQuery((q) => (key === '⌫' ? q.slice(0, -1) : q + (q.length === 0 ? key : key.toLowerCase())));
  };

  const q = query.trim().toLowerCase();

  const questionMatches = useMemo(
    () => (q ? QUESTIONS.filter((s) => s.toLowerCase().includes(q)) : QUESTIONS.slice(0, 4)),
    [q],
  );
  const instrumentMatches = useMemo(
    () =>
      q
        ? INSTRUMENTS.filter((i) => i.name.toLowerCase().includes(q) || i.ticker.toLowerCase().includes(q))
        : [],
    [q],
  );

  const showRecent = mode === 'search' && q.length === 0;

  return (
    <div className="flex flex-col" style={{ minHeight: '100%' }}>
      <div className="screen" style={{ flex: 1 }}>
        <div className="flex items-center justify-between">
          <button
            type="button"
            className="top-bar__icon"
            aria-label="Close search"
            style={{ fontSize: 'var(--font-size-title)', minWidth: 'var(--size-touch-target)', minHeight: 'var(--size-touch-target)' }}
            onClick={() => nav.setTab('home')}
          >
            ×
          </button>
          <div className="seg-control" role="tablist" aria-label="Search mode">
            <button type="button" role="tab" aria-selected={mode === 'search'} className="seg-control__item" onClick={() => setMode('search')}>
              Search
            </button>
            <button type="button" role="tab" aria-selected={mode === 'ai'} className="seg-control__item" onClick={() => setMode('ai')}>
              Ask AI
            </button>
          </div>
          <span style={{ width: 'var(--space-xl)' }} />
        </div>

        {/* The input sits at the top in AI mode: you type, then you get answers. */}
        <label className="search-field" style={{ marginBottom: 'var(--space-2xs)' }}>
          {mode === 'ai' ? <SparkIcon /> : <SearchIcon />}
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={mode === 'ai' ? 'Ask anything about your money' : 'Search shares, ETFs, crypto'}
            aria-label={mode === 'ai' ? 'Ask AI' : 'Search'}
            style={{
              flex: 1,
              minWidth: 0,
              border: 'none',
              outline: 'none',
              background: 'transparent',
              font: 'inherit',
              color: 'var(--color-text-primary)',
            }}
          />
          {query && (
            <button type="button" className="caption" onClick={() => setQuery('')} aria-label="Clear input">
              ✕
            </button>
          )}
        </label>

        {showRecent ? (
          <>
            <div className="flex items-center justify-between">
              <h2 className="m-0" style={{ fontSize: 'var(--font-size-body)', fontWeight: 'var(--font-weight-semibold)' }}>Recent searches</h2>
              <button type="button" className="caption" style={{ color: 'var(--color-text-accent)', fontWeight: 'var(--font-weight-semibold)' }}>
                Clear
              </button>
            </div>
            <div className="flex justify-between caption">
              <span>Your search</span>
              <span>Product type</span>
            </div>
            <ul className="m-0 list-none" style={{ padding: 0 }}>
              {RECENT.map((r) => (
                <li key={r.query}>
                  <button
                    type="button"
                    className="flex justify-between"
                    style={{ width: '100%', padding: 'var(--space-xs) 0', borderBottom: '1px solid var(--color-border-subtle)', minHeight: 'var(--size-touch-target)' }}
                    onClick={() => setQuery(r.query)}
                  >
                    <span style={{ fontWeight: 'var(--font-weight-medium)' }}>{r.query}</span>
                    <span className="caption">{r.type}</span>
                  </button>
                </li>
              ))}
            </ul>
          </>
        ) : (
          <>
            <h2 className="m-0" style={{ fontSize: 'var(--font-size-body)', fontWeight: 'var(--font-weight-semibold)' }}>
              {mode === 'ai' ? (q ? 'Ask Swissquote' : 'Try asking') : 'Results'}
            </h2>
            <ul className="m-0 list-none" style={{ padding: 0 }} aria-live="polite">
              {mode === 'ai'
                ? questionMatches.map((s) => (
                    <li key={s}>
                      <button
                        type="button"
                        className="flex items-center"
                        style={{ gap: 'var(--space-sm)', width: '100%', padding: 'var(--space-xs) 0', borderBottom: '1px solid var(--color-border-subtle)', minHeight: 'var(--size-touch-target)' }}
                        onClick={() => setQuery(s)}
                      >
                        <span style={{ color: 'var(--color-text-link)' }}><SparkIcon /></span>
                        <span className="flex-1">{s}</span>
                        <span className="product-row__chevron" aria-hidden="true">›</span>
                      </button>
                    </li>
                  ))
                : instrumentMatches.map((i) => (
                    <li key={i.ticker}>
                      <button
                        type="button"
                        className="flex items-center"
                        style={{ gap: 'var(--space-sm)', width: '100%', padding: 'var(--space-xs) 0', borderBottom: '1px solid var(--color-border-subtle)', minHeight: 'var(--size-touch-target)' }}
                        onClick={() => setQuery(i.ticker)}
                      >
                        <span className="flex-1 min-w-0">
                          <span className="block" style={{ fontWeight: 'var(--font-weight-medium)' }}>{i.name}</span>
                          <span className="caption block">{i.ticker}</span>
                        </span>
                        <span className="caption">{i.type}</span>
                      </button>
                    </li>
                  ))}
            </ul>
            {mode === 'ai' && q.length > 0 && questionMatches.length === 0 && (
              <p className="caption m-0">
                Ask it in your own words — Swissquote will use your accounts, cards and Smart Liquidity settings to
                answer.
              </p>
            )}
            {mode === 'search' && q.length > 0 && instrumentMatches.length === 0 && (
              <p className="caption m-0">No instruments match “{query}”.</p>
            )}
          </>
        )}
      </div>

      <Keyboard onKey={onKey} />
    </div>
  );
}
