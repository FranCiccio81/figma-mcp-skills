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

const API_URL = process.env.API_URL ?? "http://localhost:8000";

/** En-têtes entrants explicitement transmis à l'API (liste blanche). */
const FORWARDED_REQUEST_HEADERS = [
  "accept",
  "accept-language",
  "content-type",
  "cookie",
  "idempotency-key",
  "x-csrf-token",
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
