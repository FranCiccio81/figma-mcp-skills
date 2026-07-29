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
  it("reprend le libellé de l'API quand il existe", () => {
    const libelle = unknownLabel(t, inconnue({ label: "Métier : comparaison indisponible" }));
    expect(libelle).toBe("Métier : comparaison indisponible");
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
