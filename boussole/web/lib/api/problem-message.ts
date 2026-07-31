"use client";

import { useTranslations } from "next-intl";
import { type ApiProblem, isApiProblem } from "@/lib/api/client";

/**
 * Message d'erreur **dans la langue de l'utilisateur**.
 *
 * ## Ce que ça corrige
 *
 * Cinq points d'appel affichaient `error.detail` — la prose composée par
 * l'API, qui est en français — directement à l'écran, et la préféraient
 * systématiquement à leur propre traduction :
 *
 * ```ts
 * setServerError(error.detail ?? t("errors.unexpected"));
 * ```
 *
 * Le repli traduit ne servait donc que lorsque l'API se taisait. Un
 * utilisateur anglophone lisait « Validez votre profil avant de générer un
 * contenu. » ou « Le corps de la requête dépasse la limite de 12 Mo. »
 *
 * L'interface est bilingue, la négociation de langue fonctionne, les 578
 * clés sont traduites — et c'est par le message d'erreur, précisément au
 * moment où l'on a le plus besoin d'être compris, que le français
 * ressortait.
 *
 * ## La règle
 *
 * On traduit le **code** (`type` = `.../errors/<code>`), jamais la prose.
 * Le code est un identifiant stable du contrat d'API ; le `detail` est une
 * phrase écrite pour un humain, dans une langue donnée. Traduire l'un est
 * possible, l'autre non.
 *
 * Un code inconnu du catalogue retombe sur un message générique traduit
 * plutôt que sur le français : mieux vaut être vague dans la bonne langue
 * que précis dans une autre. `errors.byCode` couvre les 29 codes que l'API
 * sait produire, et le test de parité les vérifie dans les deux langues.
 *
 * ## Limite connue, pas masquée
 *
 * Les erreurs de CHAMP (`problem.errors[].message`) restent composées par
 * l'API et donc en français. Elles ne passent pas par ici : elles
 * s'affichent sous le champ concerné, où le libellé traduit du champ porte
 * déjà l'essentiel du sens. Les traduire demanderait que l'API rende un code
 * par champ — un changement de contrat qui n'a pas sa place dans un
 * correctif.
 */
export function problemMessage(
  error: unknown,
  t: ReturnType<typeof useTranslations>,
): string {
  const code = isApiProblem(error) ? problemCode(error) : null;
  if (code) {
    // next-intl lève sur une clé absente : on interroge d'abord.
    const cle = `byCode.${code}`;
    if (t.has(cle)) return t(cle);
  }
  return t("generic");
}

/**
 * Hook prêt à l'emploi — une ligne par composant, aucun repli à fournir.
 *
 * Remplace l'ancien `mutationErrorMessage(error, fallback)` : le repli était
 * un texte traduit passé par l'appelant, donc systématiquement écrasé par le
 * `detail` français de l'API dès que celle-ci en fournissait un. Ne rien
 * avoir à passer supprime la tentation.
 *
 * Les erreurs de CHAMP passent en premier : elles disent PRÉCISÉMENT ce qui
 * ne va pas dans le formulaire, et c'est plus utile qu'un message générique
 * — au prix de rester en français (voir la limite documentée ci-dessus).
 */
export function useProblemMessage(): (error: unknown) => string {
  const t = useTranslations("errors");
  return (error: unknown) => {
    if (isApiProblem(error) && error.errors.length > 0) {
      return error.errors.map((champ) => champ.message).join(" ");
    }
    return problemMessage(error, t);
  };
}

/** Dernier segment de `type` — `.../errors/profile_not_validated` → le code. */
export function problemCode(error: ApiProblem): string | null {
  if (!error.type) return null;
  const segments = error.type.split("/").filter(Boolean);
  const dernier = segments.at(-1);
  return dernier && /^[a-z_]+$/.test(dernier) ? dernier : null;
}
