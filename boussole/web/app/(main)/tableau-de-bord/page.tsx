// SCR-10 — M4 (partiel)
// Coquille livrée en M1 (E2) ; M3 : carte « Meilleures correspondances »
// (GET /matches, TopMatchesCard) ; M4 : carte candidatures en cours (compte
// par statut) et carte CV importé/non (lien vers l'import du profil).
// Reste à venir (M5) : candidatures à relancer (J+10), rappel des sources.

import { ArrowRight, Briefcase } from "lucide-react";
import Link from "next/link";
import { getTranslations } from "next-intl/server";
import { ApplicationsSummaryCard } from "@/components/dashboard/applications-summary-card";
import { CvStatusCard } from "@/components/dashboard/cv-status-card";
import { TopMatchesCard } from "@/components/match/top-matches-card";

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

      {/* M3 : meilleures correspondances (GET /matches, 5 premiers résultats). */}
      <TopMatchesCard />

      {/* M4 : candidatures par statut + état d'import du CV (blocs
          indépendants — l'erreur d'un bloc ne bloque pas les autres, 03). */}
      <div className="grid gap-6 lg:grid-cols-2">
        <ApplicationsSummaryCard />
        <CvStatusCard />
      </div>
    </section>
  );
}
