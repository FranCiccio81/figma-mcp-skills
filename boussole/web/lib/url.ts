/**
 * Garde-fous d'URL pour les liens d'origine EXTERNE (sources d'offres D13,
 * `external_url` d'une candidature saisie à la main).
 */

/**
 * N'autorise que `http:` / `https:` — une source compromise ou une saisie
 * utilisateur ne doit pas pouvoir injecter `javascript:` / `data:` dans un
 * `href`. Retourne l'URL telle quelle si le schéma est autorisé, `null`
 * sinon : l'appelant affiche alors le texte SANS lien (jamais d'href muet).
 */
export function safeHttpUrl(url: string | null | undefined): string | null {
  if (!url) return null;
  try {
    const parsed = new URL(url);
    return parsed.protocol === "http:" || parsed.protocol === "https:" ? url : null;
  } catch {
    // URL relative ou syntaxiquement invalide — jamais transformée en lien.
    return null;
  }
}
