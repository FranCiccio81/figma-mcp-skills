import { getTranslations } from "next-intl/server";
import type { ReactNode } from "react";

/**
 * Coquille de la zone publique (SCR-01…04) : carte centrée sur fond neutre,
 * nom du produit en tête. Le seul spinner plein écran autorisé est ici (03 §2).
 */
export default async function AuthLayout({ children }: { children: ReactNode }) {
  const t = await getTranslations("common");

  return (
    <main className="flex min-h-screen flex-col items-center justify-center bg-surface-muted px-4 py-10">
      <p className="mb-6 text-2xl font-bold text-content">{t("appName")}</p>
      <div className="w-full max-w-md rounded-lg border border-border bg-surface p-8 shadow-sm">
        {children}
      </div>
    </main>
  );
}
