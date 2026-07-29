import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { SESSION_COOKIE_NAME } from "@/lib/constants";

/**
 * Route racine — aiguillage serveur (03 §3) : session vérifiée contre
 * `GET /me` (appel direct à l'API côté serveur, cookie transmis).
 * Sans session valide → /connexion ; sinon → /tableau-de-bord.
 */
export default async function IndexPage() {
  const cookieStore = await cookies();
  const session = cookieStore.get(SESSION_COOKIE_NAME);

  if (!session) redirect("/connexion");

  // Les DEUX noms, comme le proxy BFF : le compose ne pose que
  // `API_INTERNAL_URL`, et cette page ne lisait que `API_URL`. Mesuré contre
  // l'image web réelle, avec un cookie de session VALIDE :
  //     API_INTERNAL_URL posée (cas du compose) → GET / = 307 vers /connexion
  //     API_URL posée                           → GET / = 307 vers /tableau-de-bord
  // Le correctif précédent avait réparé le proxy et oublié la racine : un
  // utilisateur connecté qui tape l'adresse du site était renvoyé au login.
  const apiUrl =
    process.env.API_INTERNAL_URL ?? process.env.API_URL ?? "http://localhost:8000";
  let authenticated = false;
  try {
    const response = await fetch(`${apiUrl}/api/v1/me`, {
      headers: {
        cookie: `${SESSION_COOKIE_NAME}=${session.value}`,
        "Accept-Language": "fr",
      },
      cache: "no-store",
    });
    authenticated = response.ok;
  } catch {
    // API injoignable : on retombe sur la connexion (SCR-92 — session non vérifiable).
    authenticated = false;
  }

  redirect(authenticated ? "/tableau-de-bord" : "/connexion");
}
