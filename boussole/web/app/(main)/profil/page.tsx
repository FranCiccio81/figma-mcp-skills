// SCR-50 — M1
// Profil canonique (E3) : import CV (SCR-05), revue provenance/confiance
// (SCR-06), édition par section. Livré plus tard dans M1 — placeholder ici.

import { User } from "lucide-react";
import { getTranslations } from "next-intl/server";
import { EmptyState } from "@/components/ui/empty-state";

export default async function ProfilePage() {
  const t = await getTranslations();

  return (
    <section aria-labelledby="profile-title" className="space-y-6">
      <h1 id="profile-title" className="text-2xl font-semibold text-content">
        {t("pages.profile.title")}
      </h1>
      <EmptyState
        icon={User}
        title={t("pages.profile.emptyTitle")}
        description={t("pages.profile.emptyDescription")}
      >
        <p className="text-sm font-medium text-content-secondary">
          {t("placeholder.availableAt", { milestone: "M1" })}
        </p>
      </EmptyState>
    </section>
  );
}
