"use client";

// SCR-07 — M3
// Préférences de recherche (Flux 2) : métiers cibles en tags, lieux avec
// rayon (🟡 saisie ville en texte libre — le géocodage lat/lon arrive au
// jalon M4), télétravail, contrats + mode strict, salaire souhaité / minimum
// strict (avec explication de la différence), secteurs préférés/exclus,
// entreprises cibles, mots-clés. `PUT /preferences` en payload complet à la
// sauvegarde (l'UI envoie toujours l'état entier du formulaire) ; les caches
// match sont invalidés (re-scoring asynchrone, 06 §4).

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { useMemo, useRef, useState } from "react";
import { Controller, useFieldArray, useForm } from "react-hook-form";
import { z } from "zod";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { FormField, fieldDescribedBy } from "@/components/ui/form-field";
import { Input } from "@/components/ui/input";
import { TagListInput } from "@/components/ui/tag-list-input";
import { isApiProblem } from "@/lib/api/client";
import { invalidateMatchDependentQueries } from "@/lib/api/matching";
import { getPreferences, preferencesKeys, putPreferences } from "@/lib/api/preferences";
import type { ContractType, Preferences, RemotePreference } from "@/lib/api/types";

const REMOTE_PREF_OPTIONS: RemotePreference[] = [
  "required",
  "preferred",
  "indifferent",
  "onsite_preferred",
];

const CONTRACT_OPTIONS: ContractType[] = [
  "permanent",
  "fixed_term",
  "freelance",
  "internship",
  "apprenticeship",
  "other",
];

/** Rayon par défaut d'un nouveau lieu (openapi.yaml : 30 km). */
const DEFAULT_RADIUS_KM = 30;

/** Valeurs par défaut du premier passage (`GET /preferences` vide, Flux 2 §1). */
function toFormValues(preferences: Preferences | undefined) {
  return {
    remote_pref: preferences?.remote_pref ?? ("indifferent" as RemotePreference),
    contract_types: preferences?.contract_types ?? [],
    contract_strict: preferences?.contract_strict ?? false,
    salary_min: preferences?.salary_min ?? null,
    salary_min_strict: preferences?.salary_min_strict ?? null,
    locations:
      preferences?.locations?.map((location) => ({
        label: location.label,
        lat: location.lat,
        lon: location.lon,
        radius_km: location.radius_km ?? DEFAULT_RADIUS_KM,
      })) ?? [],
    target_titles: preferences?.target_titles ?? [],
    sectors_preferred: preferences?.sectors_preferred ?? [],
    sectors_excluded: preferences?.sectors_excluded ?? [],
    target_companies: preferences?.target_companies ?? [],
    keywords: preferences?.keywords ?? [],
  };
}

/**
 * Formulaire complet SCR-07 — validation Zod miroir des règles API
 * (minimum strict ≤ salaire souhaité, rayon 1–500 km, lieu nommé), envoi
 * `PUT` du payload entier, erreurs 422 mappées par champ, focus déplacé sur
 * le bandeau d'erreur ou de succès (a11y Flux 2).
 */
function PreferencesForm({ initial }: { initial: Preferences | undefined }) {
  const t = useTranslations("preferences");
  const tJobs = useTranslations("jobs");
  const tv = useTranslations("validation");
  const queryClient = useQueryClient();
  const [serverError, setServerError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const serverErrorRef = useRef<HTMLDivElement>(null);
  const savedRef = useRef<HTMLDivElement>(null);

  const schema = useMemo(
    () =>
      z
        .object({
          remote_pref: z.enum(REMOTE_PREF_OPTIONS as [RemotePreference, ...RemotePreference[]]),
          contract_types: z.array(
            z.enum(CONTRACT_OPTIONS as [ContractType, ...ContractType[]]),
          ),
          contract_strict: z.boolean(),
          salary_min: z.union([z.number().int().min(0), z.null()]),
          salary_min_strict: z.union([z.number().int().min(0), z.null()]),
          locations: z.array(
            z.object({
              label: z.string().min(1, tv("required")),
              lat: z.number(),
              lon: z.number(),
              radius_km: z
                .number({ invalid_type_error: t("validation.radiusRange") })
                .int()
                .min(1, t("validation.radiusRange"))
                .max(500, t("validation.radiusRange")),
            }),
          ),
          target_titles: z.array(z.string()),
          sectors_preferred: z.array(z.string()),
          sectors_excluded: z.array(z.string()),
          target_companies: z.array(z.string()),
          keywords: z.array(z.string()),
        })
        .superRefine((values, ctx) => {
          // Miroir de la règle API : minimum strict ≤ salaire souhaité.
          if (
            values.salary_min !== null &&
            values.salary_min_strict !== null &&
            values.salary_min_strict > values.salary_min
          ) {
            ctx.addIssue({
              code: z.ZodIssueCode.custom,
              path: ["salary_min_strict"],
              message: t("validation.strictAboveMin"),
            });
          }
        }),
    [t, tv],
  );
  type FormValues = z.infer<typeof schema>;

  const {
    register,
    control,
    handleSubmit,
    setError,
    watch,
    formState: { errors },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: toFormValues(initial),
  });

  const locationsArray = useFieldArray({ control, name: "locations" });
  const targetTitles = watch("target_titles");

  const mutation = useMutation({
    mutationFn: (values: FormValues) => putPreferences(values),
    onSuccess: () => {
      setServerError(null);
      setSaved(true);
      void queryClient.invalidateQueries({ queryKey: preferencesKeys.root });
      // Le re-scoring est asynchrone (06 §4) : tous les scores affichés sont périmés.
      invalidateMatchDependentQueries(queryClient);
      requestAnimationFrame(() => savedRef.current?.focus());
    },
    onError: (error) => {
      setSaved(false);
      if (isApiProblem(error) && error.status === 422 && error.errors.length > 0) {
        // 422 : erreurs mappées par champ quand le chemin correspond (Flux 2).
        let mapped = false;
        for (const fieldError of error.errors) {
          if (fieldError.field) {
            setError(fieldError.field as Parameters<typeof setError>[0], {
              type: "server",
              message: fieldError.message,
            });
            mapped = true;
          }
        }
        if (mapped) return;
      }
      setServerError(isApiProblem(error) && error.detail ? error.detail : t("errorSave"));
      requestAnimationFrame(() => serverErrorRef.current?.focus());
    },
  });

  const checkboxLabelClass =
    "flex min-h-11 cursor-pointer items-center gap-2 text-sm text-content";
  const checkboxClass =
    "h-5 w-5 shrink-0 rounded border-border accent-action-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus";

  const strictConsequenceId = "preferences-strict-consequence";
  const salaryDifferenceId = "preferences-salary-difference";

  return (
    <form
      noValidate
      onSubmit={handleSubmit((values) => mutation.mutate(values))}
      className="space-y-8"
    >
      {serverError ? (
        <Alert ref={serverErrorRef} tabIndex={-1} variant="error">
          {serverError}
        </Alert>
      ) : null}
      {saved ? (
        <Alert ref={savedRef} tabIndex={-1} variant="success">
          <div className="flex flex-wrap items-center gap-3">
            <span>{t("success")}</span>
            <Link
              href="/offres"
              className="font-medium text-action-primary underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
            >
              {t("seeJobs")}
            </Link>
          </div>
        </Alert>
      ) : null}

      {/* Métiers cibles */}
      <fieldset className="space-y-3">
        <legend className="text-lg font-semibold text-content">
          {t("targetTitles.legend")}
        </legend>
        <Controller
          control={control}
          name="target_titles"
          render={({ field }) => (
            <TagListInput
              label={t("targetTitles.inputLabel")}
              value={field.value}
              onChange={field.onChange}
              removeAriaLabel={(item) => t("targetTitles.removeAria", { label: item })}
            />
          )}
        />
        {targetTitles.length === 0 ? (
          <p className="text-sm text-content-secondary">{t("targetTitles.emptyNote")}</p>
        ) : null}
      </fieldset>

      {/* Localisations — 🟡 géocodage différé au jalon M4 (ville en texte libre). */}
      <fieldset className="space-y-3">
        <legend className="text-lg font-semibold text-content">{t("locations.legend")}</legend>
        <p className="max-w-prose text-sm text-content-secondary">
          {t("locations.geocodingNote")}
        </p>
        {locationsArray.fields.length > 0 ? (
          <ul className="space-y-3">
            {locationsArray.fields.map((field, index) => {
              const cityId = `location-${field.id}-city`;
              const radiusId = `location-${field.id}-radius`;
              return (
                <li
                  key={field.id}
                  className="flex flex-wrap items-end gap-3 rounded-md border border-border p-3"
                >
                  <div className="min-w-40 flex-1">
                    <FormField
                      id={cityId}
                      label={t("locations.cityLabel")}
                      required
                      error={errors.locations?.[index]?.label?.message}
                    >
                      <Input
                        id={cityId}
                        aria-invalid={errors.locations?.[index]?.label ? true : undefined}
                        aria-describedby={fieldDescribedBy(cityId, {
                          error: Boolean(errors.locations?.[index]?.label),
                        })}
                        {...register(`locations.${index}.label`)}
                      />
                    </FormField>
                  </div>
                  <div className="w-32">
                    <FormField
                      id={radiusId}
                      label={t("locations.radiusLabel")}
                      error={errors.locations?.[index]?.radius_km?.message}
                    >
                      <Input
                        id={radiusId}
                        type="number"
                        inputMode="numeric"
                        min={1}
                        max={500}
                        aria-invalid={errors.locations?.[index]?.radius_km ? true : undefined}
                        aria-describedby={fieldDescribedBy(radiusId, {
                          error: Boolean(errors.locations?.[index]?.radius_km),
                        })}
                        {...register(`locations.${index}.radius_km`, { valueAsNumber: true })}
                      />
                    </FormField>
                  </div>
                  <Button
                    variant="ghost"
                    aria-label={t("locations.removeAria", {
                      label: watch(`locations.${index}.label`) || t("locations.cityLabel"),
                    })}
                    onClick={() => locationsArray.remove(index)}
                  >
                    {t("locations.remove")}
                  </Button>
                </li>
              );
            })}
          </ul>
        ) : (
          <p className="text-sm text-content-secondary">{t("locations.empty")}</p>
        )}
        <Button
          variant="secondary"
          onClick={() =>
            locationsArray.append({ label: "", lat: 0, lon: 0, radius_km: DEFAULT_RADIUS_KM })
          }
        >
          <Plus aria-hidden="true" className="h-4 w-4" />
          {t("locations.add")}
        </Button>
      </fieldset>

      {/* Télétravail */}
      <fieldset className="space-y-2">
        <legend className="text-lg font-semibold text-content">{t("remote.legend")}</legend>
        {REMOTE_PREF_OPTIONS.map((option) => (
          <label key={option} className={checkboxLabelClass}>
            <input
              type="radio"
              value={option}
              className={checkboxClass}
              {...register("remote_pref")}
            />
            {t(`remote.options.${option}`)}
          </label>
        ))}
      </fieldset>

      {/* Contrats + mode strict */}
      <fieldset className="space-y-2">
        <legend className="text-lg font-semibold text-content">{t("contracts.legend")}</legend>
        {CONTRACT_OPTIONS.map((option) => (
          <label key={option} className={checkboxLabelClass}>
            <input
              type="checkbox"
              value={option}
              className={checkboxClass}
              {...register("contract_types")}
            />
            {tJobs(`contract.${option}`)}
          </label>
        ))}
        <label className={checkboxLabelClass}>
          <input
            type="checkbox"
            className={checkboxClass}
            aria-describedby={strictConsequenceId}
            {...register("contract_strict")}
          />
          {t("contracts.strictLabel")}
        </label>
        {/* Conséquence des options strictes, liée par aria-describedby (Flux 2 §4). */}
        <p id={strictConsequenceId} className="max-w-prose text-sm text-content-secondary">
          {t("strictConsequence")}
        </p>
      </fieldset>

      {/* Salaire */}
      <fieldset className="space-y-3">
        <legend className="text-lg font-semibold text-content">{t("salary.legend")}</legend>
        <p id={salaryDifferenceId} className="max-w-prose text-sm text-content-secondary">
          {t("salary.difference")}
        </p>
        <div className="grid gap-4 sm:grid-cols-2">
          <FormField
            id="preferences-salary-min"
            label={t("salary.minLabel")}
            error={errors.salary_min?.message}
          >
            <Input
              id="preferences-salary-min"
              type="number"
              inputMode="numeric"
              min={0}
              step={1000}
              aria-describedby={salaryDifferenceId}
              aria-invalid={errors.salary_min ? true : undefined}
              {...register("salary_min", {
                setValueAs: (raw) =>
                  raw === "" || raw === null || Number.isNaN(Number(raw)) ? null : Number(raw),
              })}
            />
          </FormField>
          <FormField
            id="preferences-salary-strict"
            label={t("salary.strictMinLabel")}
            error={errors.salary_min_strict?.message}
          >
            <Input
              id="preferences-salary-strict"
              type="number"
              inputMode="numeric"
              min={0}
              step={1000}
              aria-describedby={`${salaryDifferenceId} ${strictConsequenceId}`}
              aria-invalid={errors.salary_min_strict ? true : undefined}
              {...register("salary_min_strict", {
                setValueAs: (raw) =>
                  raw === "" || raw === null || Number.isNaN(Number(raw)) ? null : Number(raw),
              })}
            />
          </FormField>
        </div>
      </fieldset>

      {/* Secteurs préférés / exclus */}
      <fieldset className="space-y-4">
        <legend className="text-lg font-semibold text-content">{t("sectors.legend")}</legend>
        <Controller
          control={control}
          name="sectors_preferred"
          render={({ field }) => (
            <TagListInput
              label={t("sectors.preferredLabel")}
              value={field.value}
              onChange={field.onChange}
              removeAriaLabel={(item) => t("sectors.removeAria", { label: item })}
            />
          )}
        />
        <Controller
          control={control}
          name="sectors_excluded"
          render={({ field }) => (
            <TagListInput
              label={t("sectors.excludedLabel")}
              description={t("strictConsequence")}
              value={field.value}
              onChange={field.onChange}
              removeAriaLabel={(item) => t("sectors.removeAria", { label: item })}
            />
          )}
        />
      </fieldset>

      {/* Entreprises cibles */}
      <fieldset className="space-y-3">
        <legend className="text-lg font-semibold text-content">{t("companies.legend")}</legend>
        <Controller
          control={control}
          name="target_companies"
          render={({ field }) => (
            <TagListInput
              label={t("companies.inputLabel")}
              value={field.value}
              onChange={field.onChange}
              removeAriaLabel={(item) => t("companies.removeAria", { label: item })}
            />
          )}
        />
      </fieldset>

      {/* Mots-clés */}
      <fieldset className="space-y-3">
        <legend className="text-lg font-semibold text-content">{t("keywords.legend")}</legend>
        <Controller
          control={control}
          name="keywords"
          render={({ field }) => (
            <TagListInput
              label={t("keywords.inputLabel")}
              value={field.value}
              onChange={field.onChange}
              removeAriaLabel={(item) => t("keywords.removeAria", { label: item })}
            />
          )}
        />
      </fieldset>

      <Button type="submit" disabled={mutation.isPending} aria-busy={mutation.isPending}>
        {mutation.isPending ? t("saving") : t("submit")}
      </Button>
    </form>
  );
}

export default function PreferencesPage() {
  const t = useTranslations("preferences");

  const preferencesQuery = useQuery({
    queryKey: preferencesKeys.root,
    queryFn: ({ signal }) => getPreferences(signal),
  });

  return (
    <section aria-labelledby="preferences-title" className="space-y-6">
      <h1 id="preferences-title" className="text-2xl font-semibold text-content">
        {t("title")}
      </h1>

      {preferencesQuery.isPending ? (
        <div role="status" aria-live="polite" className="space-y-4">
          <span className="sr-only">{t("loading")}</span>
          <div aria-hidden="true" className="h-32 animate-pulse rounded-lg bg-surface-muted" />
          <div aria-hidden="true" className="h-64 animate-pulse rounded-lg bg-surface-muted" />
        </div>
      ) : null}

      {preferencesQuery.isError ? (
        <Alert variant="error" title={t("errorTitle")}>
          <Button variant="secondary" onClick={() => void preferencesQuery.refetch()}>
            {t("retry")}
          </Button>
        </Alert>
      ) : null}

      {preferencesQuery.isSuccess ? <PreferencesForm initial={preferencesQuery.data} /> : null}
    </section>
  );
}
