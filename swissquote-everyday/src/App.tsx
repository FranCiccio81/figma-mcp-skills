/**
 * App shell — the production-app frame (status bar, top bar, bottom tab nav
 * with Home / Trade / Bank / Plan / Search) around the prototype. Trade and
 * Search are static replicas of the existing app; the Bank tab hosts all
 * Swissquote Everyday features; the Home tab renders whichever redesign
 * concept the Simulate rig has selected. The rig stays outside the phone.
 */
import { useState } from 'react';
import { BottomNav, DetailTopBar, TopBar } from './app-shell/shell';
import { MarginCallModal } from './components/MarginCallModal';
import { ConceptBadge } from './components/ui';
import { AutoCover } from './features/auto-cover/AutoCover';
import { AiBudgeting } from './features/budgeting/AiBudgeting';
import { CardManagement } from './features/card/CardManagement';
import { PayHub } from './features/pay/PayHub';
import { BuyingPowerSheet } from './features/buying-power/BuyingPowerSheet';
import { EverydayHome } from './features/home/EverydayHome';
import { SmartSalaryAllocation } from './features/allocation/SmartSalaryAllocation';
import { Transactions } from './features/transactions/Transactions';
import { HomeTab } from './features/wealth-home/HomeTab';
import { HomeVariantA } from './features/home-concepts/HomeVariantA';
import { HomeVariantB } from './features/home-concepts/HomeVariantB';
import { HomeVariantC } from './features/home-concepts/HomeVariantC';
import { HomeVariantD } from './features/home-concepts/HomeVariantD';
import { MonitorSheet } from './features/home-concepts/DashboardRows';
import { PlanTab } from './features/plan/PlanTab';
import { SearchTab } from './features/search/SearchTab';
import { TradeTab } from './features/trade/TradeTab';
import { SimulatePanel } from './sim/SimulatePanel';
import { StatusBar } from './app-shell/shell';
import { StoreProvider, useStore } from './state/store';
import type { Screen } from './state/store';

const BANK_SUBSCREEN_TITLES: Record<Exclude<Screen, 'home'>, string> = {
  allocation: 'Smart Salary Allocation',
  budgeting: 'AI Budgeting',
  autoCover: 'Auto Cover',
  transactions: 'Transactions',
  card: 'Card',
  pay: 'Pay',
};

function Phone() {
  const { state, nav, home } = useStore();
  const onBankSubScreen = nav.tab === 'bank' && (nav.screen !== 'home' || nav.txnDetailId !== null);

  let content: React.ReactNode;
  let header: React.ReactNode;
  if (nav.tab === 'home' && nav.wealthOpen) {
    // The wealth breakdown, one level below either Home concept.
    header = <DetailTopBar title="Your wealth" onBack={() => nav.setWealthOpen(false)} />;
    content = <HomeTab />;
  } else if (nav.tab === 'home') {
    header = <TopBar />;
    content =
      home.variant === 'A' ? (
        <HomeVariantA />
      ) : home.variant === 'B' ? (
        <HomeVariantB />
      ) : home.variant === 'C' ? (
        <HomeVariantC />
      ) : (
        <HomeVariantD />
      );
  } else if (nav.tab === 'plan') {
    header = <TopBar />;
    content = <PlanTab />;
  } else if (nav.tab === 'trade') {
    header = <TopBar />;
    content = <TradeTab />;
  } else if (nav.tab === 'search') {
    header = null;
    content = <SearchTab />;
  } else if (!onBankSubScreen) {
    header = <TopBar />;
    content = <EverydayHome />;
  } else if (nav.screen === 'transactions' || nav.txnDetailId !== null) {
    header = (
      <DetailTopBar
        title={nav.txnDetailId !== null ? 'Transaction' : 'Transactions'}
        onBack={() => (nav.txnDetailId !== null ? nav.closeTxn() : nav.go('home'))}
      />
    );
    content = <Transactions />;
  } else {
    header = <DetailTopBar title={BANK_SUBSCREEN_TITLES[nav.screen as Exclude<Screen, 'home'>]} onBack={() => nav.go('home')} />;
    content =
      nav.screen === 'allocation' ? (
        <SmartSalaryAllocation />
      ) : nav.screen === 'budgeting' ? (
        <AiBudgeting />
      ) : nav.screen === 'card' ? (
        <CardManagement />
      ) : nav.screen === 'pay' ? (
        <PayHub />
      ) : (
        <AutoCover />
      );
  }

  return (
    <div className="phone">
      <ConceptBadge />
      <StatusBar />
      {header}
      <div className="phone__scroll">{content}</div>
      {/* The search screen is a full overlay in the app: keyboard up, no tab bar. */}
      {!onBankSubScreen && nav.tab !== 'search' && <BottomNav active={nav.tab} onSelect={nav.setTab} />}
      <BuyingPowerSheet />
      <MonitorSheet />
      <MarginCallModal />
      {/* Balance changes announced to screen readers (§7 accessibility). */}
      <div aria-live="polite" className="sr-only">
        {state.announcement}
      </div>
    </div>
  );
}

export default function App() {
  const [runId, setRunId] = useState(0);
  return (
    <StoreProvider key={runId}>
      <main className="stage">
        <Phone />
        <SimulatePanel onReset={() => setRunId((x) => x + 1)} />
      </main>
    </StoreProvider>
  );
}
