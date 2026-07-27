/**
 * Formate une date ISO 8601 pour l'affichage (dates de publication,
 * d'expiration…). Retourne `null` si la chaîne est absente ou invalide —
 * l'appelant décide alors d'omettre l'information (jamais d'estimation, M3-c).
 */
export function formatDate(iso: string | null | undefined, locale: string): string | null {
  if (!iso) return null;
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return null;
  return new Intl.DateTimeFormat(locale, { dateStyle: "long" }).format(date);
}

/**
 * Formate une date ISO 8601 avec l'heure (frise des événements de candidature,
 * SCR-41). Retourne `null` si absente ou invalide — même contrat que
 * {@link formatDate}.
 */
export function formatDateTime(iso: string | null | undefined, locale: string): string | null {
  if (!iso) return null;
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return null;
  return new Intl.DateTimeFormat(locale, { dateStyle: "long", timeStyle: "short" }).format(date);
}
