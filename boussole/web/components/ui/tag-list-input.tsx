"use client";

import { useId, useState } from "react";
import { useTranslations } from "next-intl";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export interface TagListInputProps {
  /** Libellé du champ de saisie. */
  label: string;
  /** Aide affichée sous le libellé. */
  description?: string;
  /** Liste courante (contrôlée). */
  value: string[];
  onChange: (next: string[]) => void;
  /** Intitulé accessible du bouton de suppression d'un élément. */
  removeAriaLabel: (item: string) => string;
}

/**
 * Saisie de liste en tags (métiers cibles, secteurs, mots-clés… — SCR-07) :
 * champ texte + bouton « Ajouter » (Entrée équivaut au bouton), puces
 * supprimables au clavier (cibles ≥ 44 px), ajout/suppression annoncés via
 * une région `aria-live` (04 Flux 2 a11y). Doublons ignorés (insensible à la
 * casse), jamais de valeur vide.
 */
export function TagListInput({
  label,
  description,
  value,
  onChange,
  removeAriaLabel,
}: TagListInputProps) {
  const t = useTranslations("preferences.tags");
  const baseId = useId();
  const [draft, setDraft] = useState("");
  const [announcement, setAnnouncement] = useState("");

  const add = () => {
    const item = draft.trim();
    if (!item) return;
    if (value.some((existing) => existing.toLowerCase() === item.toLowerCase())) {
      setDraft("");
      return;
    }
    onChange([...value, item]);
    setAnnouncement(t("added", { label: item }));
    setDraft("");
  };

  const remove = (item: string) => {
    onChange(value.filter((entry) => entry !== item));
    setAnnouncement(t("removed", { label: item }));
  };

  const inputId = `${baseId}-input`;
  const descriptionId = description ? `${baseId}-description` : undefined;

  return (
    <div className="space-y-2">
      <label htmlFor={inputId} className="block text-sm font-medium text-content">
        {label}
      </label>
      {description ? (
        <p id={descriptionId} className="text-sm text-content-secondary">
          {description}
        </p>
      ) : null}
      <div className="flex flex-wrap items-center gap-3">
        <Input
          id={inputId}
          value={draft}
          aria-describedby={descriptionId}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              event.preventDefault();
              add();
            }
          }}
          className="min-w-40 flex-1"
        />
        <Button variant="secondary" onClick={add}>
          {t("add")}
        </Button>
      </div>
      {value.length > 0 ? (
        <ul className="flex flex-wrap gap-2">
          {value.map((item) => (
            <li
              key={item}
              className="flex items-center gap-1 rounded-md border border-border bg-surface-muted px-2 py-1 text-sm text-content"
            >
              <span>{item}</span>
              <button
                type="button"
                aria-label={removeAriaLabel(item)}
                onClick={() => remove(item)}
                className="inline-flex h-11 min-w-11 items-center justify-center rounded-sm px-1 font-semibold text-content-secondary hover:text-feedback-error focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
              >
                <span aria-hidden="true">×</span>
              </button>
            </li>
          ))}
        </ul>
      ) : null}
      <p role="status" aria-live="polite" className="sr-only">
        {announcement}
      </p>
    </div>
  );
}
