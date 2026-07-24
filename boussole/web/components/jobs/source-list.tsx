"use client";

import { ExternalLink } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { formatDate } from "@/lib/format";
import type { JobSourceLink } from "@/lib/api/types";

export interface SourceListProps {
  sources: JobSourceLink[];
}

/**
 * Section « Sources » du détail d'offre (SCR-21, Flux 4 §2 — obligation
 * produit : chaque offre affiche sa ou ses sources avec lien d'origine).
 * Chaque ligne : nom de la source, lien externe `original_url`
 * (`rel="noopener noreferrer"`, icône lien externe, mention « nouvelle
 * fenêtre » pour les lecteurs d'écran), date de publication si connue.
 */
export function SourceList({ sources }: SourceListProps) {
  const t = useTranslations("jobs.detail");
  const locale = useLocale();

  return (
    <ul className="space-y-1">
      {sources.map((source) => {
        const postedDate = formatDate(source.posted_at, locale);
        return (
          <li key={source.original_url} className="flex flex-wrap items-center gap-x-2 text-sm">
            <a
              href={source.original_url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex min-h-11 items-center gap-1.5 rounded-sm font-medium text-action-primary underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
            >
              <ExternalLink aria-hidden="true" className="h-4 w-4 shrink-0" />
              {t("sourceLink", { name: source.name })}
              <span className="sr-only"> {t("sourceExternalHint")}</span>
            </a>
            {postedDate ? (
              <span className="text-content-secondary">
                {t("sourcePostedOn", { date: postedDate })}
              </span>
            ) : null}
          </li>
        );
      })}
    </ul>
  );
}
