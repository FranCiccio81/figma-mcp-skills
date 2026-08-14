/**
 * SEARCH tab — static replica of the production app's search screen
 * (recent searches + iOS keyboard, per the reference screenshots).
 * Ask AI is the active mode, as in the reference; the switch is tappable.
 * Untouched by the Everyday concept.
 */
import { useState } from 'react';
import { useStore } from '../../state/store';

const RECENT: { query: string; type: string }[] = [
  { query: 'BTC', type: 'Crypto' },
  { query: 'SQN', type: 'Shares' },
  { query: 'APPL', type: 'Shares' },
];

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

function Keyboard() {
  const row1 = ['Q', 'W', 'E', 'R', 'T', 'Y', 'U', 'I', 'O', 'P'];
  const row2 = ['A', 'S', 'D', 'F', 'G', 'H', 'J', 'K', 'L'];
  const row3 = ['Z', 'X', 'C', 'V', 'B', 'N', 'M'];
  return (
    <div className="keyboard" aria-hidden="true">
      <div className="keyboard__row">
        {row1.map((k) => (
          <span key={k} className="keyboard__key">{k}</span>
        ))}
      </div>
      <div className="keyboard__row keyboard__row--inset">
        {row2.map((k) => (
          <span key={k} className="keyboard__key">{k}</span>
        ))}
      </div>
      <div className="keyboard__row">
        <span className="keyboard__key keyboard__key--mod"><ShiftIcon /></span>
        {row3.map((k) => (
          <span key={k} className="keyboard__key">{k}</span>
        ))}
        <span className="keyboard__key keyboard__key--mod"><BackspaceIcon /></span>
      </div>
      <div className="keyboard__row" style={{ marginBottom: 0 }}>
        <span className="keyboard__key keyboard__key--sys">123</span>
        <span className="keyboard__key keyboard__key--space">space</span>
        <span className="keyboard__key keyboard__key--sys">return</span>
      </div>
      <div className="keyboard__footer">
        <EmojiIcon />
        <MicIcon />
      </div>
      <div className="keyboard__home-indicator" />
    </div>
  );
}

export function SearchTab() {
  const { nav } = useStore();
  const [mode, setMode] = useState<'search' | 'ai'>('ai');

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
            <li key={r.query} className="flex justify-between" style={{ padding: 'var(--space-xs) 0', borderBottom: '1px solid var(--color-border-subtle)' }}>
              <span style={{ fontWeight: 'var(--font-weight-medium)' }}>{r.query}</span>
              <span className="caption">{r.type}</span>
            </li>
          ))}
        </ul>

        <div style={{ marginTop: 'auto' }}>
          <div className="search-field" role="search">
            <svg width="16" height="16" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden="true">
              <circle cx="8.5" cy="8.5" r="5.5" />
              <path d="m13 13 4.5 4.5" strokeLinecap="round" />
            </svg>
            {mode === 'ai' ? 'Ask anything about your money' : 'Search'}
          </div>
        </div>
      </div>

      <Keyboard />
    </div>
  );
}
