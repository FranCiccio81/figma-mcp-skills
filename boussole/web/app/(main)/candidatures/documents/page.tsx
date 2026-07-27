"use client";

// « Mes documents » — M4 (03 §5 Q1 : bibliothèque des contenus générés,
// GET /generations). Rattachée à la section Candidatures (les documents
// générés vivent avec le suivi de candidature — 03 SCR-41). Filtres type /
// statut, pagination par curseur (« Charger plus », jamais de scroll infini
// sans bouton), lien vers l'offre liée et vers la relecture (SCR-31).

import { useInfiniteQuery } from "@tanstack/react-query";
import { FileText } from "lucide-react";
import Link from "next/link";
import { useLocale, useTranslations } from "next-intl";
import { useMemo, useState } from "react";
import { AnchoringBadge, GenerationStatusBadge } from "@/components/generation/badges";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { getNextCursor } from "@/lib/api/client";
import { generationKeys, listGenerations, type GenerationListParams } from "@/lib/api/generations";
import type { DocType, GeneratedDocument, GenerationStatus, Page } from "@/lib/api/types";
import { formatDate } from "@/lib/format";

const PAGE_SIZE = 20;

const DOC_TYPES: readonly DocType[] = ["email", "cover_letter", "cv_variant", "cv_optimization"];
const STATUSES: readonly GenerationStatus[] = [
  "pending",
  "draft",
  "validated",
  "exported",
  "failed",
];

const selectClass =
  "h-11 rounded-md border border-border bg-surface px-3 text-sm text-content focus:border-action-primary focus:shadow-input-focus focus:outline-none";

/** Carte d'un document généré dans la bibliothèque. */
function DocumentRow({ document }: { document: GeneratedDocument }) {
  const t = useTranslations("generation");
  const locale = useLocale();
  const createdDate = formatDate(document.created_at, locale);

  return (
    <li className="space-y-2 rounded-lg border border-border bg-surface p-4">
      <div className="flex flex-wrap items-center gap-2">
        {/* `inline-flex items-center` : sans display flex, `min-h-11` ne
            s'applique pas à un élément inline et la cible tactile retombe
            à ~24 px (WCAG 2.5.5 / conventions du repo). */}
        <Link
          href={`/candidatures/documents/${document.id}`}
          className="inline-flex min-h-11 items-center rounded-sm text-base font-semibold text-content underline-offset-4 hover:text-action-primary hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
        >
          {t(`docTypes.${document.doc_type}`)}
        </Link>
        <GenerationStatusBadge status={document.status} />
        {document.status !== "pending" && document.status !== "failed" ? (
          <AnchoringBadge check={document.anchoring_check} />
        ) : null}
      </div>
      <p className="flex flex-wrap gap-x-4 gap-y-1 text-sm text-content-secondary">
        {createdDate ? <span>{t("list.createdOn", { date: createdDate })}</span> : null}
        <span>{t("document.basedOn", { version: document.based_on_profile_version })}</span>
      </p>
      {document.job_id ? (
        <Link
          href={`/offres/${document.job_id}`}
          className="inline-flex min-h-11 items-center text-sm font-medium text-action-primary underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
        >
          {t("document.viewJob")}
        </Link>
      ) : null}
    </li>
  );
}

export default function GenerationsPage() {
  const t = useTranslations("generation.list");
  const tGen = useTranslations("generation");

  const [docType, setDocType] = useState<DocType | "">("");
  const [status, setStatus] = useState<GenerationStatus | "">("");

  const params = useMemo<GenerationListParams>(
    () => ({
      doc_type: docType || undefined,
      status: status || undefined,
      limit: PAGE_SIZE,
    }),
    [docType, status],
  );

  const documentsQuery = useInfiniteQuery({
    queryKey: generationKeys.list(params),
    queryFn: ({ pageParam, signal }) => listGenerations(params, pageParam, signal),
    initialPageParam: null as string | null,
    getNextPageParam: (page: Page<GeneratedDocument>) => getNextCursor(page) ?? null,
  });

  const documents = useMemo(
    () => documentsQuery.data?.pages.flatMap((page) => page.items) ?? [],
    [documentsQuery.data],
  );

  return (
    <section aria-labelledby="generations-title" className="space-y-6">
      <h1 id="generations-title" className="text-2xl font-semibold text-content">
        {t("title")}
      </h1>
      <p className="max-w-prose text-sm text-content-secondary">{t("intro")}</p>

      <div className="flex flex-wrap items-end gap-3">
        <div className="space-y-1.5">
          <label htmlFor="generations-type" className="block text-sm font-medium text-content">
            {t("typeFilterLabel")}
          </label>
          <select
            id="generations-type"
            value={docType}
            onChange={(event) => setDocType(event.target.value as DocType | "")}
            className={selectClass}
          >
            <option value="">{t("allTypes")}</option>
            {DOC_TYPES.map((type) => (
              <option key={type} value={type}>
                {tGen(`docTypes.${type}`)}
              </option>
            ))}
          </select>
        </div>
        <div className="space-y-1.5">
          <label htmlFor="generations-status" className="block text-sm font-medium text-content">
            {t("statusFilterLabel")}
          </label>
          <select
            id="generations-status"
            value={status}
            onChange={(event) => setStatus(event.target.value as GenerationStatus | "")}
            className={selectClass}
          >
            <option value="">{t("allStatuses")}</option>
            {STATUSES.map((value) => (
              <option key={value} value={value}>
                {tGen(`status.${value}`)}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Annonce du nombre de documents après chaque filtrage. */}
      <p role="status" aria-live="polite" className="text-sm text-content-secondary">
        {documentsQuery.isSuccess ? t("resultsCount", { count: documents.length }) : null}
      </p>

      {documentsQuery.isPending ? (
        <div role="status" aria-live="polite" className="space-y-3">
          <span className="sr-only">{t("loading")}</span>
          {Array.from({ length: 3 }, (_, index) => (
            <div
              key={index}
              aria-hidden="true"
              className="h-28 animate-pulse rounded-lg border border-border bg-surface-muted"
            />
          ))}
        </div>
      ) : null}

      {documentsQuery.isError ? (
        <Alert variant="error" title={t("errorTitle")}>
          <Button variant="secondary" onClick={() => void documentsQuery.refetch()}>
            {t("retry")}
          </Button>
        </Alert>
      ) : null}

      {documentsQuery.isSuccess && documents.length === 0 ? (
        <EmptyState icon={FileText} title={t("emptyTitle")} description={t("emptyDescription")} />
      ) : null}

      {documents.length > 0 ? (
        <>
          <ul className="space-y-3">
            {documents.map((document) => (
              <DocumentRow key={document.id} document={document} />
            ))}
          </ul>
          {documentsQuery.hasNextPage ? (
            <div className="flex justify-center">
              <Button
                variant="secondary"
                onClick={() => void documentsQuery.fetchNextPage()}
                disabled={documentsQuery.isFetchingNextPage}
                aria-busy={documentsQuery.isFetchingNextPage}
              >
                {t("loadMore")}
              </Button>
            </div>
          ) : null}
        </>
      ) : null}
    </section>
  );
}
