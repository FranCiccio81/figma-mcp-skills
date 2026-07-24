// SCR-70 — M5
// Paramètres (E12/E14) : compte & sécurité (SCR-70), confidentialité & données
// (SCR-71), suppression du compte (SCR-72), sources (SCR-73), méthode (SCR-74).
// La déconnexion est déjà disponible dans la navigation (M1).

import { Settings } from "lucide-react";
import { getTranslations } from "next-intl/server";
import { EmptyState } from "@/components/ui/empty-state";

export default async function SettingsPage() {
  const t = await getTranslations();

  return (
    <section aria-labelledby="settings-title" className="space-y-6">
      <h1 id="settings-title" className="text-2xl font-semibold text-content">
        {t("pages.settings.title")}
      </h1>
      <EmptyState
        icon={Settings}
        title={t("pages.settings.emptyTitle")}
        description={t("pages.settings.emptyDescription")}
      >
        <p className="text-sm font-medium text-content-secondary">
          {t("placeholder.availableAt", { milestone: "M5" })}
        </p>
      </EmptyState>
    </section>
  );
}
