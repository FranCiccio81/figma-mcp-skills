"use client";

// SCR-30 — M4
// Modale de configuration d'une génération (Flux 5 §2–4, Flux 6) : ton /
// langue / longueur, avertissement anti-invention M4-a systématique (non
// désactivable) au-dessus du bouton « Générer », rappel M6 en pied.
// `POST /generations` avec `Idempotency-Key` UUID générée à l'ouverture
// (double-clic = rejeu de la même clé, une seule génération — 12 §1), puis
// bascule sur la page du document (SCR-31) en état « Génération en cours ».
// A11y : role="dialog" + aria-modal, focus piégé, Échap ferme et rend le
// focus à l'élément déclencheur (04 §conventions).

import { useMutation } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import {
  useEffect,
  useId,
  useRef,
  useState,
  type KeyboardEvent,
  type ReactNode,
} from "react";
import Link from "next/link";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { isApiProblem } from "@/lib/api/client";
import {
  createGeneration,
  GENERATION_QUOTA_DAILY,
  GENERATION_QUOTA_HOURLY,
} from "@/lib/api/generations";
import type {
  DocType,
  GenerationLanguage,
  GenerationLength,
  GenerationTone,
} from "@/lib/api/types";

const TONES: readonly GenerationTone[] = ["sobre", "chaleureux", "direct"];
const LANGUAGES: readonly GenerationLanguage[] = ["fr", "en"];
const LENGTHS: readonly GenerationLength[] = ["court", "standard"];

export interface GenerateModalProps {
  docType: DocType;
  /** Offre cible — requis sauf `cv_optimization` (openapi.yaml). */
  jobId?: string | null;
  /** Candidature liée (génération depuis SCR-41, Flux 7 §5). */
  applicationId?: string | null;
  /** Langue de l'offre — pré-sélectionne la langue de rédaction (Flux 5 §2). */
  jobLanguage?: string | null;
  onClose: () => void;
}

/** Sélecteur radio accessible d'une option de génération (fieldset/legend). */
function OptionGroup<T extends string>({
  legend,
  name,
  options,
  value,
  onChange,
  labelFor,
}: {
  legend: string;
  name: string;
  options: readonly T[];
  value: T;
  onChange: (next: T) => void;
  labelFor: (option: T) => string;
}) {
  return (
    <fieldset className="space-y-2 border-0 p-0">
      <legend className="text-sm font-medium text-content">{legend}</legend>
      <div className="flex flex-wrap gap-2">
        {options.map((option) => {
          const selected = option === value;
          return (
            <label
              key={option}
              className={
                "flex min-h-11 cursor-pointer items-center gap-2 rounded-md border px-3 text-sm " +
                (selected
                  ? "border-action-primary bg-surface-muted font-medium text-content"
                  : "border-border bg-surface text-content-secondary hover:bg-surface-muted")
              }
            >
              <input
                type="radio"
                name={name}
                value={option}
                checked={selected}
                onChange={() => onChange(option)}
                className="h-4 w-4 accent-action-primary"
              />
              {labelFor(option)}
            </label>
          );
        })}
      </div>
    </fieldset>
  );
}

/**
 * Modale SCR-30. À monter conditionnellement (`open ? <GenerateModal … /> :
 * null`) : le focus revient automatiquement à l'élément déclencheur au
 * démontage.
 */
export function GenerateModal({
  docType,
  jobId,
  applicationId,
  jobLanguage,
  onClose,
}: GenerateModalProps) {
  const t = useTranslations("generation");
  const locale = useLocale();
  const router = useRouter();
  const baseId = useId();
  const dialogRef = useRef<HTMLDivElement>(null);

  const [tone, setTone] = useState<GenerationTone>("sobre");
  const [language, setLanguage] = useState<GenerationLanguage>(
    jobLanguage?.toLowerCase().startsWith("en") ? "en" : "fr",
  );
  const [length, setLength] = useState<GenerationLength>("standard");

  // Idempotency-Key générée une fois par ouverture de modale : un double-clic
  // sur « Générer » rejoue la même clé (Idempotent-Replay, 12 §1).
  const idempotencyKeyRef = useRef<string>(crypto.randomUUID());

  // Focus initial + restitution au démontage (Échap / annulation — Flux 5 a11y).
  useEffect(() => {
    const previouslyFocused = document.activeElement as HTMLElement | null;
    dialogRef.current
      ?.querySelector<HTMLElement>("input, button, [tabindex]")
      ?.focus();
    return () => previouslyFocused?.focus();
  }, []);

  /** Piège de focus minimal : Tab boucle dans la modale, Échap ferme. */
  const handleKeyDown = (event: KeyboardEvent) => {
    if (event.key === "Escape") {
      event.stopPropagation();
      onClose();
      return;
    }
    if (event.key !== "Tab" || !dialogRef.current) return;
    const focusables = [
      ...dialogRef.current.querySelectorAll<HTMLElement>(
        'a[href], button:not([disabled]), input:not([disabled]), [tabindex]:not([tabindex="-1"])',
      ),
    ];
    if (focusables.length === 0) return;
    const first = focusables[0];
    const last = focusables[focusables.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  };

  const createMutation = useMutation({
    mutationFn: () =>
      createGeneration(
        {
          doc_type: docType,
          job_id: docType === "cv_optimization" ? null : (jobId ?? null),
          application_id: applicationId ?? null,
          options: { tone, language, length },
        },
        idempotencyKeyRef.current,
      ),
    onSuccess: (document) => {
      // 202 → page du document en état « Génération en cours » (SCR-31).
      router.push(`/candidatures/documents/${document.id}`);
    },
  });

  const error = createMutation.error;
  let errorContent: ReactNode = null;
  if (error) {
    if (isApiProblem(error) && error.status === 429) {
      // M4-b : quota LLM atteint, heure de déblocage depuis Retry-After.
      const unlockAt = new Date(Date.now() + (error.retryAfter ?? 3600) * 1000);
      errorContent = t("modal.errors.quota", {
        hourly: GENERATION_QUOTA_HOURLY,
        daily: GENERATION_QUOTA_DAILY,
        time: new Intl.DateTimeFormat(locale, { timeStyle: "short" }).format(unlockAt),
      });
    } else if (
      isApiProblem(error) &&
      error.status === 409 &&
      error.type?.includes("profile_not_validated")
    ) {
      errorContent = (
        <>
          <p>{t("modal.errors.profileNotValidated")}</p>
          <Link
            href="/profil"
            className="mt-1 inline-flex min-h-11 items-center font-medium underline underline-offset-4 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
          >
            {t("modal.errors.profileNotValidatedCta")}
          </Link>
        </>
      );
    } else if (
      isApiProblem(error) &&
      error.status === 409 &&
      error.type?.includes("job_expired")
    ) {
      errorContent = t("modal.errors.jobExpired");
    } else {
      errorContent = t("modal.errors.generic");
    }
  }

  // Le bouton « Générer » reste désactivé tant que le quota est nul (Flux 5).
  const quotaBlocked = isApiProblem(error) && error.status === 429;

  const titleId = `${baseId}-title`;
  const isCvVariant = docType === "cv_variant" || docType === "cv_optimization";

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center overflow-y-auto p-4"
      onKeyDown={handleKeyDown}
    >
      {/* Voile d'arrière-plan (les tokens n'exposent pas d'alpha : opacité dédiée). */}
      <div aria-hidden="true" className="absolute inset-0 bg-content opacity-40" />
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        className="relative my-8 w-full max-w-lg space-y-4 rounded-lg border border-border bg-surface p-6"
      >
        <h2 id={titleId} className="text-lg font-semibold text-content">
          {t("modal.title")}
        </h2>

        <p className="text-sm text-content">
          <span className="font-medium">{t("modal.docTypeLabel")} : </span>
          {t(`docTypes.${docType}`)}
        </p>

        <OptionGroup
          legend={t("modal.toneLegend")}
          name={`${baseId}-tone`}
          options={TONES}
          value={tone}
          onChange={setTone}
          labelFor={(option) => t(`modal.tones.${option}`)}
        />
        <OptionGroup
          legend={t("modal.languageLegend")}
          name={`${baseId}-language`}
          options={LANGUAGES}
          value={language}
          onChange={setLanguage}
          labelFor={(option) => t(`modal.languages.${option}`)}
        />
        <OptionGroup
          legend={t("modal.lengthLegend")}
          name={`${baseId}-length`}
          options={LENGTHS}
          value={length}
          onChange={setLength}
          labelFor={(option) => t(`modal.lengths.${option}`)}
        />

        {/* Quotas affichés avant l'action (03 §3 règles transverses). 🟡 pas
            d'endpoint de quota restant — limites contractuelles affichées. */}
        <p className="text-sm text-content-secondary">
          {t("modal.quotaInfo", {
            hourly: GENERATION_QUOTA_HOURLY,
            daily: GENERATION_QUOTA_DAILY,
          })}
        </p>

        {/* Avertissement anti-invention M4-a — systématique, non désactivable. */}
        <Alert variant="info" title={t("modal.warningTitle")}>
          <p>{t("modal.warningBody")}</p>
          {isCvVariant ? <p className="mt-1">{t("modal.variantNote")}</p> : null}
        </Alert>

        {errorContent ? <Alert variant="error">{errorContent}</Alert> : null}

        <div className="flex flex-wrap gap-3">
          <Button
            onClick={() => createMutation.mutate()}
            disabled={createMutation.isPending || quotaBlocked}
            aria-busy={createMutation.isPending}
          >
            {t("modal.submit")}
          </Button>
          <Button variant="secondary" onClick={onClose}>
            {t("modal.cancel")}
          </Button>
        </div>

        {/* Rappel M6 — pied de SCR-30. */}
        <p className="text-sm text-content-secondary">{t("modal.noAutoSend")}</p>
      </div>
    </div>
  );
}
