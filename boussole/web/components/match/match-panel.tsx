"use client";

// SCR-21 (panneau match) + SCR-22 (explication) — M3
// Double affichage score/confiance (D03, microcopies M1 exactes — jamais
// fusionnés), critères bloquants en premier (M2 — jamais masqués), inconnues
// sous « Non précisé » (M3 — jamais estimées), dimensions détaillées
// (forces / lacunes, 06 §6), reformulation LLM à la demande (POST
// /jobs/{id}/explanation) avec quota 429 → M4-b. 409 profile_not_validated →
// encart d'invitation vers /profil, jamais d'erreur brute.

import { useMutation, useQuery } from "@tanstack/react-query";
import clsx from "clsx";
import { CircleHelp, Compass } from "lucide-react";
import Link from "next/link";
import { useLocale, useTranslations } from "next-intl";
import { useId, useMemo, useState } from "react";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { isApiProblem } from "@/lib/api/client";
import { getMatch, isProfileNotValidated, matchKeys, postExplanation } from "@/lib/api/matching";
import type { DimensionDetails, DimensionScore, UnknownDimension } from "@/lib/api/types";

/** Quotas LLM des explications (04 Flux 4 : 10/h, 40/j) — pour le message M4-b. */
const EXPLANATION_QUOTA_HOURLY = 10;
const EXPLANATION_QUOTA_DAILY = 40;

/** Seuils de la couche d'explication déterministe (06 §6). */
const STRENGTH_MIN_SUBSCORE = 0.8;
const STRENGTH_MIN_WEIGHT = 6;
const GAP_MAX_SUBSCORE = 0.4;

/**
 * 🟡 Identifiants de dimensions connus (06 §2 + exemple 12 §4) — traduits via
 * `match.dimensions.names.*` ; tout identifiant inconnu est affiché tel quel
 * (dé-snake-casé), jamais masqué.
 */
const KNOWN_DIMENSION_IDS: ReadonlySet<string> = new Set([
  "skills_required",
  "skills_nice",
  "title_similarity",
  "seniority",
  "experience_years",
  "sector",
  "location",
  "remote",
  "languages",
  "contract",
  "salary",
  "fine_preferences",
]);

type Translator = ReturnType<typeof useTranslations<"match">>;

/** Nom lisible d'une dimension — clé i18n si connue, identifiant brut sinon. */
function dimensionName(t: Translator, dimension: string): string {
  return KNOWN_DIMENSION_IDS.has(dimension)
    ? t(`dimensions.names.${dimension}` as Parameters<Translator>[0])
    : dimension.replaceAll("_", " ");
}

/** Libellé d'une inconnue : API repris tel quel (M3-a), fallback par côté manquant. */
function unknownLabel(t: Translator, unknown: UnknownDimension): string {
  if (unknown.label) return unknown.label;
  const label = dimensionName(t, unknown.dimension);
  if (unknown.reason === "profile_not_provided") return t("unknown.profileFallback", { label });
  if (unknown.reason === "low_extraction_confidence") {
    return t("unknown.uncertainFallback", { label });
  }
  return t("unknown.jobFallback", { label });
}

/** Lignes « valeurs comparées » d'une dimension (couvertes / proches / manquantes…). */
function detailLines(
  t: Translator,
  listFormat: Intl.ListFormat,
  details: DimensionDetails | undefined,
): string[] {
  if (!details) return [];
  const lines: string[] = [];
  if (details.matched && details.matched.length > 0) {
    lines.push(t("dimensions.matched", { items: listFormat.format(details.matched) }));
  }
  if (details.related && details.related.length > 0) {
    lines.push(
      t("dimensions.related", {
        items: listFormat.format(
          details.related.map((pair) =>
            t("dimensions.relatedPair", {
              required: pair.required,
              matchedWith: pair.matched_with,
            }),
          ),
        ),
      }),
    );
  }
  if (details.missing && details.missing.length > 0) {
    lines.push(t("dimensions.missing", { items: listFormat.format(details.missing) }));
  }
  if (typeof details.distance_km === "number") {
    lines.push(
      details.matched_location
        ? t("dimensions.distanceWithLocation", {
            distance: details.distance_km,
            location: details.matched_location,
          })
        : t("dimensions.distance", { distance: details.distance_km }),
    );
  }
  return lines;
}

interface ScoreMeterProps {
  labelId: string;
  /** Libellé M1-b en gras (ex. « Compatibilité : 72 / 100 »). */
  label: string;
  /** Suite de la microcopie M1-b après le tiret. */
  help: string;
  value: number;
  /** `low_data` : jauge et libellé grisés mais lisibles (jamais `disabled`). */
  muted?: boolean;
}

/**
 * Jauge accessible d'un score sur 100 : `role="meter"` + `aria-valuenow`,
 * texte visible équivalent (04 Flux 4 a11y — jamais deux chiffres orphelins).
 */
function ScoreMeter({ labelId, label, help, value, muted }: ScoreMeterProps) {
  return (
    <div className="space-y-1">
      <p id={labelId} className="text-sm">
        <strong className={muted ? "text-content-secondary" : "text-content"}>{label}</strong>
        <span className="text-content-secondary"> — {help}</span>
      </p>
      <div
        role="meter"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={value}
        aria-labelledby={labelId}
        className="h-2 w-full max-w-md overflow-hidden rounded-full border border-border bg-surface-muted"
      >
        {/* Largeur dynamique : style inline justifié (valeur calculée). */}
        <div
          aria-hidden="true"
          className={clsx("h-full rounded-full", muted ? "bg-border-strong" : "bg-action-primary")}
          style={{ width: `${Math.max(0, Math.min(100, value))}%` }}
        />
      </div>
    </div>
  );
}

/** Ligne d'une dimension : nom, sous-score (jauge + texte), poids, valeurs comparées. */
function DimensionRow({ dimension }: { dimension: DimensionScore }) {
  const t = useTranslations("match");
  const locale = useLocale();
  const labelId = useId();
  const percent = Math.round(dimension.subscore * 100);
  const listFormat = useMemo(() => new Intl.ListFormat(locale), [locale]);
  const lines = detailLines(t, listFormat, dimension.details);

  return (
    <li className="space-y-1.5 rounded-md border border-border bg-surface p-3">
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
        <span id={labelId} className="text-sm font-medium text-content">
          {dimensionName(t, dimension.dimension)}
        </span>
        <span className="text-sm text-content-secondary">
          {t("dimensions.subscoreText", { percent })} · {t("dimensions.weight", { weight: dimension.weight })}
        </span>
      </div>
      <div
        role="meter"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={percent}
        aria-labelledby={labelId}
        className="h-1.5 w-full max-w-sm overflow-hidden rounded-full border border-border bg-surface-muted"
      >
        <div
          aria-hidden="true"
          className="h-full rounded-full bg-action-primary"
          style={{ width: `${percent}%` }}
        />
      </div>
      {lines.length > 0 ? (
        <ul className="space-y-0.5 text-sm text-content-secondary">
          {lines.map((line) => (
            <li key={line}>{line}</li>
          ))}
        </ul>
      ) : null}
    </li>
  );
}

/** Groupe de dimensions (Forces / Lacunes / Autres critères connus). */
function DimensionGroup({
  titleId,
  title,
  dimensions,
}: {
  titleId: string;
  title: string;
  dimensions: DimensionScore[];
}) {
  if (dimensions.length === 0) return null;
  return (
    <div className="space-y-2">
      <h4 id={titleId} className="text-sm font-semibold text-content">
        {title}
      </h4>
      <ul aria-labelledby={titleId} className="space-y-2">
        {dimensions.map((dimension) => (
          <DimensionRow key={dimension.dimension} dimension={dimension} />
        ))}
      </ul>
    </div>
  );
}

export interface MatchPanelProps {
  jobId: string;
}

/**
 * Panneau match du détail d'offre (SCR-21 §3) — `GET /jobs/{id}/match` puis,
 * à la demande, `POST /jobs/{id}/explanation`. Ordre imposé : bloquants →
 * inconnues → dimensions (04 Flux 4 §3). Le score `low_data` est grisé mais
 * reste lisible (contraste ≥ 4,5:1 — jamais `text-content-disabled`).
 */
export function MatchPanel({ jobId }: MatchPanelProps) {
  const t = useTranslations("match");
  const locale = useLocale();
  const baseId = useId();
  const [helpOpen, setHelpOpen] = useState(false);

  const matchQuery = useQuery({
    queryKey: matchKeys.job(jobId),
    queryFn: ({ signal }) => getMatch(jobId, signal),
  });

  const explanationMutation = useMutation({ mutationFn: () => postExplanation(jobId) });

  const heading = (
    <h2
      id="job-match-title"
      className="flex items-center gap-2 text-lg font-semibold text-content"
    >
      <Compass aria-hidden="true" className="h-5 w-5" />
      {t("panel.title")}
    </h2>
  );

  const sectionClass = "space-y-4 rounded-lg border border-border bg-surface p-4";

  if (matchQuery.isPending) {
    return (
      <section aria-labelledby="job-match-title" className={sectionClass}>
        {heading}
        <div role="status" aria-live="polite">
          <span className="sr-only">{t("panel.loading")}</span>
          <div aria-hidden="true" className="h-24 animate-pulse rounded-md bg-surface-muted" />
        </div>
      </section>
    );
  }

  if (matchQuery.isError) {
    // Profil non validé (409) : invitation à compléter/valider — pas d'erreur brute.
    if (isProfileNotValidated(matchQuery.error)) {
      return (
        <section aria-labelledby="job-match-title" className={sectionClass}>
          {heading}
          <Alert variant="info" title={t("panel.notValidatedTitle")}>
            <p>{t("panel.notValidatedBody")}</p>
            <Link
              href="/profil"
              className="mt-2 inline-flex min-h-11 items-center font-medium text-action-primary underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
            >
              {t("panel.notValidatedCta")}
            </Link>
          </Alert>
        </section>
      );
    }
    return (
      <section aria-labelledby="job-match-title" className={sectionClass}>
        {heading}
        <Alert variant="error" title={t("panel.errorTitle")}>
          <Button variant="secondary" onClick={() => void matchQuery.refetch()}>
            {t("panel.retry")}
          </Button>
        </Alert>
      </section>
    );
  }

  const match = matchQuery.data;
  const knownDimensions = match.dimensions.filter((dimension) => dimension.known);
  const strengths = knownDimensions.filter(
    (d) => d.subscore >= STRENGTH_MIN_SUBSCORE && d.weight >= STRENGTH_MIN_WEIGHT,
  );
  const gaps = knownDimensions.filter((d) => d.subscore <= GAP_MAX_SUBSCORE);
  const others = knownDimensions.filter(
    (d) => !strengths.includes(d) && !gaps.includes(d),
  );

  const explanationError = explanationMutation.error;
  let explanationErrorMessage: string | null = null;
  if (explanationError) {
    if (isApiProblem(explanationError) && explanationError.status === 429) {
      const unlockAt = new Date(Date.now() + (explanationError.retryAfter ?? 3600) * 1000);
      explanationErrorMessage = t("explanation.quota", {
        hourly: EXPLANATION_QUOTA_HOURLY,
        daily: EXPLANATION_QUOTA_DAILY,
        time: new Intl.DateTimeFormat(locale, { timeStyle: "short" }).format(unlockAt),
      });
    } else {
      explanationErrorMessage = t("explanation.failed");
    }
  }

  return (
    <section aria-labelledby="job-match-title" className={sectionClass}>
      {heading}

      {/* Double score — groupe avec libellé complet lisible par lecteur d'écran
          (« Compatibilité 72 sur 100. Confiance 61 sur 100. »), jamais deux
          chiffres orphelins (04 Flux 4 a11y). */}
      <div
        role="group"
        aria-label={t("panel.groupAria", { score: match.score, confidence: match.confidence })}
        className="space-y-3"
      >
        <ScoreMeter
          labelId={`${baseId}-score`}
          label={t("panel.scoreLabel", { score: match.score })}
          help={t("panel.scoreHelp")}
          value={match.score}
          muted={match.low_data}
        />
        <ScoreMeter
          labelId={`${baseId}-confidence`}
          label={t("panel.confidenceLabel", { confidence: match.confidence })}
          help={t("panel.confidenceHelp")}
          value={match.confidence}
        />
        <button
          type="button"
          aria-expanded={helpOpen}
          aria-controls={`${baseId}-help`}
          onClick={() => setHelpOpen((open) => !open)}
          className="inline-flex min-h-11 items-center gap-1.5 rounded-sm text-sm font-medium text-action-primary underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
        >
          <CircleHelp aria-hidden="true" className="h-4 w-4" />
          {t("panel.helpToggle")}
        </button>
        {helpOpen ? (
          <p id={`${baseId}-help`} className="max-w-prose text-sm text-content-secondary">
            {t("panel.helpText")}
          </p>
        ) : null}
      </div>

      {match.low_data ? (
        <Alert variant="warning" title={t("panel.lowDataTitle")}>
          {t("panel.lowDataBody", { score: match.score })}
        </Alert>
      ) : null}

      {/* (a) Critères bloquants — toujours en premier, jamais masqués (M2). */}
      {match.blocking_criteria.length > 0 ? (
        <div className="space-y-2">
          <h3 id={`${baseId}-blocking`} className="text-base font-semibold text-content">
            {t("blocking.title")}
          </h3>
          <ul aria-labelledby={`${baseId}-blocking`} className="space-y-2">
            {match.blocking_criteria.map((criterion) => (
              <li
                key={criterion.code}
                className="space-y-1 rounded-md bg-feedback-error-surface p-3 text-sm"
              >
                <span className="inline-block rounded-md px-1 font-semibold text-feedback-error">
                  {t("blocking.badge")}
                </span>
                <p className="text-content">
                  {criterion.label ?? t("blocking.fallbackLabel", { code: criterion.code })}
                </p>
              </li>
            ))}
          </ul>
          <p className="max-w-prose text-sm text-content-secondary">
            {t("blocking.transparency")}
          </p>
        </div>
      ) : null}

      {/* (b) Inconnues — listées sous « Non précisé », jamais estimées (M3). */}
      {match.unknown_dimensions.length > 0 ? (
        <div className="space-y-2">
          <h3 id={`${baseId}-unknown`} className="text-base font-semibold text-content">
            {t("unknown.title")}
          </h3>
          <ul aria-labelledby={`${baseId}-unknown`} className="list-disc space-y-1 pl-5 text-sm text-content">
            {match.unknown_dimensions.map((unknown) => (
              <li key={unknown.dimension}>{unknownLabel(t, unknown)}</li>
            ))}
          </ul>
          <p className="max-w-prose text-sm text-content-secondary">{t("unknown.note")}</p>
        </div>
      ) : null}

      {/* (c) Dimensions détaillées — forces / lacunes / autres (06 §6). */}
      {knownDimensions.length > 0 ? (
        <div className="space-y-4">
          <h3 className="text-base font-semibold text-content">{t("dimensions.title")}</h3>
          <DimensionGroup
            titleId={`${baseId}-strengths`}
            title={t("dimensions.strengths")}
            dimensions={strengths}
          />
          <DimensionGroup
            titleId={`${baseId}-gaps`}
            title={t("dimensions.gaps")}
            dimensions={gaps}
          />
          <DimensionGroup
            titleId={`${baseId}-others`}
            title={t("dimensions.others")}
            dimensions={others}
          />
        </div>
      ) : null}

      {/* Explication LLM (SCR-22) — à la demande, quota 429 → M4-b. */}
      <div className="space-y-3 border-t border-border pt-4">
        <h3 className="text-base font-semibold text-content">{t("explanation.title")}</h3>
        <Button
          variant="secondary"
          onClick={() => explanationMutation.mutate()}
          disabled={explanationMutation.isPending}
          aria-busy={explanationMutation.isPending}
        >
          {explanationMutation.isPending ? t("explanation.loading") : t("explanation.cta")}
        </Button>

        {/* Arrivée de la reformulation annoncée (aria-live="polite", Flux 4 a11y). */}
        <div aria-live="polite" className="space-y-3">
          {explanationMutation.isPending ? (
            <p role="status" className="text-sm text-content-secondary">
              {t("explanation.loading")}
            </p>
          ) : null}

          {explanationErrorMessage ? (
            <Alert variant="warning">{explanationErrorMessage}</Alert>
          ) : null}

          {explanationMutation.isSuccess ? (
            <div className="space-y-3">
              <p className="max-w-prose text-sm text-content">
                {explanationMutation.data.summary}
              </p>
              {(
                [
                  ["strengths", explanationMutation.data.strengths],
                  ["gaps", explanationMutation.data.gaps],
                  ["uncertainties", explanationMutation.data.uncertainties],
                  ["blockingNotes", explanationMutation.data.blocking_notes],
                ] as const
              ).map(([key, items]) =>
                items.length > 0 ? (
                  <div key={key} className="space-y-1">
                    <h4 className="text-sm font-semibold text-content">
                      {t(`explanation.${key}`)}
                    </h4>
                    <ul className="list-disc space-y-0.5 pl-5 text-sm text-content">
                      {items.map((item) => (
                        <li key={item}>{item}</li>
                      ))}
                    </ul>
                  </div>
                ) : null,
              )}
              {/* Mention obligatoire : l'explication reformule les faits calculés. */}
              <p className="text-sm italic text-content-secondary">
                {t("explanation.disclaimer")}
              </p>
            </div>
          ) : null}
        </div>
      </div>
    </section>
  );
}
