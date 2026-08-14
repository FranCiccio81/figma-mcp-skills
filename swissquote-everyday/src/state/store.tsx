/**
 * In-memory app store — React context over the liquidity engine reducer.
 * No localStorage, no sessionStorage: refresh = pristine demo (per the brief).
 */
import { createContext, useContext, useMemo, useReducer, useState, type ReactNode } from 'react';

import {
  FX,
  LOMBARD_RATE_PA,
  PENDING_CARD_RESERVED,
  SAVE_EASY_PENALTY_FREE,
  TRADING_ORDERS_RESERVED,
} from '../data/mockLedger';
import { computeForecast, type Forecast } from './forecast';
import { initialState, reduce, type EngineAction } from './liquidityEngine';
import type { EngineState } from './types';

/** Bottom-tab of the host app. Everyday lives entirely inside 'bank'. */
export type AppTab = 'home' | 'trade' | 'bank' | 'search';
/** Screens within the Bank tab ('home' = the Everyday hub). */
export type Screen = 'home' | 'allocation' | 'budgeting' | 'autoCover' | 'transactions' | 'card' | 'pay';

/** Debit-card settings — UI state, not part of the liquidity engine. */
export interface CardSettings {
  frozen: boolean;
  onlinePayments: boolean;
  monthlyLimit: number;
  contactlessLimit: number;
}

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

/**
 * One liquidity source. `class` is the spec's liquidity classification (§16):
 * available now / transferable / conditional / credit — never an opaque discount.
 */
export interface BuyingPowerSegment {
  key: 'cash' | 'fx' | 'save' | 'trading' | 'credit';
  label: string;
  amountChf: number;
  liquidityClass: 'now' | 'transferable' | 'conditional' | 'credit';
  availability: string;
  /** Amounts held back before this counts as available (§18–§22). */
  reserved?: { label: string; amount: number }[];
  cost: string | null;
  indicative: boolean;
  isCredit: boolean;
}

export interface BuyingPower {
  /** Immediately spendable from Everyday, after authorised card transactions. */
  availableNow: number;
  /** Own cash sitting in other Swissquote products that can be moved. */
  accessibleElsewhere: number;
  ownSegments: BuyingPowerSegment[];
  /** Own accessible cash — always exposed independently of credit (FR-10). */
  ownTotal: number;
  /** AI Budgeting's protected liquidity, identified separately, never deducted invisibly. */
  protectedLiquidity: number;
  /** Own cash above the protected amount. */
  flexible: number;
  credit: BuyingPowerSegment;
  /** Own cash + usable credit — a maximum, shown only as a secondary figure. */
  maximum: number;
  /** Invested money that is deliberately NOT liquidity (§6.3/BR-02). */
  notIncluded: { label: string; amountChf: number; reason: string }[];
}

/** Which sources the client lets Buying Power aggregate (§64/FR-20). */
export interface BuyingPowerSettings {
  includeTrading: boolean;
  includeSaveEasy: boolean;
  includeWallets: boolean;
  /** Lombard must be an explicit choice — off by default (FR-13). */
  showLombard: boolean;
}

interface Store {
  state: EngineState;
  dispatch: (a: EngineAction) => void;
  forecast: Forecast;
  buyingPower: BuyingPower;
  nav: Nav;
  card: CardSettings;
  setCard: (patch: Partial<CardSettings>) => void;
  bpSettings: BuyingPowerSettings;
  setBpSettings: (patch: Partial<BuyingPowerSettings>) => void;
}

const Ctx = createContext<Store | null>(null);

/**
 * Everyday Buying Power — the spec's liquidity model (§7/§17/§56).
 *
 * Own cash and credit are computed and displayed separately; invested money is
 * excluded entirely; reservations (authorised card transactions, open orders)
 * are deducted before anything is called available; AI Budgeting's protected
 * amount is identified rather than silently subtracted.
 */
export function computeBuyingPower(
  state: EngineState,
  protectedLiquidity: number,
  settings: BuyingPowerSettings,
): BuyingPower {
  const a = state.accounts;

  // Layer 1 — available now: booked balance minus authorised card transactions.
  const availableNow = Math.max(0, a.everyday - PENDING_CARD_RESERVED);

  const ownSegments: BuyingPowerSegment[] = [
    {
      key: 'cash',
      label: 'Everyday',
      amountChf: availableNow,
      liquidityClass: 'now',
      availability: 'Available now',
      reserved: [{ label: 'Authorised card payments', amount: PENDING_CARD_RESERVED }],
      cost: null,
      indicative: false,
      isCredit: false,
    },
  ];

  // Layer 2 — accessible cash elsewhere.
  if (settings.includeTrading) {
    const free = Math.max(0, a.tradingCash - TRADING_ORDERS_RESERVED);
    ownSegments.push({
      key: 'trading',
      label: 'Trading cash',
      amountChf: state.flags.tradingUnavailable ? 0 : free,
      liquidityClass: 'transferable',
      availability: state.flags.tradingUnavailable
        ? 'Temporarily unavailable'
        : 'Transferable to Everyday',
      reserved: [{ label: 'Reserved for open orders', amount: TRADING_ORDERS_RESERVED }],
      cost: null,
      indicative: false,
      isCredit: false,
    });
  }
  if (settings.includeSaveEasy) {
    const penaltyFree = Math.min(a.saveEasy, SAVE_EASY_PENALTY_FREE);
    ownSegments.push({
      key: 'save',
      label: 'Save Easy',
      amountChf: penaltyFree,
      liquidityClass: 'conditional',
      availability: 'Accessible — withdrawal conditions apply',
      reserved:
        a.saveEasy > penaltyFree
          ? [{ label: 'Above the penalty-free limit', amount: a.saveEasy - penaltyFree }]
          : undefined,
      cost: null,
      indicative: false,
      isCredit: false,
    });
  }
  if (settings.includeWallets) {
    const fxChf = a.eurWallet * FX.eurToChf + a.usdWallet * FX.usdToChf;
    ownSegments.push({
      key: 'fx',
      label: 'Other currencies',
      amountChf: fxChf,
      liquidityClass: 'conditional',
      availability: 'Needs conversion to CHF',
      cost: `FX spread ≈ ${FX.spreadPct}%`,
      indicative: true,
      isCredit: false,
    });
  }

  const ownTotal = ownSegments.reduce((s, x) => s + x.amountChf, 0);
  const accessibleElsewhere = ownTotal - availableNow;
  const flexible = Math.max(0, ownTotal - protectedLiquidity);

  const credit: BuyingPowerSegment = {
    key: 'credit',
    label: 'Lombard available',
    amountChf: settings.showLombard ? a.lombardAvailable : 0,
    liquidityClass: 'credit',
    availability: settings.showLombard ? `Up to ${a.lombardAvailable} currently drawable` : 'Not shown',
    cost: `${LOMBARD_RATE_PA}% p.a. interest`,
    indicative: false,
    isCredit: true,
  };

  // Invested money is not liquidity — stated explicitly rather than hidden.
  const notIncluded = [
    { label: 'Invest Easy', amountChf: a.investEasy, reason: 'Invested — would need to be sold' },
    { label: 'Global ETF Saving Plan', amountChf: a.savingPlan, reason: 'Invested — would need to be sold' },
  ];

  return {
    availableNow,
    accessibleElsewhere,
    ownSegments,
    ownTotal,
    protectedLiquidity,
    flexible,
    credit,
    maximum: ownTotal + credit.amountChf,
    notIncluded,
  };
}

export function StoreProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(reduce, undefined, initialState);
  const [tab, setTab] = useState<AppTab>('bank');
  const [screen, setScreen] = useState<Screen>('home');
  const [txnDetailId, setTxnDetailId] = useState<string | null>(null);
  const [buyingPowerOpen, setBuyingPowerOpen] = useState(false);
  const [card, setCardState] = useState<CardSettings>({
    frozen: false,
    onlinePayments: true,
    monthlyLimit: 10_000,
    contactlessLimit: 100,
  });

  const [bpSettings, setBpSettingsState] = useState<BuyingPowerSettings>({
    includeTrading: true,
    includeSaveEasy: true,
    includeWallets: true,
    showLombard: true, // on in the demo; the product default is off until opted in
  });

  const forecast = useMemo(() => computeForecast(state), [state]);
  const buyingPower = useMemo(
    () => computeBuyingPower(state, forecast.keep, bpSettings),
    [state, forecast.keep, bpSettings],
  );

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
  const store: Store = {
    state,
    dispatch,
    forecast,
    buyingPower,
    nav,
    card,
    setCard: (patch) => setCardState((c) => ({ ...c, ...patch })),
    bpSettings,
    setBpSettings: (patch) => setBpSettingsState((c) => ({ ...c, ...patch })),
  };

  return <Ctx.Provider value={store}>{children}</Ctx.Provider>;
}

export function useStore(): Store {
  const s = useContext(Ctx);
  if (!s) throw new Error('useStore outside <StoreProvider>');
  return s;
}
