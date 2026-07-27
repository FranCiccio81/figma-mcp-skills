"use client";

// SCR-10 (carte candidatures) — M4
// Compte des candidatures en cours par statut (`GET /applications`), avec
// lien vers SCR-40. Erreur par bloc : le reste du tableau de bord vit (03).

import { useQuery } from "@tanstack/react-query";
import { Send } from "lucide-react";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  APPLICATION_STATUS_ORDER,
  applicationKeys,
  listApplications,
} from "@/lib/api/applications";

const SUMMARY_LIMIT = 100;

/** Carte « Candidatures en cours » du tableau de bord (compte par statut). */
export function ApplicationsSummaryCard() {
  const t = useTranslations("dashboard.applications");
  const tStatus = useTranslations("applications.status");

  const applicationsQuery = useQuery({
    // Clé « summary » distincte de l'infinite query de SCR-40 : même endpoint,
    // structures de cache incompatibles (voir applicationKeys).
    queryKey: applicationKeys.summary({ limit: SUMMARY_LIMIT }),
    queryFn: ({ signal }) => listApplications({ limit: SUMMARY_LIMIT }, null, signal),
  });

  const counts = APPLICATION_STATUS_ORDER.map((status) => ({
    status,
    count:
      applicationsQuery.data?.items.filter((application) => application.status === status)
        .length ?? 0,
  })).filter((entry) => entry.count > 0);

  return (
    <section
      aria-labelledby="dashboard-applications-title"
      className="space-y-3 rounded-lg border border-border bg-surface p-5"
    >
      <h2
        id="dashboard-applications-title"
        className="flex items-center gap-2 text-base font-semibold text-content"
      >
        <Send aria-hidden="true" className="h-5 w-5 text-action-primary" />
        {t("title")}
      </h2>

      {applicationsQuery.isPending ? (
        <div role="status" aria-live="polite">
          <span className="sr-only">{t("loading")}</span>
          <div aria-hidden="true" className="h-16 animate-pulse rounded-md bg-surface-muted" />
        </div>
      ) : null}

      {applicationsQuery.isError ? (
        <Alert variant="error" title={t("errorTitle")}>
          <Button variant="secondary" onClick={() => void applicationsQuery.refetch()}>
            {t("retry")}
          </Button>
        </Alert>
      ) : null}

      {applicationsQuery.isSuccess ? (
        counts.length === 0 ? (
          <p className="text-sm text-content-secondary">{t("empty")}</p>
        ) : (
          <ul className="flex flex-wrap gap-2">
            {counts.map(({ status, count }) => (
              <li
                key={status}
                className="rounded-md border border-border bg-surface-muted px-2 py-1 text-sm text-content"
              >
                <span className="font-semibold">{count}</span> {tStatus(status)}
              </li>
            ))}
          </ul>
        )
      ) : null}

      <Link
        href="/candidatures"
        className="inline-flex min-h-11 items-center text-sm font-medium text-action-primary underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
      >
        {t("seeAll")}
      </Link>
    </section>
  );
}
