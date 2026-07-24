import { useTranslations } from "next-intl";
import type { JobMatchSummary } from "@/lib/api/types";

export interface MatchBadgeProps {
  /** Résumé de matching de la carte — `null` = rien n'est affiché (jamais de faux score). */
  match: JobMatchSummary | null;
}

/**
 * Double affichage compact score/confiance d'une carte d'offre (SCR-20/SCR-10,
 * microcopie M1-a — les deux valeurs toujours côte à côte, jamais fusionnées).
 * `low_data` : score grisé mais lisible (`text-content-secondary`, jamais
 * `disabled`) + libellé « Données insuffisantes » ; `has_blocking` : badge
 * « ⛔ Critère bloquant » (M2-a) — icône + texte, jamais la couleur seule.
 */
export function MatchBadge({ match }: MatchBadgeProps) {
  const t = useTranslations("match.card");
  if (!match) return null;

  return (
    <p className="flex flex-wrap items-center gap-2 text-sm">
      <span
        className={
          match.low_data ? "font-medium text-content-secondary" : "font-medium text-content"
        }
      >
        {t("summary", { score: match.score, confidence: match.confidence })}
      </span>
      {match.low_data ? (
        <span className="rounded-md border border-border bg-surface-muted px-2 py-0.5 text-xs font-medium text-content-secondary">
          {t("lowData")}
        </span>
      ) : null}
      {match.has_blocking ? (
        <span className="rounded-md bg-feedback-error-surface px-2 py-0.5 text-xs font-medium text-feedback-error">
          {t("blockingBadge")}
        </span>
      ) : null}
    </p>
  );
}
