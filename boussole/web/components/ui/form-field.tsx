import type { ReactNode } from "react";

export interface FormFieldProps {
  /** Id du contrôle enfant — sert à lier label, description et erreur. */
  id: string;
  label: string;
  /** Aide affichée sous le label, annoncée via `aria-describedby`. */
  description?: string;
  /** Message d'erreur — rendu dans un conteneur `role="alert"` (annonce SR). */
  error?: string;
  required?: boolean;
  children: ReactNode;
}

/**
 * Ids des éléments liés à un champ, à passer au contrôle enfant :
 * `aria-describedby={fieldDescribedBy(id, { description: true, error: !!error })}`.
 */
export function fieldDescribedBy(
  id: string,
  parts: { description?: boolean; error?: boolean },
): string | undefined {
  const ids: string[] = [];
  if (parts.description) ids.push(`${id}-description`);
  if (parts.error) ids.push(`${id}-error`);
  return ids.length > 0 ? ids.join(" ") : undefined;
}

/**
 * Enveloppe accessible d'un champ de formulaire : label lié (`htmlFor`),
 * description et erreur référencées par id (cf. {@link fieldDescribedBy}).
 * Le contrôle enfant garde la responsabilité d'`aria-invalid`.
 */
export function FormField({ id, label, description, error, required, children }: FormFieldProps) {
  return (
    <div className="space-y-1.5">
      <label htmlFor={id} className="block text-sm font-medium text-content">
        {label}
        {required ? <span aria-hidden="true"> *</span> : null}
      </label>
      {description ? (
        <p id={`${id}-description`} className="text-sm text-content-secondary">
          {description}
        </p>
      ) : null}
      {children}
      {error ? (
        <p id={`${id}-error`} role="alert" className="text-sm font-medium text-feedback-error">
          {error}
        </p>
      ) : null}
    </div>
  );
}
