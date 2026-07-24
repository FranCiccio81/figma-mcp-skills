import { API_BASE_PATH, CSRF_COOKIE_NAME } from "@/lib/constants";
import type { Page, Problem, ProblemFieldError } from "@/lib/api/types";

/**
 * Erreur typée construite depuis une réponse `application/problem+json`
 * (RFC 9457, 12 §1). Expose aussi `retryAfter` (secondes) pour les 429.
 */
export class ApiProblem extends Error {
  readonly type?: string;
  readonly title?: string;
  readonly status: number;
  readonly detail?: string;
  readonly traceId?: string;
  readonly errors: ProblemFieldError[];
  /** Secondes avant nouvel essai (en-tête `Retry-After` des réponses 429). */
  readonly retryAfter?: number;

  constructor(problem: Problem, retryAfter?: number) {
    super(problem.detail ?? problem.title ?? `HTTP ${problem.status}`);
    this.name = "ApiProblem";
    this.type = problem.type;
    this.title = problem.title;
    this.status = problem.status;
    this.detail = problem.detail;
    this.traceId = problem.trace_id;
    this.errors = problem.errors ?? [];
    this.retryAfter = retryAfter;
  }
}

/** Garde de type pour brancher la gestion d'erreur (formulaires, React Query…). */
export function isApiProblem(error: unknown): error is ApiProblem {
  return error instanceof ApiProblem;
}

type HttpMethod = "GET" | "POST" | "PATCH" | "PUT" | "DELETE";

const MUTATING_METHODS: ReadonlySet<HttpMethod> = new Set(["POST", "PATCH", "PUT", "DELETE"]);

/** Lit un cookie non-httpOnly côté navigateur (jeton CSRF double-submit). */
function readCookie(name: string): string | null {
  if (typeof document === "undefined") return null;
  const prefix = `${name}=`;
  for (const part of document.cookie.split("; ")) {
    if (part.startsWith(prefix)) return decodeURIComponent(part.slice(prefix.length));
  }
  return null;
}

async function toApiProblem(response: Response): Promise<ApiProblem> {
  const retryAfterHeader = response.headers.get("Retry-After");
  const parsedRetryAfter = retryAfterHeader ? Number.parseInt(retryAfterHeader, 10) : Number.NaN;
  const retryAfter = Number.isNaN(parsedRetryAfter) ? undefined : parsedRetryAfter;

  let problem: Problem = { status: response.status, title: response.statusText };
  const contentType = response.headers.get("Content-Type") ?? "";
  if (contentType.includes("json")) {
    try {
      problem = { ...problem, ...((await response.json()) as Partial<Problem>) };
    } catch {
      // Corps illisible : on garde le fallback statut/statusText.
    }
  }
  return new ApiProblem(problem, retryAfter);
}

export interface ApiFetchOptions {
  method?: HttpMethod;
  /** Sérialisé en JSON. Omis pour les requêtes sans corps. */
  body?: unknown;
  headers?: Record<string, string>;
  signal?: AbortSignal;
  /** En-tête `Idempotency-Key` pour les créations à effet (12 §1). */
  idempotencyKey?: string;
}

/**
 * Wrapper fetch typé vers l'API Boussole via le proxy même origine (`/api/v1`).
 *
 * - `credentials: "include"` — la session est un cookie httpOnly (12 §1) ;
 * - injecte `X-CSRF-Token` (double-submit) sur toute méthode mutante ;
 * - jette une {@link ApiProblem} typée sur toute réponse non-2xx (problem+json).
 */
export async function apiFetch<T>(path: string, options: ApiFetchOptions = {}): Promise<T> {
  const method = options.method ?? "GET";

  const headers = new Headers(options.headers);
  headers.set("Accept", "application/json");
  if (options.body !== undefined) headers.set("Content-Type", "application/json");
  if (options.idempotencyKey) headers.set("Idempotency-Key", options.idempotencyKey);
  if (MUTATING_METHODS.has(method)) {
    const csrfToken = readCookie(CSRF_COOKIE_NAME);
    if (csrfToken) headers.set("X-CSRF-Token", csrfToken);
  }

  const response = await fetch(`${API_BASE_PATH}${path}`, {
    method,
    headers,
    credentials: "include",
    body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
    signal: options.signal,
  });

  if (!response.ok) throw await toApiProblem(response);
  if (response.status === 204) return undefined as T;
  const contentType = response.headers.get("Content-Type") ?? "";
  if (!contentType.includes("json")) return undefined as T;
  return (await response.json()) as T;
}

/** Paramètres de pagination par curseur (12 §1 — `limit` max 100, jamais d'offset). */
export interface CursorParams {
  limit?: number;
  cursor?: string | null;
}

/** Construit une URL paginée par curseur : `withCursor("/jobs", { limit: 20, cursor })`. */
export function withCursor(
  path: string,
  params: CursorParams = {},
  extraQuery: Record<string, string> = {},
): string {
  const search = new URLSearchParams(extraQuery);
  if (params.limit !== undefined) search.set("limit", String(Math.min(params.limit, 100)));
  if (params.cursor) search.set("cursor", params.cursor);
  const query = search.toString();
  return query ? `${path}?${query}` : path;
}

/**
 * Curseur de page suivante pour `useInfiniteQuery`
 * (`getNextPageParam: getNextCursor` — `undefined` = fin de liste).
 */
export function getNextCursor<T>(page: Page<T>): string | undefined {
  return page.next_cursor ?? undefined;
}
