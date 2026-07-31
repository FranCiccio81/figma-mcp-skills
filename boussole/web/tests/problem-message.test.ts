/**
 * Un message d'erreur parle la langue de l'utilisateur.
 *
 * Défaut trouvé en revue avant déploiement. Cinq points d'appel affichaient
 * `error.detail` — la prose composée par l'API, qui est en français — et la
 * préféraient systématiquement à leur propre traduction :
 *
 *     setServerError(error.detail ?? t("errors.unexpected"));
 *
 * Le repli traduit ne servait donc que lorsque l'API se taisait. Un
 * utilisateur anglophone lisait « Validez votre profil avant de générer un
 * contenu. » L'interface est bilingue, la négociation de langue fonctionne,
 * les 578 clés sont traduites — et c'est par le message d'erreur, au moment
 * précis où il faut être compris, que le français ressortait.
 *
 * La règle : on traduit le CODE (`type` = `.../errors/<code>`), jamais la
 * prose. Le code est un identifiant stable du contrat d'API ; le `detail`
 * est une phrase écrite dans une langue donnée.
 */
import { describe, expect, it } from "vitest";
import { ApiProblem } from "@/lib/api/client";
import { problemCode, problemMessage } from "@/lib/api/problem-message";
import en from "@/messages/en.json";
import fr from "@/messages/fr.json";

/** Traducteur minimal sur un dictionnaire — même contrat que next-intl. */
function traducteur(messages: Record<string, string | Record<string, string>>) {
  const resoudre = (cle: string): string | undefined =>
    cle.split(".").reduce<unknown>(
      (noeud, part) =>
        noeud && typeof noeud === "object"
          ? (noeud as Record<string, unknown>)[part]
          : undefined,
      messages,
    ) as string | undefined;
  const t = ((cle: string) => resoudre(cle) ?? `!${cle}`) as never as ReturnType<
    typeof import("next-intl").useTranslations
  >;
  (t as unknown as { has: (c: string) => boolean }).has = (cle) =>
    resoudre(cle) !== undefined;
  return t;
}

const tFr = traducteur(fr.errors);
const tEn = traducteur(en.errors);

function probleme(code: string, detail = "Texte français de l'API."): ApiProblem {
  return new ApiProblem({
    type: `https://api.boussole.eu/errors/${code}`,
    title: "Erreur",
    status: 409,
    detail,
  });
}

describe("problemMessage", () => {
  it("ne rend jamais la prose française à un utilisateur anglophone", () => {
    const message = problemMessage(probleme("profile_not_validated"), tEn);

    expect(message).toBe(en.errors.byCode.profile_not_validated);
    expect(message).not.toContain("Validez");
  });

  it("rend bien le français en français", () => {
    expect(problemMessage(probleme("profile_not_validated"), tFr)).toBe(
      fr.errors.byCode.profile_not_validated,
    );
  });

  it("retombe sur un message générique TRADUIT pour un code inconnu", () => {
    /* Mieux vaut être vague dans la bonne langue que précis dans une autre. */
    const message = problemMessage(probleme("code_invente_demain"), tEn);
    expect(message).toBe(en.errors.generic);
  });

  it("retombe sur le générique quand l'erreur n'est pas un problème d'API", () => {
    expect(problemMessage(new Error("boom"), tEn)).toBe(en.errors.generic);
  });

  it("ignore le detail même quand le code est inconnu", () => {
    const message = problemMessage(
      probleme("inconnu", "Le corps de la requête dépasse la limite de 12 Mo."),
      tEn,
    );
    expect(message).not.toContain("dépasse");
  });
});

describe("problemCode", () => {
  it("extrait le dernier segment du type", () => {
    expect(problemCode(probleme("rate_limited"))).toBe("rate_limited");
  });

  it("rend null sur un type absent ou inattendu", () => {
    const sansType = new ApiProblem({ title: "x", status: 500 });
    expect(problemCode(sansType)).toBeNull();
    expect(
      problemCode(
        new ApiProblem({ type: "https://exemple.fr/Erreur-42", title: "x", status: 500 }),
      ),
    ).toBeNull();
  });
});

describe("catalogue d'erreurs", () => {
  it("couvre les mêmes codes en français et en anglais", () => {
    expect(Object.keys(en.errors.byCode).sort()).toEqual(
      Object.keys(fr.errors.byCode).sort(),
    );
  });

  it("ne laisse aucun message anglais identique au français", () => {
    /* Une clé recopiée sans traduction est la façon la plus discrète de
       réintroduire exactement ce défaut. */
    const identiques = Object.keys(fr.errors.byCode).filter(
      (code) =>
        fr.errors.byCode[code as keyof typeof fr.errors.byCode] ===
        en.errors.byCode[code as keyof typeof en.errors.byCode],
    );
    expect(identiques).toEqual([]);
  });

  it("a un message générique dans les deux langues", () => {
    expect(fr.errors.generic).toBeTruthy();
    expect(en.errors.generic).toBeTruthy();
    expect(fr.errors.generic).not.toBe(en.errors.generic);
  });
});
