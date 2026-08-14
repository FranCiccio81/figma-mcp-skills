/**
 * In-memory app store — React context over the liquidity engine reducer.
 * No localStorage, no sessionStorage: refresh = pristine demo (per the brief).
 */
import { createContext, useContext, useMemo, useReducer, useState, type ReactNode } from 'react';

import { FX } from '../data/mockLedger';
import { computeForecast, type Forecast } from './forecast';
import { initialState, reduce, type EngineAction } from './liquidityEngine';
import type { EngineState } from './types';

/** Bottom-tab of the host app. Everyday lives entirely inside 'bank'. */
export type AppTab = 'home' | 'trade' | 'bank' | 'search';
/** Screens within the Bank tab ('home' = the Everyday hub). */
export type Screen = 'home' | 'allocation' | 'budgeting' | 'autoCover' | 'transactions';

export interface Nav {
  tab: AppTab;
  screen: Screen;
  txnDetailId: string | null;
  buyingPowerOpen: boolean;
  setTab: (tab: AppTab) => void;
  go: (screen: Screen) => void;
  openTxn: (id: string) => void;
  closeTxn: () => void;
  setBuyingPowerOpen: (open: boolean) => void;
}

/** One Buying Power segment. Own funds and credit are NEVER summed together. */
export interface BuyingPowerSegment {
  key: 'cash' | 'fx' | 'save' | 'trading' | 'credit';
  label: string;
  amountChf: number;
  availability: string;
  cost: string | null;
  indicative: boolean;
  isCredit: boolean;
}

export interface BuyingPower {
  ownSegments: BuyingPowerSegment[];
  credit: BuyingPowerSegment;
  ownTotal: number;
}

interface Store {
  state: EngineState;
  dispatch: (a: EngineAction) => void;
  forecast: Forecast;
  buyingPower: BuyingPower;
  nav: Nav;
}

const Ctx = createContext<Store | null>(null);

export function computeBuyingPower(state: EngineState): BuyingPower {
  const a = state.accounts;
  const fxChf = a.eurWallet * FX.eurToChf + a.usdWallet * FX.usdToChf;
  const ownSegments: BuyingPowerSegment[] = [
    { key: 'cash', label: 'Everyday cash', amountChf: a.everyday, availability: 'Instant', cost: null, indicative: false, isCredit: false },
    { key: 'fx', label: 'Other currencies', amountChf: fxChf, availability: 'Instant', cost: `FX spread ≈ ${FX.spreadPct}%`, indicative: true, isCredit: false },
    { key: 'save', label: 'Save Easy', amountChf: a.saveEasy, availability: 'Instant', cost: null, indicative: false, isCredit: false },
    {
      key: 'trading',
      label: 'Trading cash',
      amountChf: a.tradingCash,
      availability: state.flags.marketClosed ? 'Unavailable — market closed' : 'Same day',
      cost: null,
      indicative: false,
      isCredit: false,
    },
  ];
  const credit: BuyingPowerSegment = {
    key: 'credit',
    label: 'Lombard available',
    amountChf: a.lombardAvailable,
    availability: state.autoCover.lombardEnabled ? 'Instant · opt-in active' : 'Opt-in required',
    cost: '4.25% p.a. interest',
    indicative: false,
    isCredit: true,
  };
  // NOTE: §10 states an own-funds total of 22'517.00, which does not equal the
  // sum of its own listed parts (21'916.90). The engine computes the true sum —
  // a hardcoded figure would drift the moment the simulation advances a day.
  const ownTotal = ownSegments.reduce((s, x) => s + x.amountChf, 0);
  return { ownSegments, credit, ownTotal };
}

export function StoreProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(reduce, undefined, initialState);
  const [tab, setTab] = useState<AppTab>('bank');
  const [screen, setScreen] = useState<Screen>('home');
  const [txnDetailId, setTxnDetailId] = useState<string | null>(null);
  const [buyingPowerOpen, setBuyingPowerOpen] = useState(false);

  const forecast = useMemo(() => computeForecast(state), [state]);
  const buyingPower = useMemo(() => computeBuyingPower(state), [state]);

  const nav: Nav = {
    tab,
    screen,
    txnDetailId,
    buyingPowerOpen,
    setTab: (t) => {
      setTxnDetailId(null);
      setBuyingPowerOpen(false);
      setScreen('home');
      setTab(t);
    },
    go: (s) => {
      setTxnDetailId(null);
      setBuyingPowerOpen(false);
      setScreen(s);
      setTab('bank');
    },
    openTxn: (id) => setTxnDetailId(id),
    closeTxn: () => setTxnDetailId(null),
    setBuyingPowerOpen,
  };

  // Reset is handled in App by remounting the provider with a new key.
  const store: Store = { state, dispatch, forecast, buyingPower, nav };

  return <Ctx.Provider value={store}>{children}</Ctx.Provider>;
}

export function useStore(): Store {
  const s = useContext(Ctx);
  if (!s) throw new Error('useStore outside <StoreProvider>');
  return s;
}
