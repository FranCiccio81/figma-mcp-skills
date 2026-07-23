import clsx from "clsx";
import { forwardRef, type InputHTMLAttributes } from "react";

export type InputProps = InputHTMLAttributes<HTMLInputElement>;

/**
 * Champ de saisie stylé par tokens Bridge : hauteur 44 px (cible tactile),
 * anneau de focus dédié (`--shadow-input-focus`), état invalide via
 * `aria-invalid` (posé par le formulaire, cf. FormField).
 */
export const Input = forwardRef<HTMLInputElement, InputProps>(function Input(
  { className, ...props },
  ref,
) {
  return (
    <input
      ref={ref}
      className={clsx(
        "h-11 w-full rounded-md border border-border bg-surface px-3 text-sm text-content",
        "placeholder:text-content-secondary",
        "focus:border-action-primary focus:shadow-input-focus focus:outline-none",
        "disabled:cursor-not-allowed disabled:opacity-50",
        "aria-[invalid=true]:border-feedback-error",
        className,
      )}
      {...props}
    />
  );
});
