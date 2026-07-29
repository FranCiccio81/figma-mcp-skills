import { cookies, headers } from "next/headers";
import { getRequestConfig } from "next-intl/server";

export const locales = ["fr", "en"] as const;
export type Locale = (typeof locales)[number];
export const defaultLocale: Locale = "fr";

/** Cookie de préférence de langue, posé par le sélecteur d'interface. */
export const LOCALE_COOKIE = "boussole_locale";

function isLocale(value: string | undefined | null): value is Locale {
  return value === "fr" || value === "en";
}

/**
 * Langue de l'interface, négociée : cookie de préférence, puis `Accept-Language`.
 *
 * **Ce que ça corrige.** Cette fonction rendait `defaultLocale` sans condition
 * — une ligne, `const locale: Locale = defaultLocale`. Ni `Accept-Language`,
 * ni le champ `locale` de `GET /me`, ni aucun sélecteur ne pouvait atteindre
 * `en.json` : **l'interface anglaise n'existait pas**. Les 578 clés anglaises
 * étaient du code mort, et `npm run i18n:check` répondait « Parité i18n OK » —
 * un signal vert sur une fonctionnalité inatteignable.
 *
 * C'est précisément ce qui rendait ce contrôle trompeur : il vérifie que les
 * deux fichiers portent les mêmes clés, jamais qu'on puisse en lire un second.
 *
 * Le cookie prime sur l'en-tête : un choix explicite l'emporte sur une
 * préférence de navigateur. Toute autre valeur retombe sur le français plutôt
 * que d'échouer — une langue non gérée doit donner une page lisible.
 */
export async function resolveLocale(): Promise<Locale> {
  const choix = (await cookies()).get(LOCALE_COOKIE)?.value;
  if (isLocale(choix)) return choix;

  // `Accept-Language: en-US,en;q=0.9,fr;q=0.8` → première langue reconnue,
  // dans l'ordre de préférence déclaré par le navigateur.
  const entete = (await headers()).get("accept-language") ?? "";
  for (const morceau of entete.split(",")) {
    const balise = morceau.split(";")[0]?.trim().toLowerCase() ?? "";
    const base = balise.split("-")[0];
    if (isLocale(base)) return base;
  }
  return defaultLocale;
}

export default getRequestConfig(async () => {
  const locale = await resolveLocale();

  return {
    locale,
    messages: (await import(`./messages/${locale}.json`)).default,
  };
});
