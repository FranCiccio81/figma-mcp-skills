"use client";

import { useEffect, useId, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import type { ContractType, RemotePolicy } from "@/lib/api/types";

/** Valeurs de filtre pilotées par l'URL (partage / rafraîchissement, Flux 3 §3). */
export interface JobFiltersValue {
  remote: RemotePolicy[];
  contract: ContractType[];
  salaryMin: number | null;
  /** Fraîcheur en jours (`posted_since`) — `null` = toutes les dates. */
  postedSince: number | null;
  /** « Sauvegardées uniquement » (`saved_only`). */
  savedOnly: boolean;
}

export interface JobFiltersProps {
  value: JobFiltersValue;
  /** Mise à jour partielle — l'appelant fusionne et resynchronise l'URL. */
  onChange: (patch: Partial<JobFiltersValue>) => void;
  /** Réinitialise tous les filtres (et le `q` côté page). */
  onReset: () => void;
}

const REMOTE_OPTIONS: RemotePolicy[] = ["onsite", "hybrid", "full_remote"];
const CONTRACT_OPTIONS: ContractType[] = [
  "permanent",
  "fixed_term",
  "freelance",
  "internship",
  "apprenticeship",
  "other",
];
const POSTED_SINCE_OPTIONS = [1, 7, 30] as const;

function toggle<T>(list: T[], item: T, checked: boolean): T[] {
  return checked ? [...list, item] : list.filter((entry) => entry !== item);
}

/**
 * Panneau de filtres de la recherche d'offres (SCR-20, Flux 3 §3) :
 * télétravail et contrat en groupes `fieldset`/`legend`, salaire minimum,
 * fraîcheur, interrupteur « Sauvegardées uniquement » (vrai `role="switch"`,
 * état annoncé). Cibles tactiles ≥ 44 px, aucune couleur en dur.
 */
export function JobFilters({ value, onChange, onReset }: JobFiltersProps) {
  const t = useTranslations("jobs.filters");
  const tJobs = useTranslations("jobs");
  const baseId = useId();

  // Saisie locale du salaire, propagée après 300 ms d'inactivité (même
  // pattern que le champ q) : une requête par frappe déclencherait le
  // rate-limit et polluerait le cache de recherche.
  const [salaryDraft, setSalaryDraft] = useState<string>(
    value.salaryMin === null ? "" : String(value.salaryMin)
  );
  const salaryCommitted = useRef(value.salaryMin);
  useEffect(() => {
    if (value.salaryMin !== salaryCommitted.current) {
      salaryCommitted.current = value.salaryMin;
      setSalaryDraft(value.salaryMin === null ? "" : String(value.salaryMin));
    }
  }, [value.salaryMin]);
  useEffect(() => {
    const timer = setTimeout(() => {
      const parsed = Number.parseInt(salaryDraft, 10);
      const next = Number.isNaN(parsed) ? null : parsed;
      if (next !== salaryCommitted.current) {
        salaryCommitted.current = next;
        onChange({ salaryMin: next });
      }
    }, 300);
    return () => clearTimeout(timer);
  }, [salaryDraft, onChange]);
  const salaryId = `${baseId}-salary`;
  const postedId = `${baseId}-posted`;
  const savedOnlyId = `${baseId}-saved-only`;

  const checkboxLabelClass =
    "flex min-h-11 cursor-pointer items-center gap-2 text-sm text-content";
  const checkboxClass =
    "h-5 w-5 shrink-0 rounded border-border accent-action-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus";

  return (
    <section
      aria-labelledby={`${baseId}-title`}
      className="space-y-5 rounded-lg border border-border bg-surface p-4"
    >
      <h2 id={`${baseId}-title`} className="text-sm font-semibold text-content">
        {t("title")}
      </h2>

      <fieldset>
        <legend className="text-sm font-medium text-content">{t("remoteLegend")}</legend>
        <div className="mt-1">
          {REMOTE_OPTIONS.map((option) => (
            <label key={option} className={checkboxLabelClass}>
              <input
                type="checkbox"
                className={checkboxClass}
                checked={value.remote.includes(option)}
                onChange={(event) =>
                  onChange({ remote: toggle(value.remote, option, event.target.checked) })
                }
              />
              {tJobs(`remote.${option}`)}
            </label>
          ))}
        </div>
      </fieldset>

      <fieldset>
        <legend className="text-sm font-medium text-content">{t("contractLegend")}</legend>
        <div className="mt-1">
          {CONTRACT_OPTIONS.map((option) => (
            <label key={option} className={checkboxLabelClass}>
              <input
                type="checkbox"
                className={checkboxClass}
                checked={value.contract.includes(option)}
                onChange={(event) =>
                  onChange({ contract: toggle(value.contract, option, event.target.checked) })
                }
              />
              {tJobs(`contract.${option}`)}
            </label>
          ))}
        </div>
      </fieldset>

      <div className="space-y-1.5">
        <label htmlFor={salaryId} className="block text-sm font-medium text-content">
          {t("salaryMinLabel")}
        </label>
        <Input
          id={salaryId}
          type="number"
          inputMode="numeric"
          min={0}
          step={1000}
          value={salaryDraft}
          onChange={(event) => setSalaryDraft(event.target.value)}
        />
      </div>

      <div className="space-y-1.5">
        <label htmlFor={postedId} className="block text-sm font-medium text-content">
          {t("postedSinceLabel")}
        </label>
        <select
          id={postedId}
          value={value.postedSince ?? ""}
          onChange={(event) => {
            const parsed = Number.parseInt(event.target.value, 10);
            onChange({ postedSince: Number.isNaN(parsed) ? null : parsed });
          }}
          className="h-11 w-full rounded-md border border-border bg-surface px-3 text-sm text-content focus:border-action-primary focus:shadow-input-focus focus:outline-none"
        >
          <option value="">{t("postedSinceAny")}</option>
          {POSTED_SINCE_OPTIONS.map((days) => (
            <option key={days} value={days}>
              {t("postedSinceDays", { days })}
            </option>
          ))}
        </select>
      </div>

      <div className="flex min-h-11 items-center justify-between gap-3 border-t border-border pt-4">
        <label htmlFor={savedOnlyId} className="text-sm font-medium text-content">
          {t("savedOnlyLabel")}
        </label>
        <button
          id={savedOnlyId}
          type="button"
          role="switch"
          aria-checked={value.savedOnly}
          onClick={() => onChange({ savedOnly: !value.savedOnly })}
          className="relative inline-flex h-11 w-14 shrink-0 items-center rounded-full focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus focus-visible:ring-offset-2 focus-visible:ring-offset-surface"
        >
          <span
            aria-hidden="true"
            className={`h-6 w-full rounded-full transition-colors ${
              value.savedOnly ? "bg-action-primary" : "bg-border-strong"
            }`}
          />
          <span
            aria-hidden="true"
            className={`absolute top-1/2 h-5 w-5 -translate-y-1/2 rounded-full bg-surface transition-all ${
              value.savedOnly ? "left-8" : "left-1"
            }`}
          />
        </button>
      </div>

      <Button variant="secondary" onClick={onReset} className="w-full">
        {t("reset")}
      </Button>
    </section>
  );
}
