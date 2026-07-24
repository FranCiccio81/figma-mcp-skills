"use client";

// SCR-10 (extrait) — M3
// Carte « Meilleures correspondances » du tableau de bord : les 5 premiers
// résultats de `GET /matches` (titre, entreprise, score + confiance M1-a),
// lien vers /offres?sort=match. Profil non validé (409) → état vide avec
// lien vers /profil (gating 03 §3), jamais d'erreur brute.

import { useQuery } from "@tanstack/react-query";
import { ArrowRight, Target } from "lucide-react";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { MatchBadge } from "@/components/match/match-badge";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { getMatches, isProfileNotValidated, matchKeys } from "@/lib/api/matching";

const TOP_MATCHES_COUNT = 5;

/**
 * Carte des meilleures correspondances (SCR-10). L'intitulé d'accessibilité
 * de chaque lien reprend poste, entreprise, score et confiance (Flux 3 a11y).
 */
export function TopMatchesCard() {
  const t = useTranslations("dashboard.topMatches");
  const tCard = useTranslations("jobs.card");

  const matchesQuery = useQuery({
    queryKey: matchKeys.list({ limit: TOP_MATCHES_COUNT }),
    queryFn: ({ signal }) => getMatches({ limit: TOP_MATCHES_COUNT }, undefined, signal),
  });

  const notValidated = matchesQuery.isError && isProfileNotValidated(matchesQuery.error);

  return (
    <section
      aria-labelledby="top-matches-title"
      className="space-y-4 rounded-lg border border-border bg-surface p-5"
    >
      <h2
        id="top-matches-title"
        className="flex items-center gap-2 text-lg font-semibold text-content"
      >
        <Target aria-hidden="true" className="h-5 w-5 text-action-primary" />
        {t("title")}
      </h2>

      {matchesQuery.isPending ? (
        <div role="status" aria-live="polite">
          <span className="sr-only">{t("loading")}</span>
          <div aria-hidden="true" className="h-40 animate-pulse rounded-md bg-surface-muted" />
        </div>
      ) : null}

      {notValidated ? (
        <div className="space-y-2">
          <p className="text-sm text-content-secondary">{t("notValidated")}</p>
          <Link
            href="/profil"
            className="inline-flex min-h-11 items-center gap-1.5 text-sm font-medium text-action-primary underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
          >
            {t("notValidatedCta")}
            <ArrowRight aria-hidden="true" className="h-4 w-4" />
          </Link>
        </div>
      ) : null}

      {matchesQuery.isError && !notValidated ? (
        <Alert variant="error" title={t("errorTitle")}>
          <Button variant="secondary" onClick={() => void matchesQuery.refetch()}>
            {t("retry")}
          </Button>
        </Alert>
      ) : null}

      {matchesQuery.isSuccess ? (
        matchesQuery.data.items.length === 0 ? (
          <p className="text-sm text-content-secondary">{t("empty")}</p>
        ) : (
          <>
            <ol className="space-y-3">
              {matchesQuery.data.items.slice(0, TOP_MATCHES_COUNT).map((job) => (
                <li key={job.id} className="rounded-md border border-border p-3">
                  <p className="text-sm font-semibold text-content">
                    <Link
                      href={`/offres/${job.id}`}
                      aria-label={
                        job.match
                          ? tCard("linkAriaWithMatch", {
                              title: job.title,
                              company: job.company_name,
                              score: job.match.score,
                              confidence: job.match.confidence,
                            })
                          : tCard("linkAria", { title: job.title, company: job.company_name })
                      }
                      className="rounded-sm underline-offset-4 hover:text-action-primary hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
                    >
                      {job.title}
                    </Link>
                  </p>
                  <p className="text-sm text-content-secondary">{job.company_name}</p>
                  <MatchBadge match={job.match} />
                </li>
              ))}
            </ol>
            <Link
              href="/offres?sort=match"
              className="inline-flex min-h-11 items-center gap-1.5 text-sm font-medium text-action-primary underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
            >
              {t("seeAll")}
              <ArrowRight aria-hidden="true" className="h-4 w-4" />
            </Link>
          </>
        )
      ) : null}
    </section>
  );
}
