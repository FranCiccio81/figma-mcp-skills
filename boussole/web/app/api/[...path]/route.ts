import { type NextRequest, NextResponse } from "next/server";

/**
 * Proxy BFF même origine (D11, 12 §1) : /api/* → `${API_URL}/api/*`.
 *
 * - transmet méthode, corps, query string, cookies (session httpOnly),
 *   `X-CSRF-Token` (double-submit), `Accept-Language` et `Idempotency-Key` ;
 * - retourne la réponse telle quelle, y compris `application/problem+json`
 *   (RFC 9457), `Retry-After` (429) et les `Set-Cookie` de l'API ;
 * - CORS reste fermé : le navigateur ne parle jamais directement à l'API.
 */

/**
 * Adresse interne de l'API.
 *
 * Les DEUX noms sont acceptés, et c'est délibéré : le compose posait
 * `API_INTERNAL_URL`, ce code lisait `API_URL`, et personne ne faisait le
 * lien. Le front démarrait, la page s'affichait, et **chaque** appel API
 * partait sur `http://localhost:8000` — inexistant dans le conteneur web —
 * pour finir en 500. Toute l'application, pas une fonctionnalité.
 *
 * Corriger un seul des deux côtés aurait laissé l'autre nom en embuscade
 * pour le prochain déploiement.
 */
const API_URL =
  process.env.API_INTERNAL_URL ?? process.env.API_URL ?? "http://localhost:8000";

/**
 * En-têtes entrants explicitement transmis à l'API (liste blanche).
 *
 * `x-forwarded-for` est la moitié manquante d'un correctif que l'API croyait
 * complet. Elle lit cet en-tête pour identifier l'appelant anonyme, et
 * `--forwarded-allow-ips` est bien passé à uvicorn — mais **personne ne
 * l'émettait** : le proxy ne le transmettait pas. Résultat mesuré en revue,
 * front réel devant l'API réelle : tout le trafic anonyme tombait dans UN
 * SEUL seau de quota (`rl:global:ip:127.0.0.1:…`, l'IP du proxy). Un script
 * à une requête par seconde suffisait à faire répondre 429 à **toutes** les
 * connexions et **toutes** les inscriptions, pour tout le monde.
 *
 * Vérifié en exécution, faux API en écoute derrière le proxy réel :
 *
 *     curl -H "X-Forwarded-For: 203.0.113.7" …  → l'API reçoit 203.0.113.7
 *     curl (sans en-tête)                       → l'API reçoit 127.0.0.1
 *
 * Le second cas est celui qui compte : quand rien n'arrive en amont, **Next
 * pose lui-même l'en-tête avec l'adresse réelle du client**. La chaîne est
 * donc complète avec ou sans reverse proxy devant — ce qui est la situation
 * du `docker-compose` livré, où le front est le premier saut.
 *
 * Sa valeur n'est pas digne de confiance en soi — c'est pour ça que l'API
 * n'écoute que les pairs listés dans `FORWARDED_ALLOW_IPS`. La transmettre
 * sans cette liste blanche côté API laisserait n'importe qui usurper une IP.
 */
const FORWARDED_REQUEST_HEADERS = [
  "accept",
  "accept-language",
  "content-type",
  "cookie",
  "idempotency-key",
  "x-csrf-token",
  "x-forwarded-for",
] as const;

/** En-têtes de transport recalculés par le runtime — jamais recopiés. */
const STRIPPED_RESPONSE_HEADERS = ["content-encoding", "content-length", "transfer-encoding"] as const;

type RouteContext = { params: Promise<{ path: string[] }> };

async function proxy(request: NextRequest, context: RouteContext): Promise<NextResponse> {
  const { path } = await context.params;

  const targetUrl = new URL(`${API_URL}/api/${path.join("/")}`);
  targetUrl.search = request.nextUrl.search;

  const headers = new Headers();
  for (const name of FORWARDED_REQUEST_HEADERS) {
    const value = request.headers.get(name);
    if (value !== null) headers.set(name, value);
  }

  const hasBody = request.method !== "GET" && request.method !== "HEAD";
  const upstream = await fetch(targetUrl, {
    method: request.method,
    headers,
    body: hasBody ? request.body : undefined,
    redirect: "manual",
    cache: "no-store",
    // Requis par undici pour streamer un corps de requête.
    duplex: "half",
  } as RequestInit & { duplex: "half" });

  const responseHeaders = new Headers(upstream.headers);
  for (const name of STRIPPED_RESPONSE_HEADERS) responseHeaders.delete(name);

  return new NextResponse(upstream.body, {
    status: upstream.status,
    headers: responseHeaders,
  });
}

export {
  proxy as GET,
  proxy as POST,
  proxy as PATCH,
  proxy as PUT,
  proxy as DELETE,
};
