"use client";

import Link from "next/link";
import { useLocale, useTranslations } from "next-intl";
import { JobBadges } from "@/components/jobs/job-badges";
import { SavedToggle } from "@/components/jobs/saved-toggle";
import { formatDate } from "@/lib/format";
import type { JobCard as JobCardData, SavedState } from "@/lib/api/types";

export interface JobCardProps {
  job: JobCardData;
  /** Bascule sauvegarde/masquage — voir {@link SavedToggle}. */
  onSavedStateChange: (state: SavedState | null) => void;
  /** Désactive les actions pendant une mutation en vol sur cette offre. */
  actionsDisabled?: boolean;
}

/**
 * Carte d'offre de la liste SCR-20 (Flux 3 §2/§5) : titre (lien vers le
 * détail avec intitulé d'accessibilité complet poste + entreprise), lieux,
 * badges contrat/télétravail, salaire (« Salaire non communiqué » si `null`,
 * microcopie M3-a — jamais d'estimation), date de publication, actions
 * sauvegarder/masquer. Pas de score au jalon M2 (`match` est `null`).
 */
export function JobCard({ job, onSavedStateChange, actionsDisabled }: JobCardProps) {
  const t = useTranslations("jobs.card");
  const locale = useLocale();
  const postedDate = formatDate(job.posted_at, locale);
  const headingId = `job-${job.id}-title`;

  return (
    <article
      aria-labelledby={headingId}
      className="space-y-3 rounded-lg border border-border bg-surface p-4"
    >
      <div className="space-y-1">
        <h3 id={headingId} className="text-base font-semibold text-content">
          <Link
            href={`/offres/${job.id}`}
            aria-label={t("linkAria", { title: job.title, company: job.company_name })}
            className="rounded-sm underline-offset-4 hover:text-action-primary hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
          >
            {job.title}
          </Link>
        </h3>
        <p className="text-sm text-content-secondary">
          {job.company_name}
          {job.locations.length > 0 ? ` — ${job.locations.join(" · ")}` : ""}
        </p>
      </div>

      <JobBadges contract={job.contract} remote={job.remote} />

      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm">
        {job.salary_label ? (
          <span className="font-medium text-content">{job.salary_label}</span>
        ) : (
          <span className="text-content-secondary">{t("salaryNotDisclosed")}</span>
        )}
        {postedDate ? (
          <span className="text-content-secondary">{t("postedOn", { date: postedDate })}</span>
        ) : null}
      </div>

      <SavedToggle
        savedState={job.saved_state}
        jobTitle={job.title}
        onChange={onSavedStateChange}
        disabled={actionsDisabled}
      />
    </article>
  );
}
