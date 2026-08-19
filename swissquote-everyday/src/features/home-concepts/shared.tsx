/**
 * Pieces both Home concepts need. Kept deliberately small: anything that
 * shapes the product hypothesis belongs in the variant, not here.
 */
import type { ReactNode } from 'react';
import { AmountXL } from '../../app-shell/shell';
import { swissNumber } from '../../lib/format';
import { useStore } from '../../state/store';
import type { Destination } from './homeData';

/** Routes a `Destination` through the app's existing navigation. */
export function useGoTo(): (d: Destination) => void {
  const { nav } = useStore();
  return (d) => (d.tab === 'bank' ? nav.go(d.screen ?? 'home') : nav.setTab(d.tab));
}

export function EyeIcon({ off }: { off: boolean }) {
  return (
    <svg width="18" height="18" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden="true">
      <path d="M1.5 10S4.7 4.5 10 4.5 18.5 10 18.5 10 15.3 15.5 10 15.5 1.5 10 1.5 10z" strokeLinejoin="round" />
      <circle cx="10" cy="10" r="2.6" />
      {off && <path d="M3 17 17 3" strokeLinecap="round" />}
    </svg>
  );
}

export function SparkIcon({ size = 12 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 12 12" fill="currentColor" aria-hidden="true">
      <path d="M6 0c.5 3.2 2.3 5 5.5 5.5C8.3 6 6.5 7.8 6 11 5.5 7.8 3.7 6 .5 5.5 3.7 5 5.5 3.2 6 0z" />
    </svg>
  );
}

/** Button that hides or shows every balance on the screen. */
export function BalanceVisibilityButton() {
  const { home } = useStore();
  return (
    <button
      type="button"
      className="top-bar__icon"
      style={{ minWidth: 'var(--size-touch-target)', minHeight: 'var(--size-touch-target)' }}
      aria-pressed={home.balancesHidden}
      aria-label={home.balancesHidden ? 'Show balances' : 'Hide balances'}
      onClick={() => home.setBalancesHidden(!home.balancesHidden)}
    >
      <EyeIcon off={home.balancesHidden} />
    </button>
  );
}

/**
 * An amount, or dots when the client has hidden balances. Hidden means
 * hidden: the number is not in the accessible name either.
 */
export function Amount({ value, currency = 'CHF' }: { value: number; currency?: string }) {
  const { home } = useStore();
  if (home.balancesHidden) return <span className="amount-hidden">•••••</span>;
  return (
    <span className="amount">
      {swissNumber(value)} <span className="caption">{currency}</span>
    </span>
  );
}

export function BigAmount({ value }: { value: number }) {
  const { home } = useStore();
  if (home.balancesHidden) {
    return (
      <span className="amount-hidden amount-hidden--xl" aria-label="Balances hidden">
        ••••••
      </span>
    );
  }
  return <AmountXL value={value} />;
}

export function Skeleton({ w = '100%', h = 'var(--space-md)' }: { w?: string; h?: string }) {
  return <span className="skeleton" style={{ width: w, height: h }} aria-hidden="true" />;
}

/** Loading state — a shape, not a spinner, so the layout does not jump. */
export function HomeSkeleton({ rows = 3 }: { rows?: number }) {
  return (
    <div className="screen" aria-busy="true" aria-label="Loading your accounts">
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 'var(--space-xs)' }}>
        <Skeleton w="88px" h="var(--space-sm)" />
        <Skeleton w="200px" h="var(--space-xl)" />
      </div>
      {Array.from({ length: rows }, (_, i) => (
        <div key={i} className="card flex flex-col" style={{ gap: 'var(--space-xs)' }}>
          <Skeleton w="72px" h="var(--space-sm)" />
          <Skeleton w="60%" h="var(--space-lg)" />
          <Skeleton w="80%" h="var(--space-sm)" />
        </div>
      ))}
      <p className="sr-only">Loading your accounts</p>
    </div>
  );
}

/** The label every AI-assisted surface carries, next to a way to see the data. */
export function AiLabel({ children }: { children?: ReactNode }) {
  return (
    <span className="ai-label">
      <SparkIcon />
      {children ?? 'AI-assisted'}
    </span>
  );
}
