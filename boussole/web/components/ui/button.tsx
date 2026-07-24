import clsx from "clsx";
import { forwardRef, type ButtonHTMLAttributes } from "react";

type ButtonVariant = "primary" | "secondary" | "ghost" | "destructive";
type ButtonSize = "md" | "lg";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  /** Variante visuelle — tokens sémantiques uniquement. @default "primary" */
  variant?: ButtonVariant;
  /** Taille — `md` garantit déjà la cible tactile de 44 px. @default "md" */
  size?: ButtonSize;
}

const variantStyles: Record<ButtonVariant, string> = {
  primary: "bg-action-primary text-content-on-action hover:bg-action-primary-hover",
  secondary: "border border-border bg-surface text-content hover:bg-surface-muted",
  ghost: "text-content-secondary hover:bg-surface-muted hover:text-content",
  destructive: "bg-feedback-error text-content-on-action hover:opacity-90",
};

const sizeStyles: Record<ButtonSize, string> = {
  md: "min-h-11 px-4 text-sm",
  lg: "min-h-12 px-6 text-base",
};

/**
 * Bouton accessible (WCAG 2.1 AA) : cible ≥ 44 px, focus visible (ring 3:1),
 * contrastes garantis par les tokens Bridge. Aucune couleur en dur.
 */
export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = "primary", size = "md", type = "button", className, ...props },
  ref,
) {
  return (
    <button
      ref={ref}
      type={type}
      className={clsx(
        "inline-flex items-center justify-center gap-2 rounded-md font-medium transition-colors",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus focus-visible:ring-offset-2 focus-visible:ring-offset-surface",
        "disabled:pointer-events-none disabled:opacity-50",
        variantStyles[variant],
        sizeStyles[size],
        className,
      )}
      {...props}
    />
  );
});
