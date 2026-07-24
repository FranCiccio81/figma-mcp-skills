// SCR-10 — M3
// Coquille livrée en M1 (E2) ; le contenu (checklist d'onboarding, top matches,
// candidatures à relancer, rappel des sources) arrive avec E7/E8 au jalon M3.

import { ArrowRight, Briefcase, LayoutDashboard } from "lucide-react";
import Link from "next/link";
import { getTranslations } from "next-intl/server";
import { EmptyState } from "@/components/ui/empty-state";

export default async function DashboardPage() {
  const t = await getTranslations();

  return (
    <section aria-labelledby="dashboard-title" className="space-y-6">
      <h1 id="dashboard-title" className="text-2xl font-semibold text-content">
        {t("pages.dashboard.title")}
      </h1>
      {/* M2 : la zone Offres est disponible — carte d'accès direct (SCR-20). */}
      <Link
        href="/offres"
        className="group flex items-center justify-between gap-4 rounded-lg border border-border bg-surface p-5 transition-colors hover:border-action-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus focus-visible:ring-offset-2 focus-visible:ring-offset-surface"
      >
        <span className="flex items-start gap-4">
          <Briefcase aria-hidden="true" className="mt-0.5 h-6 w-6 shrink-0 text-action-primary" />
          <span>
            <span className="block text-base font-semibold text-content group-hover:text-action-primary">
              {t("pages.dashboard.exploreJobsTitle")}
            </span>
            <span className="mt-1 block text-sm text-content-secondary">
              {t("pages.dashboard.exploreJobsDescription")}
            </span>
          </span>
        </span>
        <ArrowRight aria-hidden="true" className="h-5 w-5 shrink-0 text-content-secondary" />
      </Link>

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
