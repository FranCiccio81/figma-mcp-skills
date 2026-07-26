import { FileSearch } from "lucide-react";
import { useTranslations } from "next-intl";
import type { Provenance } from "@/lib/api/types";

export interface ProvenanceBadgeProps {
  provenance?: Provenance;
}

/**
 * Badge de provenance d'un champ de profil (SCR-06/SCR-50, D05) : affiché
 * uniquement pour `cv_extraction` (« Extrait du CV — confiance {p} % », texte
 * complet M3-d en infobulle/aria) ; rien pour `user_confirmed` / `user_input`.
 * Toujours un texte, jamais une pastille de couleur seule (Flux 1 a11y).
 */
export function ProvenanceBadge({ provenance }: ProvenanceBadgeProps) {
  const t = useTranslations("profile.provenance");
  if (!provenance || provenance.source !== "cv_extraction") return null;

  const percent = Math.round((provenance.confidence ?? 0) * 100);
  const help = t("cvHelp", { percent });

  return (
    <span
      title={help}
      className="inline-flex items-center gap-1 rounded-md bg-feedback-warning-surface px-2 py-0.5 text-xs font-medium text-feedback-warning"
    >
      <FileSearch aria-hidden="true" className="h-3.5 w-3.5 shrink-0" />
      <span aria-hidden="true">{t("cvBadge", { percent })}</span>
      {/* Texte M3-d complet pour les lecteurs d'écran (le `title` ne suffit pas). */}
      <span className="sr-only">{help}</span>
    </span>
  );
}
