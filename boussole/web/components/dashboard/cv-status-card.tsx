"use client";

// SCR-10 (checklist CV) — M4
// État « CV importé ou non » depuis `GET /me` (onboarding — jamais d'état
// local seul, 03 §3), avec lien direct vers le bloc d'import du profil.

import { useQuery } from "@tanstack/react-query";
import { CircleCheck, FileUp } from "lucide-react";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { getMe, meKeys } from "@/lib/api/me";

/** Carte « Mon CV » du tableau de bord : importé (✓) ou CTA d'import. */
export function CvStatusCard() {
  const t = useTranslations("dashboard.cv");

  const meQuery = useQuery({
    queryKey: meKeys.root,
    queryFn: ({ signal }) => getMe(signal),
  });

  return (
    <section
      aria-labelledby="dashboard-cv-title"
      className="space-y-3 rounded-lg border border-border bg-surface p-5"
    >
      <h2
        id="dashboard-cv-title"
        className="flex items-center gap-2 text-base font-semibold text-content"
      >
        <FileUp aria-hidden="true" className="h-5 w-5 text-action-primary" />
        {t("title")}
      </h2>

      {meQuery.isPending ? (
        <div role="status" aria-live="polite">
          <span className="sr-only">{t("loading")}</span>
          <div aria-hidden="true" className="h-12 animate-pulse rounded-md bg-surface-muted" />
        </div>
      ) : null}

      {meQuery.isError ? (
        <Alert variant="error" title={t("errorTitle")}>
          <Button variant="secondary" onClick={() => void meQuery.refetch()}>
            {t("retry")}
          </Button>
        </Alert>
      ) : null}

      {meQuery.isSuccess ? (
        meQuery.data.onboarding.cv_imported ? (
          <p className="flex items-center gap-2 text-sm text-content">
            <CircleCheck aria-hidden="true" className="h-5 w-5 shrink-0 text-feedback-success" />
            {t("imported")}
          </p>
        ) : (
          <p className="text-sm text-content-secondary">{t("notImported")}</p>
        )
      ) : null}

      <Link
        href="/profil#import-cv"
        className="inline-flex min-h-11 items-center text-sm font-medium text-action-primary underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
      >
        {meQuery.data?.onboarding.cv_imported ? t("reimportLink") : t("importLink")}
      </Link>
    </section>
  );
}
