/**
 * Money actions, and the rule for which ones a given client sees.
 *
 * Variant A shows a fixed set — part of its "same screen every day" promise.
 * Variant B derives them from the client's situation, so "Contribute to 3a"
 * only appears while there is allowance left. Neither ever offers an action
 * into a space the client has not opened.
 */
import type { ReactNode } from 'react';
import { PILLAR_3A_ALLOWANCE, PILLAR_3A_PAID_IN } from '../../data/mockLedger';
import type { Destination, HomeData, UniverseKey } from './homeData';

export interface MoneyAction {
  label: string;
  destination: Destination;
  /** The space this action needs; null if it works for any client. */
  needs: UniverseKey | null;
  icon: ReactNode;
}

const TRANSFER = (
  <>
    <path d="M7 3.5v15M7 18.5l-3-3M7 18.5l3-3" strokeLinecap="round" strokeLinejoin="round" />
    <path d="M15 18.5v-15M15 3.5l-3 3M15 3.5l3 3" strokeLinecap="round" strokeLinejoin="round" />
  </>
);
const PLUS = <path d="M11 4.5v13M4.5 11h13" strokeLinecap="round" />;
const SWAP = <path d="M4 8h11l-3-3M18 14H7l3 3" strokeLinecap="round" strokeLinejoin="round" />;
const TREND = (
  <path d="M4 15.5 9 10l3.5 3L18 6.5M18 6.5h-4M18 6.5v4" strokeLinecap="round" strokeLinejoin="round" />
);
const SHIELD = (
  <path d="M11 3.2 17.5 5.5v5c0 4-2.6 6.9-6.5 8.3-3.9-1.4-6.5-4.3-6.5-8.3v-5L11 3.2z" strokeLinejoin="round" />
);

export const MOVE_MONEY: MoneyAction = {
  label: 'Move money',
  needs: 'bank',
  destination: { tab: 'bank', screen: 'autoCover' },
  icon: TRANSFER,
};
export const ADD_MONEY: MoneyAction = {
  label: 'Add money',
  needs: null,
  destination: { tab: 'bank', screen: 'home' },
  icon: PLUS,
};
export const EXCHANGE: MoneyAction = {
  label: 'Exchange',
  needs: 'bank',
  destination: { tab: 'bank', screen: 'pay' },
  icon: SWAP,
};
export const INVEST: MoneyAction = {
  label: 'Invest',
  needs: 'plan',
  destination: { tab: 'plan' },
  icon: TREND,
};
export const CONTRIBUTE_3A: MoneyAction = {
  label: 'Top up 3a',
  needs: 'plan',
  destination: { tab: 'plan' },
  icon: SHIELD,
};

/** Keeps a client from being offered a space they have not opened. */
export function availableActions(data: HomeData, actions: MoneyAction[]): MoneyAction[] {
  const owns = (key: UniverseKey) => data.universes.some((u) => u.key === key && u.owned);
  return actions
    .filter((a) => a.needs === null || owns(a.needs))
    .map((a) =>
      // Someone with no Bank account still needs somewhere to pay money in.
      a === ADD_MONEY && !owns('bank') ? { ...a, destination: { tab: 'trade' as const } } : a,
    );
}

/** Variant A: the same four, every day. */
export const FIXED_ACTIONS = [MOVE_MONEY, ADD_MONEY, EXCHANGE, INVEST];

/**
 * Variant B: what this client can usefully do right now. Four is the cap —
 * a fifth turns a decision into a menu.
 */
export function contextualActions(data: HomeData): MoneyAction[] {
  const room = PILLAR_3A_ALLOWANCE - PILLAR_3A_PAID_IN > 0;
  const candidates = [MOVE_MONEY, ADD_MONEY, EXCHANGE, ...(room ? [CONTRIBUTE_3A] : [INVEST])];
  return availableActions(data, candidates).slice(0, 4);
}
