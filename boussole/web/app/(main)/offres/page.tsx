// SCR-20 — M2
// Recherche & liste d'offres (E5/E6) : filtres, tri match/date/relevance,
// pagination par curseur (« Charger plus »), scores + confiance côte à côte.

import { Briefcase } from "lucide-react";
import { getTranslations } from "next-intl/server";
import { EmptyState } from "@/components/ui/empty-state";

export default async function JobsPage() {
  const t = await getTranslations();

  return (
    <section aria-labelledby="jobs-title" className="space-y-6">
      <h1 id="jobs-title" className="text-2xl font-semibold text-content">
        {t("pages.jobs.title")}
      </h1>
      <EmptyState
        icon={Briefcase}
        title={t("pages.jobs.emptyTitle")}
        description={t("pages.jobs.emptyDescription")}
      >
        <p className="text-sm font-medium text-content-secondary">
          {t("placeholder.availableAt", { milestone: "M2" })}
        </p>
      </EmptyState>
    </section>
  );
}
