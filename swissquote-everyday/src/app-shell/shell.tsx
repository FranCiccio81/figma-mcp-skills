/**
 * App shell replicated from the production Swissquote app reference:
 * iOS status bar, top bar (shield / search / avatar, or back + centred title),
 * bottom tab bar (Home · Trade · Bank · Search), and the app's signature
 * amount treatment (large integer, smaller grey decimals + currency).
 */
import type { ReactNode } from 'react';
import { swissNumber } from '../lib/format';

export function StatusBar({ onCard = false }: { onCard?: boolean }) {
  return (
    <div className={`status-bar ${onCard ? 'status-bar--card' : ''}`} aria-hidden="true">
      <span>9:41</span>
      <span className="flex items-center" style={{ gap: 'var(--space-2xs)' }}>
        <svg width="17" height="11" viewBox="0 0 17 11" fill="currentColor">
          <rect x="0" y="7" width="3" height="4" rx="0.8" />
          <rect x="4.5" y="5" width="3" height="6" rx="0.8" />
          <rect x="9" y="2.5" width="3" height="8.5" rx="0.8" />
          <rect x="13.5" y="0" width="3" height="11" rx="0.8" />
        </svg>
        <svg width="15" height="11" viewBox="0 0 15 11" fill="currentColor">
          <path d="M7.5 9.2a1.4 1.4 0 1 0 0 2.8 1.4 1.4 0 0 0 0-2.8zM4.9 7.6l1.3 1.3a1.9 1.9 0 0 1 2.6 0l1.3-1.3a3.7 3.7 0 0 0-5.2 0zM2.3 5l1.3 1.3a5.6 5.6 0 0 1 7.8 0L12.7 5a7.4 7.4 0 0 0-10.4 0zM0 2.6l1.3 1.3a8.9 8.9 0 0 1 12.4 0L15 2.6a10.8 10.8 0 0 0-15 0z" transform="scale(1,0.92)" />
        </svg>
        <svg width="25" height="12" viewBox="0 0 25 12" fill="none" stroke="currentColor">
          <rect x="0.5" y="0.5" width="21" height="11" rx="3" opacity="0.4" />
          <rect x="2" y="2" width="18" height="8" rx="1.8" fill="currentColor" stroke="none" />
          <path d="M23.5 4v4a2.2 2.2 0 0 0 0-4z" fill="currentColor" stroke="none" opacity="0.4" />
        </svg>
      </span>
    </div>
  );
}

function ShieldIcon() {
  return (
    <svg width="16" height="18" viewBox="0 0 16 18" fill="none" stroke="currentColor" strokeWidth="1.5">
      <path d="M8 1.2 14.5 3.5v5c0 4-2.6 6.9-6.5 8.3C4.1 15.4 1.5 12.5 1.5 8.5v-5L8 1.2z" strokeLinejoin="round" />
    </svg>
  );
}

function SearchIcon({ plus = false }: { plus?: boolean }) {
  return (
    <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.7">
      <circle cx="8.5" cy="8.5" r="5.5" />
      <path d="m13 13 4.5 4.5" strokeLinecap="round" />
      {plus && <path d="M8.5 6.3v4.4M6.3 8.5h4.4" strokeLinecap="round" strokeWidth="1.4" />}
    </svg>
  );
}

/** Root-screen top bar: shield left, search + avatar right. */
export function TopBar({ onCard = false }: { onCard?: boolean }) {
  return (
    <div className={`top-bar ${onCard ? 'top-bar--card' : ''}`}>
      <span className="top-bar__icon top-bar__icon--ring" aria-hidden="true">
        <ShieldIcon />
      </span>
      <span className="flex items-center" style={{ gap: 'var(--space-xs)' }}>
        <span className="top-bar__icon" aria-hidden="true">
          <SearchIcon />
        </span>
        <span className="top-bar__avatar" aria-label="Profile — Léa Baumann">LB</span>
      </span>
    </div>
  );
}

/** Detail-screen top bar: back chevron left, centred title, search + avatar right. */
export function DetailTopBar({ title, onBack, onCard = false }: { title: string; onBack: () => void; onCard?: boolean }) {
  return (
    <div className={`top-bar ${onCard ? 'top-bar--card' : ''}`}>
      <button type="button" className="top-bar__icon" style={{ minWidth: 'var(--size-touch-target)', minHeight: 'var(--size-touch-target)' }} onClick={onBack} aria-label="Back">
        <svg width="11" height="18" viewBox="0 0 11 18" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M9.5 1.5 2 9l7.5 7.5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </button>
      <h1 className="top-bar__title m-0">{title}</h1>
      <span className="flex items-center" style={{ gap: 'var(--space-xs)' }}>
        <span className="top-bar__icon" aria-hidden="true">
          <SearchIcon />
        </span>
        <span className="top-bar__avatar" aria-hidden="true">LB</span>
      </span>
    </div>
  );
}

export type AppTab = 'home' | 'trade' | 'bank' | 'search';

const TAB_ICONS: Record<AppTab, ReactNode> = {
  home: (
    <svg width="22" height="22" viewBox="0 0 22 22" fill="none" stroke="currentColor" strokeWidth="1.7">
      <path d="M3 9.5 11 3l8 6.5V19a1 1 0 0 1-1 1h-4.5v-5.5h-5V20H4a1 1 0 0 1-1-1V9.5z" strokeLinejoin="round" />
    </svg>
  ),
  trade: (
    <svg width="22" height="22" viewBox="0 0 22 22" fill="none" stroke="currentColor" strokeWidth="1.7">
      <path d="M4 4v10M4 6.5h3v5H4M11 3v3M11 6h1.5v6H9.5V6H11M11 12v2M18 8v10M18 10h-3v5.5h3" strokeLinecap="round" />
    </svg>
  ),
  bank: (
    <svg width="22" height="22" viewBox="0 0 22 22" fill="none" stroke="currentColor" strokeWidth="1.7">
      <rect x="2.5" y="5" width="17" height="12" rx="2" />
      <path d="M2.5 9h17" />
      <path d="M6 13.5h4" strokeLinecap="round" />
    </svg>
  ),
  search: <SearchIcon plus />,
};

const TAB_LABELS: Record<AppTab, string> = { home: 'Home', trade: 'Trade', bank: 'Bank', search: 'Search' };

export function BottomNav({ active, onSelect }: { active: AppTab; onSelect: (t: AppTab) => void }) {
  return (
    <nav className="tab-bar" aria-label="Main navigation">
      {(Object.keys(TAB_LABELS) as AppTab[]).map((tab) => (
        <button
          key={tab}
          type="button"
          className="tab-bar__item"
          aria-current={active === tab ? 'page' : undefined}
          onClick={() => onSelect(tab)}
        >
          {TAB_ICONS[tab]}
          {TAB_LABELS[tab]}
        </button>
      ))}
    </nav>
  );
}

/** App-style amount: `45'218` large, `.30 CHF` smaller and grey. */
export function AmountXL({ value, currency = 'CHF' }: { value: number; currency?: string }) {
  const fixed = swissNumber(value);
  const dot = fixed.lastIndexOf('.');
  return (
    <span className="amount-xl">
      <span className="amount-xl__int">{fixed.slice(0, dot)}</span>
      <span className="amount-xl__frac">
        {fixed.slice(dot)} {currency}
      </span>
    </span>
  );
}

/** Green/red change line: `▲ 3.24%  +1'418.30 CHF` */
export function Delta({ pct, amount }: { pct: number; amount: number }) {
  const up = pct >= 0;
  return (
    <span className={`delta ${up ? 'delta--up' : 'delta--down'} amount`}>
      {up ? '▲' : '▼'} {Math.abs(pct).toFixed(2)}% {up ? '+' : '−'}
      {swissNumber(Math.abs(amount))} CHF
    </span>
  );
}
