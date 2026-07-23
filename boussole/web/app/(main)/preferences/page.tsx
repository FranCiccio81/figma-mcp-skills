// SCR-07 — M1
// Préférences de recherche (E4, début en M1, fin en M2) : écran unique à deux
// contextes (onboarding et navigation), `GET/PUT /preferences` payload complet.

import { SlidersHorizontal } from "lucide-react";
import { getTranslations } from "next-intl/server";
import { EmptyState } from "@/components/ui/empty-state";

export default async function PreferencesPage() {
  const t = await getTranslations();

  return (
    <section aria-labelledby="preferences-title" className="space-y-6">
      <h1 id="preferences-title" className="text-2xl font-semibold text-content">
        {t("pages.preferences.title")}
      </h1>
      <EmptyState
        icon={SlidersHorizontal}
        title={t("pages.preferences.emptyTitle")}
        description={t("pages.preferences.emptyDescription")}
      >
        <p className="text-sm font-medium text-content-secondary">
          {t("placeholder.availableAt", { milestone: "M1" })}
        </p>
      </EmptyState>
    </section>
  );
}
