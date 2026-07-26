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
