"use client";

import clsx from "clsx";
import { CircleCheck, CircleHelp, TriangleAlert } from "lucide-react";
import { useTranslations } from "next-intl";
import type { AnchoringCheck, GenerationStatus } from "@/lib/api/types";

/** Styles par statut de génération — icône implicite via libellé (jamais couleur seule). */
const STATUS_STYLES: Record<GenerationStatus, string> = {
  pending: "bg-feedback-info-surface text-feedback-info",
  draft: "bg-feedback-warning-surface text-feedback-warning",
  validated: "bg-feedback-success-surface text-feedback-success",
  exported: "bg-feedback-success-surface text-feedback-success",
  failed: "bg-feedback-error-surface text-feedback-error",
};

/** Badge de statut d'un document généré (SCR-31, bibliothèque « Mes documents »). */
export function GenerationStatusBadge({ status }: { status: GenerationStatus }) {
  const t = useTranslations("generation.status");
  return (
    <span
      className={clsx(
        "inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium",
        STATUS_STYLES[status],
      )}
    >
      {t(status)}
    </span>
  );
}

export interface AnchoringBadgeProps {
  /** `null` = contrôle non disponible (édition manuelle, ou génération en cours). */
  check: AnchoringCheck | null;
}

/**
 * Badge du contrôle d'ancrage (SCR-31) : `passed` (toutes les affirmations
 * reliées au profil), `failed` (claims non ancrées — export bloqué), `null`
 * (document édité manuellement : contrôle non re-vérifié). Icône + libellé,
 * jamais la couleur seule (04 §conventions).
 */
export function AnchoringBadge({ check }: AnchoringBadgeProps) {
  const t = useTranslations("generation.anchoring");

  if (check === null) {
    return (
      <span className="inline-flex items-center gap-1 rounded-md bg-surface-muted px-2 py-0.5 text-xs font-medium text-content-secondary">
        <CircleHelp aria-hidden="true" className="h-3.5 w-3.5" />
        {t("badgeManual")}
      </span>
    );
  }
  if (check.status === "passed") {
    return (
      <span className="inline-flex items-center gap-1 rounded-md bg-feedback-success-surface px-2 py-0.5 text-xs font-medium text-feedback-success">
        <CircleCheck aria-hidden="true" className="h-3.5 w-3.5" />
        {t("badgePassed")}
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 rounded-md bg-feedback-error-surface px-2 py-0.5 text-xs font-medium text-feedback-error">
      <TriangleAlert aria-hidden="true" className="h-3.5 w-3.5" />
      {t("badgeFailed")}
    </span>
  );
}
