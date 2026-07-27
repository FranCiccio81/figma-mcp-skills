"use client";

// SCR-21 — M3
// Détail d'une offre (Flux 4) : en-tête (titre, entreprise, lieux, badges,
// date), panneau match (score + confiance + bloquants + inconnues +
// dimensions + explication — voir MatchPanel), description en texte brut
// (espaces préservés), compétences, langue, sources avec liens d'origine
// (obligation produit), actions sauvegarder/masquer optimistes.

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, FilePen, Mail, Send } from "lucide-react";
import Link from "next/link";
import { notFound, useParams } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import { GenerateModal } from "@/components/generation/generate-modal";
import { JobBadges } from "@/components/jobs/job-badges";
import { SavedToggle } from "@/components/jobs/saved-toggle";
import { SourceList } from "@/components/jobs/source-list";
import { MatchPanel } from "@/components/match/match-panel";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { isApiProblem } from "@/lib/api/client";
import { clearSavedState, getJob, jobsKeys, setSavedState } from "@/lib/api/jobs";
import type { DocType, JobDetail, SavedState } from "@/lib/api/types";
import { formatDate } from "@/lib/format";

/**
 * Section « Candidater » (SCR-21 §6, M4) : génération de lettre / e-mail /
 * variante de CV (SCR-30 en modale) et suivi de candidature pré-rempli
 * (Flux 7 §1a). Génération désactivée sur offre expirée 🟡 (03 Q6) avec
 * explication — le suivi de candidature, lui, reste possible.
 */
function ApplySection({ job }: { job: JobDetail }) {
  const t = useTranslations("generation.actions");
  const [openDocType, setOpenDocType] = useState<DocType | null>(null);
  const isExpired = job.status === "expired";

  const trackHref = `/candidatures?suivre=${encodeURIComponent(job.id)}&titre=${encodeURIComponent(
    job.title,
  )}&entreprise=${encodeURIComponent(job.company_name)}`;

  const generationButtons: { docType: DocType; labelKey: "writeLetter" | "writeEmail" | "adaptCv"; icon: typeof Mail }[] = [
    { docType: "cover_letter", labelKey: "writeLetter", icon: FilePen },
    { docType: "email", labelKey: "writeEmail", icon: Mail },
    { docType: "cv_variant", labelKey: "adaptCv", icon: FilePen },
  ];

  return (
    <section aria-labelledby="job-apply-title" className="space-y-3 rounded-lg border border-border bg-surface p-4">
      <h2 id="job-apply-title" className="text-lg font-semibold text-content">
        {t("sectionTitle")}
      </h2>
      {isExpired ? (
        <p id="job-apply-expired" className="text-sm text-content-secondary">
          {t("expiredDisabled")}
        </p>
      ) : null}
      <div className="flex flex-wrap gap-2">
        {generationButtons.map(({ docType, labelKey, icon: Icon }) => (
          <Button
            key={docType}
            variant="secondary"
            disabled={isExpired}
            aria-describedby={isExpired ? "job-apply-expired" : undefined}
            onClick={() => setOpenDocType(docType)}
          >
            <Icon aria-hidden="true" className="h-4 w-4" />
            {t(labelKey)}
          </Button>
        ))}
        <Link
          href={trackHref}
          className="inline-flex min-h-11 items-center gap-2 rounded-md bg-action-primary px-4 text-sm font-medium text-content-on-action transition-colors hover:bg-action-primary-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus focus-visible:ring-offset-2 focus-visible:ring-offset-surface"
        >
          <Send aria-hidden="true" className="h-4 w-4" />
          {t("trackApplication")}
        </Link>
      </div>
      {/* Rappel M6 — aucune candidature automatique. */}
      <p className="text-sm text-content-secondary">{t("noAutoSend")}</p>

      {openDocType ? (
        <GenerateModal
          docType={openDocType}
          jobId={job.id}
          jobLanguage={job.language}
          onClose={() => setOpenDocType(null)}
        />
      ) : null}
    </section>
  );
}

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

  // Échec de mutation : rollback + message visible (04 §conventions — jamais
  // de retour silencieux à l'état antérieur).
  const [actionError, setActionError] = useState<string | null>(null);

  const savedMutation = useMutation({
    mutationFn: (nextState: SavedState | null) =>
      nextState ? setSavedState(id, nextState) : clearSavedState(id),
    onMutate: async (nextState) => {
      setActionError(null);
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
      setActionError(t("jobs.list.actionError"));
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
        {actionError ? <Alert variant="error">{actionError}</Alert> : null}
      </header>

      {/* Panneau match (SCR-21 §3) — requête dédiée `GET /jobs/{id}/match`. */}
      <MatchPanel jobId={id} />

      {/* Candidater (M4) : génération SCR-30 + suivi de candidature (Flux 7). */}
      <ApplySection job={job} />

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
