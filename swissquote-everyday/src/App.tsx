/**
 * App shell — the 390×844 phone frame (holds at 320), screen switch, overlay
 * sheets, the interruptive margin-call modal, the screen-reader live region,
 * and the Simulate rig beside the phone.
 */
import { useState } from 'react';
import { MarginCallModal } from './components/MarginCallModal';
import { ConceptBadge } from './components/ui';
import { AutoCover } from './features/auto-cover/AutoCover';
import { AiBudgeting } from './features/budgeting/AiBudgeting';
import { BuyingPowerSheet } from './features/buying-power/BuyingPowerSheet';
import { EverydayHome } from './features/home/EverydayHome';
import { SmartSalaryAllocation } from './features/allocation/SmartSalaryAllocation';
import { Transactions } from './features/transactions/Transactions';
import { SimulatePanel } from './sim/SimulatePanel';
import { StoreProvider, useStore } from './state/store';

function Phone() {
  const { state, nav } = useStore();
  return (
    <div className="phone">
      <ConceptBadge />
      <div className="phone__scroll">
        {nav.screen === 'home' && <EverydayHome />}
        {nav.screen === 'allocation' && <SmartSalaryAllocation />}
        {nav.screen === 'budgeting' && <AiBudgeting />}
        {nav.screen === 'autoCover' && <AutoCover />}
        {nav.screen === 'transactions' && <Transactions />}
      </div>
      <BuyingPowerSheet />
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
