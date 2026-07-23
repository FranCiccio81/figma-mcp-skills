import { getRequestConfig } from "next-intl/server";

export const locales = ["fr", "en"] as const;
export type Locale = (typeof locales)[number];
export const defaultLocale: Locale = "fr";

/**
 * Configuration next-intl (D15) — UI en français au lancement, clés déjà
 * externalisées pour l'anglais. Pas de routage par locale au MVP : la locale
 * viendra de `GET /me` (champ `locale`) une fois le sélecteur livré. 🟡
 */
export default getRequestConfig(async () => {
  const locale: Locale = defaultLocale;

  return {
    locale,
    messages: (await import(`./messages/${locale}.json`)).default,
  };
});
