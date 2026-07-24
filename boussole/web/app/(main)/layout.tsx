import { getTranslations } from "next-intl/server";
import type { ReactNode } from "react";
import { MainNav } from "@/components/layout/main-nav";

/**
 * Coquille authentifiée (03 §3) : sidebar desktop / barre inférieure mobile,
 * lien d'évitement vers le contenu, landmark `main` unique. La garde de
 * session est assurée par `middleware.ts`.
 */
export default async function MainLayout({ children }: { children: ReactNode }) {
  const t = await getTranslations("common");

  return (
    <div className="flex min-h-screen flex-col lg:flex-row">
      <a
        href="#contenu"
        className="sr-only z-20 rounded-md bg-surface px-4 py-2 text-sm font-medium text-action-primary focus:not-sr-only focus:fixed focus:left-4 focus:top-4"
      >
        {t("skipToContent")}
      </a>
      <MainNav />
      <main id="contenu" className="flex-1 px-4 py-8 pb-24 sm:px-6 lg:px-10 lg:pb-8">
        <div className="mx-auto w-full max-w-5xl">{children}</div>
      </main>
    </div>
  );
}
