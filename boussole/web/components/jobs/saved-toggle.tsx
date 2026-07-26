"use client";

import { Bookmark, EyeOff } from "lucide-react";
import { useTranslations } from "next-intl";
import { Button } from "@/components/ui/button";
import type { SavedState } from "@/lib/api/types";

export interface SavedToggleProps {
  /** État courant de l'offre (`null` = ni sauvegardée ni masquée). */
  savedState: SavedState | null;
  /** Titre de l'offre — injecté dans les libellés d'accessibilité. */
  jobTitle: string;
  /**
   * Bascule demandée par l'utilisateur : `state` est le nouvel état voulu
   * (`null` = retirer la sauvegarde / le masquage — `DELETE saved-state`).
   */
  onChange: (state: SavedState | null) => void;
  /** Désactive les deux boutons pendant une mutation en vol. */
  disabled?: boolean;
}

/**
 * Paire d'actions Sauvegarder / Masquer d'une offre (SCR-20/21, Flux 3 §5).
 * Boutons à bascule accessibles : `aria-pressed` reflète l'état courant,
 * libellé complet incluant le titre de l'offre, cibles ≥ 44 px (Button `md`),
 * icône + texte (jamais l'icône seule). Aucune couleur en dur.
 */
export function SavedToggle({ savedState, jobTitle, onChange, disabled }: SavedToggleProps) {
  const t = useTranslations("jobs.actions");
  const isSaved = savedState === "saved";
  const isHidden = savedState === "hidden";

  return (
    <div className="flex flex-wrap gap-2">
      <Button
        variant="secondary"
        aria-pressed={isSaved}
        aria-label={t(isSaved ? "unsaveAria" : "saveAria", { title: jobTitle })}
        disabled={disabled}
        onClick={() => onChange(isSaved ? null : "saved")}
        className={isSaved ? "border-action-primary text-action-primary" : undefined}
      >
        <Bookmark
          aria-hidden="true"
          className="h-4 w-4"
          fill={isSaved ? "currentColor" : "none"}
        />
        {t(isSaved ? "saved" : "save")}
      </Button>
      <Button
        variant="ghost"
        aria-pressed={isHidden}
        aria-label={t(isHidden ? "unhideAria" : "hideAria", { title: jobTitle })}
        disabled={disabled}
        onClick={() => onChange(isHidden ? null : "hidden")}
      >
        <EyeOff aria-hidden="true" className="h-4 w-4" />
        {t(isHidden ? "hidden" : "hide")}
      </Button>
    </div>
  );
}
