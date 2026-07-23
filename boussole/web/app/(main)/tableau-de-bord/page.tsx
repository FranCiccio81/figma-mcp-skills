// SCR-10 — M3
// Coquille livrée en M1 (E2) ; le contenu (checklist d'onboarding, top matches,
// candidatures à relancer, rappel des sources) arrive avec E7/E8 au jalon M3.

import { LayoutDashboard } from "lucide-react";
import { getTranslations } from "next-intl/server";
import { EmptyState } from "@/components/ui/empty-state";

export default async function DashboardPage() {
  const t = await getTranslations();

  return (
    <section aria-labelledby="dashboard-title" className="space-y-6">
      <h1 id="dashboard-title" className="text-2xl font-semibold text-content">
        {t("pages.dashboard.title")}
      </h1>
      <EmptyState
        icon={LayoutDashboard}
        title={t("pages.dashboard.emptyTitle")}
        description={t("pages.dashboard.emptyDescription")}
      >
        <p className="text-sm font-medium text-content-secondary">
          {t("placeholder.availableAt", { milestone: "M3" })}
        </p>
      </EmptyState>
    </section>
  );
}
