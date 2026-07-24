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

  const apiUrl = process.env.API_URL ?? "http://localhost:8000";
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
