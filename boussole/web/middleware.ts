import { type NextRequest, NextResponse } from "next/server";
import { SESSION_COOKIE_NAME } from "@/lib/constants";

/**
 * Garde de session (03 §3, SCR-92) :
 * - routes (main) sans cookie de session → /connexion, avec conservation de
 *   l'URL cible (`?next=`) pour reprendre après connexion ;
 * - routes (auth) avec cookie de session → /tableau-de-bord.
 *
 * La présence du cookie ne prouve pas sa validité : l'API reste l'autorité
 * (une session expirée produira un 401 → retour SCR-01 côté client).
 */

const PROTECTED_PREFIXES = [
  "/tableau-de-bord",
  "/offres",
  "/candidatures",
  "/profil",
  "/preferences",
  "/parametres",
] as const;

const AUTH_PREFIXES = ["/connexion", "/inscription"] as const;

function matchesPrefix(pathname: string, prefixes: readonly string[]): boolean {
  return prefixes.some((prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`));
}

export function middleware(request: NextRequest): NextResponse {
  const { pathname } = request.nextUrl;
  const hasSession = request.cookies.has(SESSION_COOKIE_NAME);

  if (!hasSession && matchesPrefix(pathname, PROTECTED_PREFIXES)) {
    const loginUrl = new URL("/connexion", request.url);
    loginUrl.searchParams.set("next", pathname);
    return NextResponse.redirect(loginUrl);
  }

  if (hasSession && matchesPrefix(pathname, AUTH_PREFIXES)) {
    return NextResponse.redirect(new URL("/tableau-de-bord", request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    "/connexion/:path*",
    "/inscription/:path*",
    "/tableau-de-bord/:path*",
    "/offres/:path*",
    "/candidatures/:path*",
    "/profil/:path*",
    "/preferences/:path*",
    "/parametres/:path*",
  ],
};
