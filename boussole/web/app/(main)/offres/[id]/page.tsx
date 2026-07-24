"use client";

// SCR-21 — M2 (partiel)
// Détail d'une offre (Flux 4) : en-tête (titre, entreprise, lieux, badges,
// date), description en texte brut (espaces préservés), compétences, langue,
// sources avec liens d'origine (obligation produit), actions sauvegarder/
// masquer optimistes. Le panneau match (score + confiance + explication)
// arrive au jalon M3 : en attendant, une carte placeholder l'annonce —
// jamais de faux score (`match` est `null`).

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Compass } from "lucide-react";
import Link from "next/link";
import { notFound, useParams } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import { JobBadges } from "@/components/jobs/job-badges";
import { SavedToggle } from "@/components/jobs/saved-toggle";
import { SourceList } from "@/components/jobs/source-list";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { isApiProblem } from "@/lib/api/client";
import { clearSavedState, getJob, jobsKeys, setSavedState } from "@/lib/api/jobs";
import type { JobDetail, SavedState } from "@/lib/api/types";
import { formatDate } from "@/lib/format";

/** Liste de compétences en puces — requises ou souhaitées (SCR-21). */
function SkillList({ titleId, title, skills }: { titleId: string; title: string; skills: string[] }) {
  if (skills.length === 0) return null;
  return (
    <section aria-labelledby={titleId} className="space-y-2">
      <h2 id={titleId} className="text-lg font-semibold text-content">
        {title}
      </h2>
      <ul className="flex flex-wrap gap-2">
        {skills.map((skill) => (
          <li
            key={skill}
            className="rounded-md border border-border bg-surface-muted px-2 py-1 text-sm text-content"
          >
            {skill}
          </li>
        ))}
      </ul>
    </section>
  );
}

export default function JobDetailPage() {
  const t = useTranslations();
  const locale = useLocale();
  const params = useParams<{ id: string }>();
  const id = params.id;
  const queryClient = useQueryClient();

  const jobQuery = useQuery({
    queryKey: jobsKeys.detail(id),
    queryFn: ({ signal }) => getJob(id, signal),
  });

  const savedMutation = useMutation({
    mutationFn: (nextState: SavedState | null) =>
      nextState ? setSavedState(id, nextState) : clearSavedState(id),
    onMutate: async (nextState) => {
      await queryClient.cancelQueries({ queryKey: jobsKeys.detail(id) });
      const previous = queryClient.getQueryData<JobDetail>(jobsKeys.detail(id));
      if (previous) {
        queryClient.setQueryData<JobDetail>(jobsKeys.detail(id), {
          ...previous,
          saved_state: nextState,
        });
      }
      return { previous };
    },
    onError: (_error, _vars, context) => {
      if (context?.previous) {
        queryClient.setQueryData(jobsKeys.detail(id), context.previous);
      }
    },
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: jobsKeys.detail(id) });
      // Les listes reflètent le nouvel état (offre masquée retirée, etc.).
      void queryClient.invalidateQueries({ queryKey: jobsKeys.searches() });
    },
  });

  // 404 (offre supprimée ou d'autrui, anti-énumération 12 §5) → SCR-90.
  if (jobQuery.error && isApiProblem(jobQuery.error) && jobQuery.error.status === 404) {
    notFound();
  }

  const backLink = (
    <Link
      href="/offres"
      className="inline-flex min-h-11 items-center gap-1.5 rounded-sm text-sm font-medium text-action-primary underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
    >
      <ArrowLeft aria-hidden="true" className="h-4 w-4" />
      {t("jobs.detail.backToList")}
    </Link>
  );

  if (jobQuery.isPending) {
    return (
      <section className="space-y-6">
        {backLink}
        <div role="status" aria-live="polite" className="space-y-4">
          <span className="sr-only">{t("common.loading")}</span>
          <div aria-hidden="true" className="h-24 animate-pulse rounded-lg bg-surface-muted" />
          <div aria-hidden="true" className="h-64 animate-pulse rounded-lg bg-surface-muted" />
        </div>
      </section>
    );
  }

  if (jobQuery.isError) {
    return (
      <section className="space-y-6">
        {backLink}
        <Alert variant="error" title={t("jobs.detail.errorTitle")}>
          <Button variant="secondary" onClick={() => void jobQuery.refetch()}>
            {t("jobs.list.retry")}
          </Button>
        </Alert>
      </section>
    );
  }

  const job = jobQuery.data;
  const postedDate = formatDate(job.posted_at, locale);
  const expiredDate = formatDate(job.expires_at, locale);
  const isExpired = job.status === "expired";

  return (
    <article aria-labelledby="job-detail-title" className="space-y-8">
      {backLink}

      {isExpired ? (
        <Alert variant="warning">
          {expiredDate
            ? t("jobs.detail.expiredBanner", { date: expiredDate })
            : t("jobs.detail.expiredBannerNoDate")}
        </Alert>
      ) : null}

      <header className="space-y-3">
        <h1 id="job-detail-title" className="text-2xl font-semibold text-content">
          {job.title}
        </h1>
        <p className="text-base text-content-secondary">
          {job.company_name}
          {job.locations.length > 0 ? ` — ${job.locations.join(" · ")}` : ""}
        </p>
        <JobBadges contract={job.contract} remote={job.remote} />
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm">
          {job.salary_label ? (
            <span className="font-medium text-content">{job.salary_label}</span>
          ) : (
            <span className="text-content-secondary">{t("jobs.card.salaryNotDisclosed")}</span>
          )}
          {postedDate ? (
            <span className="text-content-secondary">
              {t("jobs.card.postedOn", { date: postedDate })}
            </span>
          ) : null}
        </div>
        <SavedToggle
          savedState={job.saved_state}
          jobTitle={job.title}
          onChange={(nextState) => savedMutation.mutate(nextState)}
          disabled={savedMutation.isPending}
        />
      </header>

      {/* Emplacement du panneau match (SCR-21) — placeholder tant que match=null. */}
      <section
        aria-labelledby="job-match-title"
        className="space-y-2 rounded-lg border border-border bg-surface-muted p-4"
      >
        <h2 id="job-match-title" className="flex items-center gap-2 text-lg font-semibold text-content">
          <Compass aria-hidden="true" className="h-5 w-5" />
          {t("jobs.detail.matchTitle")}
        </h2>
        {job.match ? (
          <p className="text-sm text-content">
            {t("jobs.detail.matchSummary", {
              score: job.match.score,
              confidence: job.match.confidence,
            })}
          </p>
        ) : (
          <p className="text-sm text-content-secondary">{t("jobs.detail.matchPlaceholder")}</p>
        )}
      </section>

      <section aria-labelledby="job-description-title" className="space-y-2">
        <h2 id="job-description-title" className="text-lg font-semibold text-content">
          {t("jobs.detail.descriptionTitle")}
        </h2>
        {/* Texte brut de la source, espaces et sauts de ligne préservés. */}
        <p className="whitespace-pre-wrap text-sm leading-relaxed text-content">
          {job.description_text}
        </p>
      </section>

      <SkillList
        titleId="job-skills-required-title"
        title={t("jobs.detail.skillsRequiredTitle")}
        skills={job.skills_required}
      />
      <SkillList
        titleId="job-skills-nice-title"
        title={t("jobs.detail.skillsNiceTitle")}
        skills={job.skills_nice}
      />

      <section aria-labelledby="job-about-title" className="space-y-2">
        <h2 id="job-about-title" className="text-lg font-semibold text-content">
          {t("jobs.detail.aboutTitle")}
        </h2>
        <dl className="grid gap-x-8 gap-y-2 text-sm sm:grid-cols-2">
          <div>
            <dt className="font-medium text-content">{t("jobs.detail.languageLabel")}</dt>
            <dd className="text-content-secondary">
              {job.language || t("jobs.detail.notSpecified")}
            </dd>
          </div>
          <div>
            <dt className="font-medium text-content">{t("jobs.detail.seniorityLabel")}</dt>
            <dd className="text-content-secondary">
              {job.seniority
                ? t(`jobs.seniority.${job.seniority}`)
                : t("jobs.detail.notSpecified")}
            </dd>
          </div>
        </dl>
      </section>

      <section aria-labelledby="job-sources-title" className="space-y-2">
        <h2 id="job-sources-title" className="text-lg font-semibold text-content">
          {t("jobs.detail.sourcesTitle")}
        </h2>
        <p className="text-sm text-content-secondary">{t("jobs.detail.sourcesIntro")}</p>
        <SourceList sources={job.sources} />
      </section>
    </article>
  );
}
