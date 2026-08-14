/**
 * PlanBar — the §28 salary-plan visual: keep-first segment, then the
 * allocation splits. Shared by the Bank-home Smart Liquidity card and the
 * allocation screen. Colours are the CVD-validated plan palette; identity is
 * always also carried by the labels rendered next to it.
 */
import type { AllocationSplit } from '../state/types';

export const PLAN_SWATCH: Record<string, string> = {
  keep: 'plan-bar__segment--keep',
  saveEasy: 'plan-bar__segment--saveEasy',
  investEasy: 'plan-bar__segment--investEasy',
  tradingCash: 'plan-bar__segment--tradingCash',
  savingPlan: 'plan-bar__segment--savingPlan',
  goal: 'plan-bar__segment--saveEasy',
};

export function PlanBar({ buffer, estTotal, splits }: { buffer: number; estTotal: number; splits: AllocationSplit[] }) {
  const scale = buffer + estTotal || 1;
  return (
    <div className="plan-bar" aria-hidden="true">
      <span className="plan-bar__segment plan-bar__segment--keep" style={{ width: `${Math.max(6, (buffer / scale) * 100)}%` }} />
      {splits.map((s) => (
        <span
          key={s.destination}
          className={`plan-bar__segment ${PLAN_SWATCH[s.destination]}`}
          style={{ width: `${Math.max(2, ((estTotal * s.percent) / 100 / scale) * 100)}%` }}
        />
      ))}
    </div>
  );
}
