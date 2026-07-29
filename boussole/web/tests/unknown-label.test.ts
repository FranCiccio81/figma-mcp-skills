/**
 * Libellés des critères non évalués — ne jamais accuser à tort.
 *
 * Trois raisons possibles mettent en cause des choses différentes : l'offre
 * (`job_not_provided`), le profil (`profile_not_provided`), et **nous**
 * (`unavailable` — un critère que l'outil ne sait pas évaluer de façon
 * fiable, cas de `title_similarity` tant que les seuils ne sont pas calibrés
 * pour le modèle de vecteurs employé).
 *
 * Le piège corrigé : le repli par défaut renvoyait vers « information
 * extraite de l'offre incertaine ». Une annonce sans le moindre défaut se
 * serait vue reprocher une extraction douteuse, et un utilisateur aurait pu
 * aller vérifier l'annonce d'origine pour rien.
 */
import { describe, expect, it } from "vitest";
import { unknownLabel } from "@/components/match/match-panel";
import type { UnknownDimension } from "@/lib/api/types";

/** Traducteur factice : rend la clé et ses paramètres, pas de i18n réelle. */
const t = ((cle: string, params?: Record<string, unknown>) =>
  params ? `${cle}:${JSON.stringify(params)}` : cle) as never;

function inconnue(overrides: Partial<UnknownDimension> = {}): UnknownDimension {
  return {
    dimension: "title_similarity",
    reason: "unavailable",
    label: "",
    ...overrides,
  } as UnknownDimension;
}

describe("libellé d'un critère non évalué", () => {
  it("IGNORE le libellé de l'API quand le code lui suffit", () => {
    // Ce test disait l'inverse — « reprend le libellé de l'API quand il
    // existe » — et il encodait le défaut. L'API rend ses libellés en
    // français sans condition : la reprendre télégraphiait du français dans
    // une interface anglaise. Voir le bloc « la langue de l'interface
    // l'emporte » plus bas.
    const libelle = unknownLabel(t, inconnue({ label: "Métier : comparaison indisponible" }));
    expect(libelle).toContain("unknown.unavailableFallback");
  });

  it("n'accuse ni le profil ni l'offre quand la limite est la nôtre", () => {
    const libelle = unknownLabel(t, inconnue({ reason: "unavailable" }));
    expect(libelle).toContain("unknown.unavailableFallback");
    // Le piège : ces deux replis mettraient en cause des données saines.
    expect(libelle).not.toContain("uncertainFallback");
    expect(libelle).not.toContain("profileFallback");
  });

  it("renvoie vers le profil quand c'est le profil qui manque", () => {
    const libelle = unknownLabel(t, inconnue({ reason: "profile_not_provided" }));
    expect(libelle).toContain("unknown.profileFallback");
  });

  it("signale une extraction douteuse quand c'est le cas", () => {
    const libelle = unknownLabel(t, inconnue({ reason: "low_extraction_confidence" }));
    expect(libelle).toContain("unknown.uncertainFallback");
  });

  it("retombe sur l'offre pour une donnée absente de l'annonce", () => {
    const libelle = unknownLabel(t, inconnue({ reason: "job_not_provided" }));
    expect(libelle).toContain("unknown.jobFallback");
  });
});

/**
 * La langue de l'interface l'emporte sur celle de l'API.
 *
 * L'API rend ses libellés **en français, sans condition** : elle ne lit jamais
 * `Accept-Language`, alors que le proxy BFF le lui transmet. La précédence
 * était `if (unknown.label) return unknown.label`, donc un utilisateur en
 * anglais lisait « Similarité du métier : comparaison indisponible (outil non
 * calibré) » sur l'écran même censé lui expliquer son score — et les
 * traductions `unknown.*Fallback`, présentes et correctes en `en`, étaient du
 * code mort.
 */
describe("la langue de l'interface l'emporte sur celle de l'API", () => {
  it("ignore le libellé de l'API quand le code est connu", () => {
    const rendu = unknownLabel(
      t,
      inconnue({ label: "Similarité du métier : comparaison indisponible" }),
    );
    expect(rendu).toContain("unknown.unavailableFallback");
    expect(rendu).not.toContain("Similarité du métier");
  });

  it("garde le libellé de l'API sur une raison qu'il ne connaît pas", () => {
    // Compatibilité ascendante : mieux vaut un libellé dans la mauvaise
    // langue qu'une ligne vide si l'API introduit un nouveau code.
    const rendu = unknownLabel(
      t,
      inconnue({ reason: "raison_future" as never, label: "Libellé de l'API" }),
    );
    expect(rendu).toBe("Libellé de l'API");
  });

  it("garde le libellé de l'API sur une dimension qu'il ne connaît pas", () => {
    const rendu = unknownLabel(
      t,
      inconnue({ dimension: "dimension_future", label: "Libellé de l'API" }),
    );
    expect(rendu).toBe("Libellé de l'API");
  });
});

describe("les critères bloquants sont traduits par l'interface", () => {
  it("traduit les six codes de la spécification", async () => {
    const { blockingLabel } = await import("@/components/match/match-panel");
    const codes = [
      "location_incompatible",
      "remote_required",
      "language_missing",
      "contract_excluded",
      "salary_below_minimum",
      "sector_excluded",
    ];
    for (const code of codes) {
      const rendu = blockingLabel(t, {
        code,
        label: "Langue requise absente ou >= 2 niveaux CECRL en dessous",
      } as never);
      expect(rendu).toBe(`blocking.codes.${code}`);
      expect(rendu).not.toContain("CECRL");
    }
  });

  it("retombe sur le libellé de l'API pour un code inconnu", () => {
    return import("@/components/match/match-panel").then(({ blockingLabel }) => {
      expect(
        blockingLabel(t, { code: "code_futur", label: "Libellé de l'API" } as never),
      ).toBe("Libellé de l'API");
    });
  });
});
