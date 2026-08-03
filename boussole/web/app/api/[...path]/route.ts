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
 * ⚠️ **`x-forwarded-for` en est volontairement ABSENT.** Il y a figuré, et
 * c'était pire que le défaut qu'il corrigeait.
 *
 * L'intention était bonne : l'API lit cet en-tête pour identifier l'appelant
 * anonyme, `--forwarded-allow-ips` est bien passé à uvicorn, et sans émetteur
 * tout le trafic anonyme tombe dans UN SEUL seau de quota (celui de l'IP du
 * proxy) — un script à 1 req/s suffit alors à faire répondre 429 à toutes les
 * connexions, pour tout le monde.
 *
 * Mais ce proxy **recopie la valeur du client** (`headers.set(nom, valeur)`) :
 * il remplace, il n'ajoute pas. Next ne pose l'en-tête que s'il est absent,
 * donc une valeur envoyée par le client passe intacte jusqu'à uvicorn, qui —
 * le front étant dans `FORWARDED_ALLOW_IPS` — la croit et réécrit
 * `request.client`. Mesuré en revue finale, à travers le front réel :
 *
 *     POST /auth/login ×30, sans en-tête              → {401: 5, 429: 25}
 *     POST /auth/login ×200, X-Forwarded-For tournant → {401: 200}
 *     POST /auth/login ×500, 50 en parallèle          → {401: 500}  en 98 s
 *     puis le bon mot de passe                        → 204
 *
 * Soit ~440 000 tentatives par jour sur un compte, depuis une seule machine.
 * Un limiteur **contournable** est pire qu'un limiteur **grossier** : le
 * second gêne tout le monde de façon visible, le premier ne gêne que les
 * honnêtes gens.
 *
 * Le rétablir suppose une couche en amont qui pose `X-Forwarded-For` de façon
 * autoritaire ET **écrase** celui du client.
 *
 * ## Cette couche existe désormais — et elle se déclare
 *
 * `infra/Caddyfile` fait exactement cela (`header_up X-Forwarded-For
 * {remote_host}` : il REMPLACE, il n'ajoute pas), et
 * `docker-compose.prod.yml` ne publie de ports que sur Caddy — `web` n'est
 * joignable que par lui. La garantie est donc structurelle, pas seulement
 * documentaire.
 *
 * Mais elle n'est vraie que dans CE montage. Le compose de développement n'a
 * pas de Caddy, et y transmettre l'en-tête rendrait de nouveau l'identité de
 * limitation forgeable. D'où un interrupteur explicite plutôt qu'un
 * comportement implicite : on ne transmet que si l'exploitant DÉCLARE la
 * bordure. Oublier la variable dégrade (seau partagé, auto-DoS grossier) ;
 * la poser à tort est un geste conscient, pas un défaut de conception.
 */
const TRUSTED_EDGE = process.env.TRUSTED_EDGE === "true";

const FORWARDED_REQUEST_HEADERS = [
  "accept",
  "accept-language",
  "content-type",
  "cookie",
  "idempotency-key",
  "x-csrf-token",
  // Uniquement derrière une bordure qui l'écrase — voir ci-dessus.
  // Uniquement derrière une bordure qui l'écrase — voir ci-dessus.
  ...(TRUSTED_EDGE ? (["x-forwarded-for"] as const) : []),
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
