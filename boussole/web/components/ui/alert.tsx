import clsx from "clsx";
import { CircleAlert, CircleCheck, Info, TriangleAlert } from "lucide-react";
import { forwardRef, type HTMLAttributes } from "react";

type AlertVariant = "info" | "success" | "warning" | "error";

export interface AlertProps extends HTMLAttributes<HTMLDivElement> {
  /** Variante sémantique. `error`/`warning` → `role="alert"`, sinon `role="status"`. */
  variant?: AlertVariant;
  /** Titre optionnel en gras au-dessus du contenu. */
  title?: string;
}

const variantStyles: Record<AlertVariant, string> = {
  info: "bg-feedback-info-surface text-feedback-info",
  success: "bg-feedback-success-surface text-feedback-success",
  warning: "bg-feedback-warning-surface text-feedback-warning",
  error: "bg-feedback-error-surface text-feedback-error",
};

const variantIcons = {
  info: Info,
  success: CircleCheck,
  warning: TriangleAlert,
  error: CircleAlert,
} as const;

/**
 * Bandeau de feedback accessible : icône + texte (jamais la couleur seule),
 * rôle ARIA adapté à la sévérité, focalisable via `tabIndex={-1}` pour la
 * gestion de focus après une erreur serveur.
 */
export const Alert = forwardRef<HTMLDivElement, AlertProps>(function Alert(
  { variant = "info", title, className, children, ...props },
  ref,
) {
  const Icon = variantIcons[variant];
  const role = variant === "error" || variant === "warning" ? "alert" : "status";

  return (
    <div
      ref={ref}
      role={role}
      className={clsx(
        "flex items-start gap-3 rounded-md p-4 text-sm",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus",
        variantStyles[variant],
        className,
      )}
      {...props}
    >
      <Icon aria-hidden="true" className="mt-0.5 h-5 w-5 shrink-0" />
      <div className="space-y-1">
        {title ? <p className="font-semibold">{title}</p> : null}
        <div>{children}</div>
      </div>
    </div>
  );
});
