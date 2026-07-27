"use client";

// SCR-31 / SCR-32 — M4
// Relecture, validation et export d'un document généré (Flux 5 §4–8, Flux 6) :
// polling `GET /generations/{id}` (2 s ×1,5) jusqu'à `draft`/`failed` avec
// annonce ARIA, contenu + panneau « Affirmations et leurs sources », badge du
// contrôle d'ancrage (passed / failed avec claims non ancrées et blocage /
// null si édité), édition manuelle (PATCH, vrai textarea labellisé),
// validation humaine obligatoire (D10) puis export : copie presse-papier +
// téléchargement texte ; PDF/DOCX grisés « M5 ». Diff textuel pour les
// variantes CV (préfixes texte + jamais la couleur seule).

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { notFound, useParams, useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useEffect, useId, useRef, useState } from "react";
import { AnchoringBadge, GenerationStatusBadge } from "@/components/generation/badges";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { isApiProblem } from "@/lib/api/client";
import {
  createGeneration,
  exportGeneration,
  generationKeys,
  getGeneration,
  isGenerationSettled,
  patchGeneration,
  validateGeneration,
} from "@/lib/api/generations";
import { getProfile, profileKeys } from "@/lib/api/profile";
import type { CvVariantChange, GeneratedDocument } from "@/lib/api/types";
import { makePollingInterval } from "@/lib/polling";

/** Un changement du diff CV (Flux 6 §3) — préfixe textuel + ancien/nouveau. */
function DiffChange({ change }: { change: CvVariantChange }) {
  const t = useTranslations("generation.diff");
  return (
    <li className="space-y-1.5 rounded-md border border-border bg-surface p-3 text-sm">
      <p className="flex flex-wrap items-center gap-2">
        <span className="rounded-md bg-surface-muted px-2 py-0.5 text-xs font-semibold text-content">
          {t(change.kind)}
        </span>
        <span className="font-medium text-content">{change.section}</span>
      </p>
      {change.before ? (
        <p className="text-content-secondary">
          <span className="font-medium text-content">{t("before")} : </span>
          {change.before}
        </p>
      ) : null}
      {change.after ? (
        <p className="text-content-secondary">
          <span className="font-medium text-content">{t("after")} : </span>
          {change.after}
        </p>
      ) : null}
    </li>
  );
}

/** Déclenche un téléchargement client d'un contenu texte (export SCR-32). */
function downloadText(filename: string, content: string) {
  const blob = new Blob([content], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

export default function GenerationDocumentPage() {
  const t = useTranslations("generation");
  const params = useParams<{ id: string }>();
  const id = params.id;
  const router = useRouter();
  const queryClient = useQueryClient();
  const baseId = useId();

  const titleRef = useRef<HTMLHeadingElement>(null);
  const announcedDraftRef = useRef(false);

  const [editing, setEditing] = useState(false);
  const [draftBody, setDraftBody] = useState("");
  const [announcement, setAnnouncement] = useState<string | null>(null);
  const [exportError, setExportError] = useState<string | null>(null);
  const [exportedOnce, setExportedOnce] = useState(false);

  const documentQuery = useQuery({
    queryKey: generationKeys.detail(id),
    queryFn: ({ signal }) => getGeneration(id, signal),
    // Polling 2 s ×1,5 tant que `pending` (12 §1).
    refetchInterval: makePollingInterval(isGenerationSettled),
  });

  // Version courante du profil — bandeau « version antérieure » (Flux 5).
  const profileQuery = useQuery({
    queryKey: profileKeys.root,
    queryFn: ({ signal }) => getProfile(signal),
  });

  const doc = documentQuery.data;

  // Passage à `draft` : annonce « Brouillon prêt à relire » + focus sur le
  // titre du document (Flux 5 a11y) — une seule fois.
  useEffect(() => {
    if (doc && doc.status !== "pending" && !announcedDraftRef.current) {
      announcedDraftRef.current = true;
      if (doc.status === "draft") {
        setAnnouncement(t("document.draftReady"));
        requestAnimationFrame(() => titleRef.current?.focus());
      }
    }
  }, [doc, t]);

  const patchMutation = useMutation({
    mutationFn: (body: string) => patchGeneration(id, { ...(doc?.content ?? {}), body }),
    onSuccess: (updated, body) => {
      queryClient.setQueryData<GeneratedDocument>(generationKeys.detail(id), (previous) => {
        if (updated) return updated;
        if (!previous) return previous;
        // 🟡 Réponse sans corps : mise à jour locale — texte édité + contrôle
        // d'ancrage neutralisé (édition manuelle) ; re-fetch derrière.
        return {
          ...previous,
          content: { ...(previous.content ?? {}), body },
          anchoring_check: null,
        };
      });
      void queryClient.invalidateQueries({ queryKey: generationKeys.detail(id) });
      setEditing(false);
      setAnnouncement(t("document.saved"));
    },
  });

  const validateMutation = useMutation({
    mutationFn: () => validateGeneration(id),
    onSuccess: (updated) => {
      queryClient.setQueryData<GeneratedDocument>(generationKeys.detail(id), (previous) =>
        updated ?? (previous ? { ...previous, status: "validated" } : previous),
      );
      void queryClient.invalidateQueries({ queryKey: generationKeys.detail(id) });
      void queryClient.invalidateQueries({ queryKey: generationKeys.lists() });
      setAnnouncement(t("document.validated"));
    },
  });

  const exportMutation = useMutation({
    mutationFn: async (mode: "copy" | "download") => {
      const result = await exportGeneration(id, "text");
      const text = result.content ?? "";
      if (mode === "copy") {
        await navigator.clipboard.writeText(text);
        return "copied" as const;
      }
      downloadText(`boussole-${doc?.doc_type ?? "document"}-${id.slice(0, 8)}.txt`, text);
      return "downloaded" as const;
    },
    onSuccess: (outcome) => {
      setExportError(null);
      setExportedOnce(true);
      setAnnouncement(t(`export.${outcome}`));
      void queryClient.invalidateQueries({ queryKey: generationKeys.detail(id) });
      void queryClient.invalidateQueries({ queryKey: generationKeys.lists() });
    },
    onError: (error) => {
      // 409 generation_not_validated : libellé API repris tel quel (Flux 5).
      if (isApiProblem(error) && error.status === 409) {
        setExportError(t("export.notValidated"));
      } else {
        setExportError(t("export.error"));
      }
    },
  });

  // « Réessayer » après échec : nouvelle génération, nouvelle Idempotency-Key.
  const retryMutation = useMutation({
    mutationFn: () =>
      createGeneration(
        {
          doc_type: doc?.doc_type ?? "cover_letter",
          job_id: doc?.job_id ?? null,
          application_id: doc?.application_id ?? null,
        },
        crypto.randomUUID(),
      ),
    onSuccess: (created) => router.push(`/candidatures/documents/${created.id}`),
  });

  if (documentQuery.error && isApiProblem(documentQuery.error) && documentQuery.error.status === 404) {
    notFound();
  }

  const backLink = (
    <Link
      href="/candidatures/documents"
      className="inline-flex min-h-11 items-center gap-1.5 rounded-sm text-sm font-medium text-action-primary underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
    >
      <ArrowLeft aria-hidden="true" className="h-4 w-4" />
      {t("document.backToList")}
    </Link>
  );

  if (documentQuery.isPending) {
    return (
      <section className="space-y-6">
        {backLink}
        <div role="status" aria-live="polite" className="space-y-4">
          <span className="sr-only">{t("document.loading")}</span>
          <div aria-hidden="true" className="h-24 animate-pulse rounded-lg bg-surface-muted" />
        </div>
      </section>
    );
  }

  if (documentQuery.isError) {
    return (
      <section className="space-y-6">
        {backLink}
        <Alert variant="error" title={t("document.loadErrorTitle")}>
          <Button variant="secondary" onClick={() => void documentQuery.refetch()}>
            {t("document.retry")}
          </Button>
        </Alert>
      </section>
    );
  }

  const documentData = documentQuery.data;
  const isPending = documentData.status === "pending";
  const isFailed = documentData.status === "failed";
  const isDraft = documentData.status === "draft";
  const isValidated = documentData.status === "validated" || documentData.status === "exported";
  const isExported = documentData.status === "exported";
  const isCvDiff =
    documentData.doc_type === "cv_variant" || documentData.doc_type === "cv_optimization";

  const content = documentData.content;
  const body = content?.body ?? "";
  const claims = content?.claims ?? [];
  const changes = content?.changes;
  const anchoringFailed = documentData.anchoring_check?.status === "failed";
  const unanchoredClaims = documentData.anchoring_check?.unanchored_claims ?? [];

  const staleProfile =
    profileQuery.data !== undefined &&
    profileQuery.data.version > documentData.based_on_profile_version;

  return (
    <article aria-labelledby="generation-doc-title" className="space-y-6">
      {backLink}

      {/* Annonces (validation, sauvegarde, copie…) — une région unique. */}
      <p role="status" aria-live="polite" className="sr-only">
        {announcement}
      </p>

      <header className="space-y-2">
        <div className="flex flex-wrap items-center gap-3">
          <h1
            id="generation-doc-title"
            ref={titleRef}
            tabIndex={-1}
            className="text-2xl font-semibold text-content focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
          >
            {t(`docTypes.${documentData.doc_type}`)}
          </h1>
          <GenerationStatusBadge status={documentData.status} />
          {!isPending && !isFailed ? (
            <AnchoringBadge check={documentData.anchoring_check} />
          ) : null}
        </div>
        <p className="flex flex-wrap gap-x-4 gap-y-1 text-sm text-content-secondary">
          <span>{t("document.basedOn", { version: documentData.based_on_profile_version })}</span>
          {documentData.prompt_version ? (
            <span>{t("document.promptVersion", { version: documentData.prompt_version })}</span>
          ) : null}
        </p>
        {documentData.job_id ? (
          <Link
            href={`/offres/${documentData.job_id}`}
            className="inline-flex min-h-11 items-center text-sm font-medium text-action-primary underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
          >
            {t("document.viewJob")}
          </Link>
        ) : null}
      </header>

      {staleProfile && !isPending && !isFailed ? (
        <Alert variant="info">
          {t("document.staleProfile", { version: documentData.based_on_profile_version })}
        </Alert>
      ) : null}

      {/* --- Génération en cours (annonce espacée, jamais à chaque poll) --- */}
      {isPending ? (
        <div role="status" aria-live="polite" className="space-y-3 rounded-lg border border-border bg-surface p-6">
          <p className="text-base font-medium text-content">{t("document.pending")}</p>
          <p className="text-sm text-content-secondary">{t("document.pendingHint")}</p>
          <div aria-hidden="true" className="h-24 animate-pulse rounded-md bg-surface-muted" />
        </div>
      ) : null}

      {/* --- Échec de génération ------------------------------------------ */}
      {isFailed ? (
        <div className="space-y-3">
          <Alert variant="error">{t("document.failed")}</Alert>
          <Button
            onClick={() => retryMutation.mutate()}
            disabled={retryMutation.isPending}
            aria-busy={retryMutation.isPending}
          >
            {t("document.retryGenerate")}
          </Button>
        </div>
      ) : null}

      {!isPending && !isFailed ? (
        <>
          {/* --- Contrôle d'ancrage (bandeau détaillé) ---------------------- */}
          {anchoringFailed ? (
            <Alert variant="error" title={t("anchoring.title")}>
              <p>{t("anchoring.failedBody", { count: unanchoredClaims.length })}</p>
              {unanchoredClaims.length > 0 ? (
                <>
                  <p className="mt-2 font-medium">{t("anchoring.unanchoredTitle")}</p>
                  <ul className="mt-1 list-disc space-y-0.5 pl-5">
                    {unanchoredClaims.map((claim) => (
                      <li key={claim}>{claim}</li>
                    ))}
                  </ul>
                </>
              ) : null}
            </Alert>
          ) : null}
          {documentData.anchoring_check === null ? (
            <Alert variant="info" title={t("anchoring.title")}>
              {t("anchoring.manualBody")}
            </Alert>
          ) : null}

          {/* --- Diff CV (variante / optimisation, Flux 6 §3) --------------- */}
          {isCvDiff && changes !== undefined ? (
            <section aria-labelledby={`${baseId}-diff`} className="space-y-3">
              <h2 id={`${baseId}-diff`} className="text-lg font-semibold text-content">
                {t("diff.title")}
              </h2>
              <p className="text-sm font-medium text-content">{t("diff.note")}</p>
              {changes.length === 0 ? (
                <p className="text-sm text-content-secondary">{t("diff.nearIdentical")}</p>
              ) : (
                <ul className="space-y-2">
                  {changes.map((change, index) => (
                    <DiffChange key={`${change.section}-${index}`} change={change} />
                  ))}
                </ul>
              )}
            </section>
          ) : null}

          {/* --- Contenu + édition manuelle (vrai textarea labellisé) ------- */}
          <section aria-labelledby={`${baseId}-content`} className="space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h2 id={`${baseId}-content`} className="text-lg font-semibold text-content">
                {t("document.contentTitle")}
              </h2>
              {isDraft && !editing ? (
                <Button
                  variant="secondary"
                  onClick={() => {
                    setDraftBody(body);
                    setEditing(true);
                  }}
                >
                  {t("document.edit")}
                </Button>
              ) : null}
            </div>

            {isExported ? (
              <p className="text-sm text-content-secondary">{t("document.readonlyExported")}</p>
            ) : null}

            {editing ? (
              <div className="space-y-3">
                <p className="max-w-prose text-sm text-content-secondary">
                  {t("document.editHint")}
                </p>
                <label htmlFor={`${baseId}-textarea`} className="sr-only">
                  {t("document.editLabel")}
                </label>
                <textarea
                  id={`${baseId}-textarea`}
                  value={draftBody}
                  onChange={(event) => setDraftBody(event.target.value)}
                  rows={16}
                  className="w-full rounded-md border border-border bg-surface px-3 py-2 text-sm leading-relaxed text-content focus:border-action-primary focus:shadow-input-focus focus:outline-none"
                />
                {patchMutation.isError ? (
                  <Alert variant="error">{t("document.saveError")}</Alert>
                ) : null}
                <div className="flex flex-wrap gap-3">
                  <Button
                    onClick={() => patchMutation.mutate(draftBody)}
                    disabled={patchMutation.isPending}
                    aria-busy={patchMutation.isPending}
                  >
                    {t("document.save")}
                  </Button>
                  <Button variant="secondary" onClick={() => setEditing(false)}>
                    {t("document.cancel")}
                  </Button>
                </div>
              </div>
            ) : body ? (
              <p className="max-w-prose whitespace-pre-wrap rounded-lg border border-border bg-surface p-4 text-sm leading-relaxed text-content">
                {body}
              </p>
            ) : !isCvDiff ? (
              <p className="text-sm text-content-secondary">{t("document.emptyContent")}</p>
            ) : null}
          </section>

          {/* --- Affirmations et leurs sources (Flux 5 §5) ------------------ */}
          {claims.length > 0 ? (
            <section aria-labelledby={`${baseId}-claims`} className="space-y-3">
              <h2 id={`${baseId}-claims`} className="text-lg font-semibold text-content">
                {t("document.claimsTitle")}
              </h2>
              <p className="max-w-prose text-sm text-content-secondary">
                {t("document.claimsIntro")}
              </p>
              <ul className="space-y-2">
                {claims.map((claim) => (
                  <li
                    key={`${claim.profile_ref}-${claim.claim}`}
                    className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-border bg-surface p-3 text-sm"
                  >
                    <span className="text-content">{claim.claim}</span>
                    <Link
                      href="/profil"
                      aria-label={t("document.claimSourceLink", { claim: claim.claim })}
                      className="inline-flex min-h-11 items-center font-medium text-action-primary underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
                    >
                      {t("document.claimSourceShort")}
                    </Link>
                  </li>
                ))}
              </ul>
            </section>
          ) : null}

          {/* --- Validation humaine (D10 — obligatoire avant export) -------- */}
          {!isValidated ? (
            <div className="space-y-3 rounded-lg border border-border bg-surface p-4">
              {validateMutation.isError ? (
                <Alert variant="error">{t("document.validateError")}</Alert>
              ) : null}
              <Button
                onClick={() => validateMutation.mutate()}
                disabled={!isDraft || editing || anchoringFailed || validateMutation.isPending}
                aria-busy={validateMutation.isPending}
                aria-describedby={anchoringFailed ? `${baseId}-validate-hint` : undefined}
              >
                {t("document.validateCta")}
              </Button>
              {anchoringFailed ? (
                <p id={`${baseId}-validate-hint`} className="text-sm text-content-secondary">
                  {t("document.validateBlockedAnchoring")}
                </p>
              ) : null}
            </div>
          ) : null}

          {/* --- Export (SCR-32) ------------------------------------------- */}
          <section
            aria-labelledby={`${baseId}-export`}
            className="space-y-3 rounded-lg border border-border bg-surface p-4"
          >
            <h2 id={`${baseId}-export`} className="text-lg font-semibold text-content">
              {t("export.title")}
            </h2>
            {!isValidated ? (
              <p id={`${baseId}-export-hint`} className="text-sm text-content-secondary">
                {t("export.blocked")}
              </p>
            ) : null}
            {exportError ? <Alert variant="error">{exportError}</Alert> : null}
            <div className="flex flex-wrap gap-3">
              <Button
                onClick={() => exportMutation.mutate("copy")}
                disabled={!isValidated || exportMutation.isPending}
                aria-describedby={!isValidated ? `${baseId}-export-hint` : undefined}
              >
                {t("export.copy")}
              </Button>
              <Button
                variant="secondary"
                onClick={() => exportMutation.mutate("download")}
                disabled={!isValidated || exportMutation.isPending}
                aria-describedby={!isValidated ? `${baseId}-export-hint` : undefined}
              >
                {t("export.downloadText")}
              </Button>
              {/* PDF / DOCX : jalon M5 — grisés avec explication. */}
              <Button
                variant="secondary"
                disabled
                aria-describedby={`${baseId}-export-m5`}
              >
                {t("export.pdf")}
              </Button>
              <Button
                variant="secondary"
                disabled
                aria-describedby={`${baseId}-export-m5`}
              >
                {t("export.docx")}
              </Button>
            </div>
            <p id={`${baseId}-export-m5`} className="text-sm text-content-secondary">
              {t("export.m5Note")}
            </p>
            {/* Rappel SCR-32 : aucune candidature automatique (M6). */}
            <p className="text-sm font-medium text-content">{t("export.noSend")}</p>

            {exportedOnce ? (
              <div className="space-y-1 border-t border-border pt-3">
                <p className="text-sm text-content">{t("export.trackCta")}</p>
                <Link
                  href={
                    documentData.job_id
                      ? `/candidatures?suivre=${encodeURIComponent(documentData.job_id)}`
                      : "/candidatures"
                  }
                  className="inline-flex min-h-11 items-center text-sm font-medium text-action-primary underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
                >
                  {t("export.trackLink")}
                </Link>
              </div>
            ) : null}
          </section>
        </>
      ) : null}
    </article>
  );
}
