/**
 * L'interface anglaise doit être ATTEIGNABLE, pas seulement traduite.
 *
 * Défaut trouvé en revue finale : `i18n.ts` rendait `defaultLocale` sans
 * condition — une ligne, `const locale: Locale = defaultLocale`. Ni
 * `Accept-Language`, ni le champ `locale` de `GET /me`, ni aucun sélecteur
 * ne pouvait atteindre `en.json`. Constaté sur le HTML rendu, avec un
 * `Accept-Language: en-US` ET un compte dont `/me` répond `"locale":"en"` :
 *
 *     <html lang="fr">
 *     /inscription      → « Inscription », « Créer mon compte »
 *     /tableau-de-bord  → « Meilleures correspondances », « Importer mon CV »
 *     …aucun mot anglais nulle part
 *
 * Les 578 clés de `en.json` étaient du code mort — et `npm run i18n:check`
 * répondait « Parité i18n OK ». C'est ce qui rend ce contrôle trompeur : il
 * vérifie que les deux fichiers portent les mêmes clés, jamais qu'on puisse
 * en lire un second. Un test de parité ne remplace pas un test d'accès.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";

const cookieStore = { valeur: undefined as string | undefined };
const headerStore = { acceptLanguage: "" };

vi.mock("next/headers", () => ({
  cookies: async () => ({
    get: (nom: string) =>
      nom === "boussole_locale" && cookieStore.valeur
        ? { value: cookieStore.valeur }
        : undefined,
  }),
  headers: async () => ({
    get: (nom: string) =>
      nom === "accept-language" ? headerStore.acceptLanguage : null,
  }),
}));

const { resolveLocale } = await import("@/i18n");

beforeEach(() => {
  cookieStore.valeur = undefined;
  headerStore.acceptLanguage = "";
});

describe("négociation de la langue d'interface", () => {
  it("rend l'anglais sur un Accept-Language anglais", async () => {
    headerStore.acceptLanguage = "en-US,en;q=0.9";
    expect(await resolveLocale()).toBe("en");
  });

  it("respecte l'ordre de préférence du navigateur", async () => {
    headerStore.acceptLanguage = "de-DE,de;q=0.9,en;q=0.8,fr;q=0.7";
    expect(await resolveLocale()).toBe("en");
    headerStore.acceptLanguage = "de-DE,fr;q=0.9,en;q=0.8";
    expect(await resolveLocale()).toBe("fr");
  });

  it("laisse le choix explicite l'emporter sur le navigateur", async () => {
    cookieStore.valeur = "en";
    headerStore.acceptLanguage = "fr-FR,fr;q=0.9";
    expect(await resolveLocale()).toBe("en");
  });

  it("retombe sur le français sans indication", async () => {
    expect(await resolveLocale()).toBe("fr");
  });

  it("retombe sur le français sur une langue non gérée", async () => {
    // Une langue qu'on ne parle pas doit donner une page lisible, pas une
    // erreur ni une page vide.
    headerStore.acceptLanguage = "ja-JP,ja;q=0.9";
    expect(await resolveLocale()).toBe("fr");
    cookieStore.valeur = "klingon";
    expect(await resolveLocale()).toBe("fr");
  });
});

describe("les deux catalogues sont réellement chargeables", () => {
  it("charge fr.json et en.json, non vides", async () => {
    const fr = (await import("@/messages/fr.json")).default;
    const en = (await import("@/messages/en.json")).default;
    expect(Object.keys(fr).length).toBeGreaterThan(5);
    expect(Object.keys(en).length).toBe(Object.keys(fr).length);
  });

  it("les deux catalogues disent des choses DIFFÉRENTES", async () => {
    // Contrôle qui aurait manqué de toute façon : si `en.json` était une
    // copie du français, la parité passerait et l'anglais serait faux.
    const fr = (await import("@/messages/fr.json")).default;
    const en = (await import("@/messages/en.json")).default;
    expect(JSON.stringify(en)).not.toBe(JSON.stringify(fr));
  });
});
