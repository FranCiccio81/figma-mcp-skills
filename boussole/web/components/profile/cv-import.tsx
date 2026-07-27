"use client";

// SCR-05 / SCR-06 (revue) — M4
// Bloc « Importer mon CV » du profil (Flux 1 §2–5, SCR-51 en réimport) :
// upload accessible (input fichier, contrôles client extension/taille avant
// envoi), polling `GET /cv-documents/{id}` (2 s ×1,5 — 12 §1) avec étapes
// annoncées en aria-live, messages dédiés par `error_code`, puis ÉCRAN DE
// REVUE : proposition GROUPÉE (`proposal` — headline/summary + expériences,
// formations, compétences, langues) avec confiance + citation
// (`evidence_quote`), cases à cocher (tout coché sauf confiance < 0,5),
// « Appliquer au profil » → POST /cv-documents/{id}/apply
// ({ item_ids, include_headline, include_summary }). L'existant
// saisi/confirmé n'est jamais écrasé (03 Q4).

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import clsx from "clsx";
import { FileUp } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { useEffect, useId, useMemo, useRef, useState } from "react";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { isApiProblem } from "@/lib/api/client";
import {
  applyCvDocument,
  CV_MAX_FILE_BYTES,
  cvKeys,
  getCvDocument,
  hasAcceptedExtension,
  isCvDocumentSettled,
  uploadCvDocument,
} from "@/lib/api/cv";
import { invalidateMatchDependentQueries } from "@/lib/api/matching";
import { meKeys } from "@/lib/api/me";
import { profileKeys } from "@/lib/api/profile";
import type {
  CvDocument,
  CvErrorCode,
  CvProposal,
  CvProposalItemBase,
  CvProposedEducation,
  CvProposedExperience,
  CvProposedLanguage,
} from "@/lib/api/types";
import { makePollingInterval } from "@/lib/polling";

/** Seuil de confiance sous lequel un élément est décoché par défaut (06 §1, M3-d). */
const LOW_CONFIDENCE_THRESHOLD = 0.5;

/** Sections d'items de la proposition groupée (mêmes sections que le profil). */
type CvProposalSectionKind = "experience" | "education" | "skill" | "language";

/** Tous les items sélectionnables de la proposition (headline/summary à part). */
function allProposalItems(proposal: CvProposal | undefined): CvProposalItemBase[] {
  if (!proposal) return [];
  return [
    ...proposal.experiences,
    ...proposal.educations,
    ...proposal.skills,
    ...proposal.languages,
  ];
}

/** Un item est-il coché par défaut ? Oui, sauf confiance d'extraction < 0,5. */
function isCheckedByDefault(item: CvProposalItemBase): boolean {
  return (item.provenance.confidence ?? 1) >= LOW_CONFIDENCE_THRESHOLD;
}

/** « Développeuse backend — ACME, 2019–2023 » (années des dates ISO). */
function experienceLabel(item: CvProposedExperience, presentLabel: string): string {
  const startYear = item.start_date.slice(0, 4);
  const endYear = item.end_date ? item.end_date.slice(0, 4) : presentLabel;
  return `${item.title} — ${item.company}, ${startYear}–${endYear}`;
}

/** « Master Informatique — Université de Lyon, 2017–2019 » (années optionnelles). */
function educationLabel(item: CvProposedEducation): string {
  const base = `${item.degree} — ${item.institution}`;
  const years = [item.start_year, item.end_year].filter((year) => year !== null);
  return years.length > 0 ? `${base}, ${years.join("–")}` : base;
}

/** « Anglais — C1 » : nom de langue localisé (repli sur le code si inconnu). */
function languageLabel(item: CvProposedLanguage, locale: string): string {
  let name: string = item.lang_code;
  try {
    name = new Intl.DisplayNames([locale], { type: "language" }).of(item.lang_code) ?? name;
  } catch {
    // Code de langue non reconnu — affiché tel quel.
  }
  return `${name} — ${item.level}`;
}

/** Étapes affichées pendant le parsing (Flux 1 §3 — libellés exacts). */
const PARSING_STEPS = ["reading", "extracting", "preparing"] as const;
type ParsingStep = (typeof PARSING_STEPS)[number];

/** Étape courante selon le statut du document (uploaded → lecture, parsing → extraction). */
function currentStep(document: CvDocument | undefined): ParsingStep {
  if (!document || document.status === "uploaded") return "reading";
  return "extracting";
}

type CvErrorKey =
  | "unreadable"
  | "imageOnlyPdf"
  | "tooLarge"
  | "unsupportedFormat"
  | "extractionFailed"
  | "quota"
  | "generic";

/** Clé i18n du message dédié à un `error_code` de parsing (04 Flux 1, tableau des cas). */
function errorKeyForCode(code: CvErrorCode | null | undefined): CvErrorKey {
  switch (code) {
    case "unreadable":
      return "unreadable";
    case "image_only_pdf":
      return "imageOnlyPdf";
    case "too_large":
      return "tooLarge";
    case "unsupported_format":
      return "unsupportedFormat";
    case "extraction_failed":
      return "extractionFailed";
    default:
      return "generic";
  }
}

/** Clé i18n du message d'une erreur d'upload (contrôle client, 413, 415, 429). */
function errorKeyForUpload(error: unknown): CvErrorKey {
  if (isApiProblem(error)) {
    if (error.status === 413) return "tooLarge";
    if (error.status === 415) return "unsupportedFormat";
    if (error.status === 429) return "quota";
  }
  return "generic";
}

/**
 * Élément de la revue : case à cocher + confiance + citation (`evidence_quote`,
 * texte secondaire). `confidence`/`evidenceQuote` absents (`undefined`) pour
 * headline/summary — la proposition groupée ne les fournit que par item ;
 * `evidenceQuote: null` = citation indisponible (mention dédiée).
 */
function ReviewItem({
  label,
  secondary,
  confidence,
  evidenceQuote,
  checked,
  onToggle,
}: {
  label: string;
  /** Texte secondaire optionnel (ex. description d'expérience). */
  secondary?: string | null;
  confidence?: number;
  evidenceQuote?: string | null;
  checked: boolean;
  onToggle: () => void;
}) {
  const t = useTranslations("cvImport.review");
  const baseId = useId();
  const lowConfidence = confidence !== undefined && confidence < LOW_CONFIDENCE_THRESHOLD;
  const hasDetails = secondary != null || confidence !== undefined || evidenceQuote !== undefined;
  const checkboxId = `${baseId}-check`;
  const detailsId = `${baseId}-details`;

  return (
    <li className="rounded-md border border-border bg-surface p-3">
      <div className="flex items-start gap-3">
        <input
          id={checkboxId}
          type="checkbox"
          checked={checked}
          onChange={onToggle}
          aria-describedby={hasDetails ? detailsId : undefined}
          className="mt-1 h-5 w-5 shrink-0 accent-action-primary"
        />
        <div className="min-w-0 flex-1 space-y-1.5">
          <label htmlFor={checkboxId} className="block text-sm font-medium text-content">
            {label}
          </label>
          {hasDetails ? (
            <div id={detailsId} className="space-y-1.5">
              {secondary ? (
                <p className="whitespace-pre-wrap text-sm text-content-secondary">{secondary}</p>
              ) : null}
              {confidence !== undefined ? (
                <p className="flex flex-wrap items-center gap-2 text-xs">
                  <span
                    className={clsx(
                      "rounded-md px-2 py-0.5 font-medium",
                      lowConfidence
                        ? "bg-feedback-warning-surface text-feedback-warning"
                        : "bg-feedback-info-surface text-feedback-info",
                    )}
                  >
                    {t("confidence", { percent: Math.round(confidence * 100) })}
                  </span>
                  {lowConfidence ? (
                    <span className="font-medium text-feedback-warning">{t("toVerify")}</span>
                  ) : null}
                </p>
              ) : null}
              {evidenceQuote !== undefined ? (
                evidenceQuote ? (
                  <blockquote className="border-l-2 border-border pl-3 text-sm italic text-content-secondary">
                    <span className="not-italic font-medium">{t("evidenceLabel")} </span>
                    {evidenceQuote}
                  </blockquote>
                ) : (
                  <p className="text-sm text-content-secondary">{t("noEvidence")}</p>
                )
              ) : null}
            </div>
          ) : null}
        </div>
      </div>
    </li>
  );
}

/**
 * Bloc « Importer mon CV » (SCR-05 + revue SCR-06), inséré dans la page
 * Profil. Après application, invalide le profil, `GET /me` (checklist
 * d'onboarding) et tous les caches match.
 */
export function CvImport() {
  const t = useTranslations("cvImport");
  const locale = useLocale();
  const queryClient = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const reviewTitleRef = useRef<HTMLHeadingElement>(null);
  const appliedAlertRef = useRef<HTMLDivElement>(null);
  const baseId = useId();

  const [documentId, setDocumentId] = useState<string | null>(null);
  const [lastFile, setLastFile] = useState<File | null>(null);
  const [uploadErrorKey, setUploadErrorKey] = useState<CvErrorKey | null>(null);
  /** `item_id` cochés dans la revue (`null` = sélection par défaut pas encore calculée). */
  const [checkedIds, setCheckedIds] = useState<Set<string> | null>(null);
  /** Cases dédiées aux deux champs racine de la proposition (hors `item_ids`). */
  const [includeHeadline, setIncludeHeadline] = useState(false);
  const [includeSummary, setIncludeSummary] = useState(false);
  const [applied, setApplied] = useState(false);

  const uploadMutation = useMutation({
    mutationFn: (file: File) => uploadCvDocument(file),
    onSuccess: (document) => {
      setUploadErrorKey(null);
      setApplied(false);
      setCheckedIds(null);
      setIncludeHeadline(false);
      setIncludeSummary(false);
      queryClient.setQueryData(cvKeys.document(document.id), document);
      setDocumentId(document.id);
    },
    onError: (error) => setUploadErrorKey(errorKeyForUpload(error)),
  });

  const documentQuery = useQuery({
    queryKey: cvKeys.document(documentId ?? ""),
    queryFn: ({ signal }) => getCvDocument(documentId ?? "", signal),
    enabled: documentId !== null,
    // Polling 2 s ×1,5 (12 §1) tant que le parsing n'est pas terminé.
    refetchInterval: makePollingInterval(isCvDocumentSettled),
  });

  const document = documentId !== null ? documentQuery.data : undefined;
  const isParsing =
    documentId !== null &&
    !documentQuery.isError &&
    (document === undefined || document.status === "uploaded" || document.status === "parsing");
  // Pendant un nouvel upload (« Réessayer »), les états de l'ancien document
  // ne sont plus affichés — seul l'état d'envoi reste visible.
  const isFailed = document?.status === "failed" && !uploadMutation.isPending;
  const isParsed = document?.status === "parsed" && !uploadMutation.isPending;

  // Sélection par défaut à l'arrivée du résultat : tout coché sauf confiance
  // < 0,5 (prompt SCR-06) ; headline/summary cochés s'ils sont proposés —
  // puis focus sur le titre de la revue (Flux 1 a11y).
  useEffect(() => {
    if (isParsed && checkedIds === null) {
      const proposal = document?.proposal;
      setCheckedIds(
        new Set(
          allProposalItems(proposal)
            .filter(isCheckedByDefault)
            .map((item) => item.item_id),
        ),
      );
      setIncludeHeadline(proposal?.headline != null);
      setIncludeSummary(proposal?.summary != null);
      requestAnimationFrame(() => reviewTitleRef.current?.focus());
    }
  }, [isParsed, checkedIds, document]);

  const applyMutation = useMutation({
    mutationFn: () =>
      applyCvDocument(documentId ?? "", {
        // Liste explicite des items cochés — jamais `null` (= tout) depuis la revue.
        item_ids: [...(checkedIds ?? [])],
        include_headline: includeHeadline,
        include_summary: includeSummary,
      }),
    onSuccess: (profile) => {
      setApplied(true);
      queryClient.setQueryData(profileKeys.root, profile);
      void queryClient.invalidateQueries({ queryKey: profileKeys.root });
      void queryClient.invalidateQueries({ queryKey: meKeys.root });
      invalidateMatchDependentQueries(queryClient);
      requestAnimationFrame(() => appliedAlertRef.current?.focus());
    },
  });

  /** Contrôles client immédiats (extension, taille — Flux 1 §2) puis upload. */
  const handleFile = (file: File | null) => {
    if (!file) return;
    setApplied(false);
    if (!hasAcceptedExtension(file.name)) {
      setUploadErrorKey("unsupportedFormat");
      return;
    }
    if (file.size > CV_MAX_FILE_BYTES) {
      setUploadErrorKey("tooLarge");
      return;
    }
    setUploadErrorKey(null);
    setLastFile(file);
    uploadMutation.mutate(file);
  };

  const resetToUpload = () => {
    setDocumentId(null);
    setCheckedIds(null);
    setIncludeHeadline(false);
    setIncludeSummary(false);
    setUploadErrorKey(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
    fileInputRef.current?.focus();
  };

  const step = currentStep(document);
  const stepIndex = PARSING_STEPS.indexOf(step);

  const proposal = document?.proposal;

  /** Sections d'items de la revue (mêmes sections que le profil), vides omises. */
  const sections = useMemo(() => {
    if (!proposal) return [];
    const present = t("review.present");
    const entryOf = (item: CvProposalItemBase, label: string, secondary?: string | null) => ({
      itemId: item.item_id,
      label,
      secondary,
      confidence: item.provenance.confidence,
      evidenceQuote: item.evidence_quote,
    });
    return (
      [
        {
          kind: "experience",
          entries: proposal.experiences.map((item) =>
            entryOf(item, experienceLabel(item, present), item.description),
          ),
        },
        {
          kind: "education",
          entries: proposal.educations.map((item) => entryOf(item, educationLabel(item))),
        },
        {
          kind: "skill",
          entries: proposal.skills.map((item) => entryOf(item, item.label)),
        },
        {
          kind: "language",
          entries: proposal.languages.map((item) => entryOf(item, languageLabel(item, locale))),
        },
      ] satisfies { kind: CvProposalSectionKind; entries: unknown[] }[]
    ).filter((section) => section.entries.length > 0);
  }, [proposal, locale, t]);

  const hasProposedContent =
    sections.length > 0 || proposal?.headline != null || proposal?.summary != null;

  const selectedCount =
    (checkedIds?.size ?? 0) + (includeHeadline ? 1 : 0) + (includeSummary ? 1 : 0);

  const toggleItem = (id: string) => {
    setCheckedIds((previous) => {
      const next = new Set(previous ?? []);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const fileInputId = `${baseId}-file`;
  const titleId = `${baseId}-title`;

  return (
    <section
      id="import-cv"
      aria-labelledby={titleId}
      className="space-y-4 rounded-lg border border-border bg-surface p-4"
    >
      <h2 id={titleId} className="flex items-center gap-2 text-lg font-semibold text-content">
        <FileUp aria-hidden="true" className="h-5 w-5" />
        {t("title")}
      </h2>

      {applied ? (
        <Alert ref={appliedAlertRef} tabIndex={-1} variant="success">
          {t("review.applied")}
        </Alert>
      ) : null}

      {/* --- État upload (SCR-05, dropzone = input fichier accessible) ----- */}
      {documentId === null || uploadMutation.isPending ? (
        <div className="space-y-3">
          <p className="max-w-prose text-sm text-content-secondary">{t("intro")}</p>
          {uploadErrorKey ? (
            <Alert variant="error">{t(`errors.${uploadErrorKey}`)}</Alert>
          ) : null}
          <div className="space-y-1.5">
            <label htmlFor={fileInputId} className="block text-sm font-medium text-content">
              {t("fileLabel")}
            </label>
            <p id={`${fileInputId}-description`} className="text-sm text-content-secondary">
              {t("constraints")}
            </p>
            <input
              ref={fileInputRef}
              id={fileInputId}
              type="file"
              accept=".pdf,.docx"
              disabled={uploadMutation.isPending}
              aria-describedby={`${fileInputId}-description`}
              onChange={(event) => handleFile(event.target.files?.[0] ?? null)}
              className="block w-full min-h-11 max-w-md cursor-pointer rounded-md border border-border bg-surface text-sm text-content file:mr-3 file:min-h-11 file:cursor-pointer file:rounded-l-md file:border-0 file:bg-surface-muted file:px-4 file:text-sm file:font-medium file:text-content focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus disabled:cursor-not-allowed disabled:opacity-50"
            />
          </div>
          {uploadMutation.isPending ? (
            <p role="status" aria-live="polite" className="text-sm text-content-secondary">
              {t("uploading")}
            </p>
          ) : null}
        </div>
      ) : null}

      {/* --- État parsing en cours (polling 2 s ×1,5, étapes annoncées) ----- */}
      {isParsing && !uploadMutation.isPending ? (
        <div role="status" aria-live="polite" className="space-y-3">
          {/* Une annonce par étape (jamais à chaque poll — Flux 1 a11y). */}
          <p className="sr-only">{t("stepAnnounce", { step: t(`steps.${step}`) })}</p>
          <ol aria-hidden="true" className="space-y-1.5">
            {PARSING_STEPS.map((name, index) => (
              <li
                key={name}
                className={clsx(
                  "flex items-center gap-2 text-sm",
                  index === stepIndex
                    ? "font-semibold text-content"
                    : "text-content-secondary",
                )}
              >
                <span
                  className={clsx(
                    "h-2 w-2 shrink-0 rounded-full",
                    index < stepIndex
                      ? "bg-feedback-success"
                      : index === stepIndex
                        ? "animate-pulse bg-action-primary"
                        : "bg-border-strong",
                  )}
                />
                {t(`steps.${name}`)}
              </li>
            ))}
          </ol>
        </div>
      ) : null}

      {/* Le polling lui-même a échoué (réseau…) — pas un échec de parsing. */}
      {documentId !== null && documentQuery.isError ? (
        <Alert variant="error">
          <p>{t("errors.pollFailed")}</p>
          <div className="mt-2">
            <Button variant="secondary" onClick={() => void documentQuery.refetch()}>
              {t("retry")}
            </Button>
          </div>
        </Alert>
      ) : null}

      {/* --- État échec de parsing (message dédié par error_code) ----------- */}
      {isFailed ? (
        <div className="space-y-3">
          <Alert variant="error">
            <p>{t(`errors.${errorKeyForCode(document?.error_code)}`)}</p>
            {document?.error_code === "image_only_pdf" ||
            document?.error_code === "extraction_failed" ? (
              // Proposition de saisie manuelle (prompt M4 : `image_only_pdf`).
              <p className="mt-1">{t("manualEntryHint")}</p>
            ) : null}
          </Alert>
          {document?.trace_id ? (
            <details className="text-sm text-content-secondary">
              <summary className="min-h-11 cursor-pointer list-item font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">
                {t("traceToggle")}
              </summary>
              <p>{t("traceId", { traceId: document.trace_id })}</p>
            </details>
          ) : null}
          <div className="flex flex-wrap gap-3">
            {lastFile &&
            (document?.error_code === "unreadable" ||
              document?.error_code === "extraction_failed") ? (
              // « Réessayer » proposé pour unreadable / extraction_failed (04 Flux 1).
              <Button onClick={() => uploadMutation.mutate(lastFile)}>{t("retry")}</Button>
            ) : null}
            <Button variant="secondary" onClick={resetToUpload}>
              {t("chooseAnotherFile")}
            </Button>
          </div>
        </div>
      ) : null}

      {/* --- Écran de revue (SCR-06 : confiance + evidence + cases) --------- */}
      {isParsed && !applied ? (
        <div className="space-y-4">
          <h3
            ref={reviewTitleRef}
            tabIndex={-1}
            className="text-base font-semibold text-content focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
          >
            {t("review.title")}
          </h3>

          {(document?.extraction_warnings?.length ?? 0) > 0 ? (
            // Parsing partiel : jamais présenté comme un échec (Flux 1).
            <Alert variant="warning">
              {t("review.partialWarnings", {
                list: (document?.extraction_warnings ?? []).join(", "),
              })}
            </Alert>
          ) : null}

          {!hasProposedContent ? (
            <p className="text-sm text-content-secondary">{t("review.empty")}</p>
          ) : (
            <>
              <p className="max-w-prose text-sm text-content-secondary">{t("review.intro")}</p>
              <p className="max-w-prose text-sm font-medium text-content">
                {t("review.noOverwrite")}
              </p>

              {/* Champs racine de la proposition (hors item_ids) — cases dédiées. */}
              {proposal?.headline != null ? (
                <fieldset className="space-y-2 border-0 p-0">
                  <legend className="text-sm font-semibold text-content">
                    {t("review.kinds.headline")}
                  </legend>
                  <ul className="space-y-2">
                    <ReviewItem
                      label={proposal.headline}
                      checked={includeHeadline}
                      onToggle={() => setIncludeHeadline((value) => !value)}
                    />
                  </ul>
                </fieldset>
              ) : null}
              {proposal?.summary != null ? (
                <fieldset className="space-y-2 border-0 p-0">
                  <legend className="text-sm font-semibold text-content">
                    {t("review.kinds.summary")}
                  </legend>
                  <ul className="space-y-2">
                    <ReviewItem
                      label={proposal.summary}
                      checked={includeSummary}
                      onToggle={() => setIncludeSummary((value) => !value)}
                    />
                  </ul>
                </fieldset>
              ) : null}

              {sections.map(({ kind, entries }) => (
                <fieldset key={kind} className="space-y-2 border-0 p-0">
                  <legend className="text-sm font-semibold text-content">
                    {t(`review.kinds.${kind}`)}
                  </legend>
                  <ul className="space-y-2">
                    {entries.map((entry) => (
                      <ReviewItem
                        key={entry.itemId}
                        label={entry.label}
                        secondary={entry.secondary}
                        confidence={entry.confidence}
                        evidenceQuote={entry.evidenceQuote}
                        checked={checkedIds?.has(entry.itemId) ?? false}
                        onToggle={() => toggleItem(entry.itemId)}
                      />
                    ))}
                  </ul>
                </fieldset>
              ))}

              <p role="status" aria-live="polite" className="text-sm text-content-secondary">
                {t("review.selectedCount", { count: selectedCount })}
              </p>

              {applyMutation.isError ? (
                <Alert variant="error">{t("review.applyError")}</Alert>
              ) : null}

              <div className="flex flex-wrap gap-3">
                <Button
                  onClick={() => applyMutation.mutate()}
                  disabled={selectedCount === 0 || applyMutation.isPending}
                  aria-busy={applyMutation.isPending}
                >
                  {t("review.apply")}
                </Button>
                <Button variant="secondary" onClick={resetToUpload}>
                  {t("chooseAnotherFile")}
                </Button>
              </div>
            </>
          )}
          {!hasProposedContent ? (
            <Button variant="secondary" onClick={resetToUpload}>
              {t("chooseAnotherFile")}
            </Button>
          ) : null}
        </div>
      ) : null}

      {/* Après application : possibilité de réimporter un autre CV (SCR-51). */}
      {isParsed && applied ? (
        <Button variant="secondary" onClick={resetToUpload}>
          {t("chooseAnotherFile")}
        </Button>
      ) : null}
    </section>
  );
}
