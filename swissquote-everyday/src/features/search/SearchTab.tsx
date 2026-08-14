/**
 * SEARCH tab — static replica of the production app's search screen
 * (recent searches + keyboard, copied from the reference screenshots).
 * Untouched by the Everyday concept.
 */

const RECENT: { query: string; type: string }[] = [
  { query: 'BTC', type: 'Crypto' },
  { query: 'SQN', type: 'Shares' },
  { query: 'APPL', type: 'Shares' },
];

const KEY_ROWS = [
  ['Q', 'W', 'E', 'R', 'T', 'Y', 'U', 'I', 'O', 'P'],
  ['A', 'S', 'D', 'F', 'G', 'H', 'J', 'K', 'L'],
  ['⇧', 'Z', 'X', 'C', 'V', 'B', 'N', 'M', '⌫'],
];

export function SearchTab() {
  return (
    <div className="flex flex-col" style={{ flex: 1, minHeight: 0 }}>
      <div className="screen" style={{ flex: 1 }}>
        <div className="flex items-center justify-between">
          <span className="top-bar__icon" aria-hidden="true" style={{ fontSize: 'var(--font-size-title)' }}>×</span>
          <div className="seg-control" role="tablist" aria-label="Search mode">
            <button type="button" role="tab" aria-selected className="seg-control__item">Search</button>
            <button type="button" role="tab" aria-selected={false} className="seg-control__item">Ask AI</button>
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
            Search
          </div>
        </div>
      </div>

      <div className="keyboard" aria-hidden="true">
        {KEY_ROWS.map((row, i) => (
          <div key={i} className="keyboard__row">
            {row.map((k) => (
              <span key={k} className={`keyboard__key ${k === '⇧' || k === '⌫' ? 'keyboard__key--mod' : ''}`}>{k}</span>
            ))}
          </div>
        ))}
        <div className="keyboard__row" style={{ marginBottom: 0 }}>
          <span className="keyboard__key keyboard__key--mod keyboard__key--edge">123</span>
          <span className="keyboard__key keyboard__key--wide">space</span>
          <span className="keyboard__key keyboard__key--mod keyboard__key--edge">return</span>
        </div>
      </div>
    </div>
  );
}
