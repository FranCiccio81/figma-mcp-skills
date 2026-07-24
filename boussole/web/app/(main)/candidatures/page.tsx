// SCR-40 — M4
// Suivi des candidatures (E11) : colonnes par statut, historique des
// transitions, ajout de candidatures externes (SCR-42).

import { Send } from "lucide-react";
import { getTranslations } from "next-intl/server";
import { EmptyState } from "@/components/ui/empty-state";

export default async function ApplicationsPage() {
  const t = await getTranslations();

  return (
    <section aria-labelledby="applications-title" className="space-y-6">
      <h1 id="applications-title" className="text-2xl font-semibold text-content">
        {t("pages.applications.title")}
      </h1>
      <EmptyState
        icon={Send}
        title={t("pages.applications.emptyTitle")}
        description={t("pages.applications.emptyDescription")}
      >
        <p className="text-sm font-medium text-content-secondary">
          {t("placeholder.availableAt", { milestone: "M4" })}
        </p>
      </EmptyState>
    </section>
  );
}
