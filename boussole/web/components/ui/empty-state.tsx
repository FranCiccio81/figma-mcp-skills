import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

export interface EmptyStateProps {
  /** Icône lucide décorative (aria-hidden). */
  icon?: LucideIcon;
  title: string;
  description?: string;
  /** Contenu additionnel (note de jalon, CTA…), rendu sous la description. */
  children?: ReactNode;
}

/**
 * État vide réutilisable (convention 03 §2 : chaque écran a un état Vide
 * explicite) — icône décorative, titre, description et zone d'action.
 */
export function EmptyState({ icon: Icon, title, description, children }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 rounded-lg border border-dashed border-border bg-surface-muted px-6 py-16 text-center">
      {Icon ? <Icon aria-hidden="true" className="h-10 w-10 text-content-secondary" /> : null}
      <h2 className="text-lg font-semibold text-content">{title}</h2>
      {description ? (
        <p className="max-w-md text-sm text-content-secondary">{description}</p>
      ) : null}
      {children}
    </div>
  );
}
