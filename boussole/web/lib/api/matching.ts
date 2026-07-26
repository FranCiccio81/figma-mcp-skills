import type { QueryClient } from "@tanstack/react-query";
import { apiFetch, isApiProblem, withCursor } from "@/lib/api/client";
import { jobsKeys } from "@/lib/api/jobs";
import type { MatchExplanation, MatchResult, SearchPage } from "@/lib/api/types";

/**
 * Paramètres de `GET /matches` (openapi.yaml) — offres classées par score
 * pour le profil courant, pagination par curseur.
 */
export interface MatchesParams {
  /** Score minimum 0–100. */
  min_score?: number;
  /** Défaut API : `true` — les offres bloquées restent listées, badgées. */
  include_blocked?: boolean;
  /** Max 100 (12 §1). */
  limit?: number;
}

/** Clés React Query du domaine Matching — partagées entre panneau, listes et dashboard. */
export const matchKeys = {
  all: ["match"] as const,
  job: (jobId: string) => [...matchKeys.all, "job", jobId] as const,
  lists: () => [...matchKeys.all, "list"] as const,
  list: (params: MatchesParams) => [...matchKeys.lists(), params] as const,
};

/**
 * Détecte le 409 `profile_not_validated` de `GET /jobs/{id}/match` — seul 409
 * documenté sur cette route (openapi.yaml). L'UI affiche alors un encart
 * d'invitation vers /profil, jamais l'erreur brute.
 */
export function isProfileNotValidated(error: unknown): boolean {
  return (
    isApiProblem(error) &&
    error.status === 409 &&
    (error.type === undefined || error.type.includes("profile_not_validated"))
  );
}

/**
 * Résultat de matching pour le profil courant — `GET /jobs/{id}/match`.
 * Jette une {@link ApiProblem} 409 `profile_not_validated` si le profil
 * n'est pas validé (voir {@link isProfileNotValidated}).
 */
export async function getMatch(jobId: string, signal?: AbortSignal): Promise<MatchResult> {
  return apiFetch<MatchResult>(`/jobs/${encodeURIComponent(jobId)}/match`, { signal });
}

/** Offres classées par score — `GET /matches` (items = JobCard avec `match` renseigné). */
export async function getMatches(
  params: MatchesParams = {},
  cursor?: string | null,
  signal?: AbortSignal,
): Promise<SearchPage> {
  const extra: Record<string, string> = {};
  if (params.min_score !== undefined) extra.min_score = String(params.min_score);
  if (params.include_blocked !== undefined) {
    extra.include_blocked = String(params.include_blocked);
  }
  return apiFetch<SearchPage>(withCursor("/matches", { limit: params.limit, cursor }, extra), {
    signal,
  });
}

/**
 * Reformulation LLM des faits d'explication — `POST /jobs/{id}/explanation`
 * (mise en cache serveur par version de profil/scoring). 429 = quota LLM
 * atteint (10/h, 40/j) → message M4-b, la couche déterministe reste affichée.
 */
export async function postExplanation(jobId: string): Promise<MatchExplanation> {
  return apiFetch<MatchExplanation>(`/jobs/${encodeURIComponent(jobId)}/explanation`, {
    method: "POST",
  });
}

/**
 * Invalide tous les caches dépendant du score après une mutation de profil ou
 * de préférences (le re-scoring est asynchrone, 06 §4) : résultats de match,
 * listes `/matches` et recherches `/jobs` (les cartes embarquent `match`).
 */
export function invalidateMatchDependentQueries(queryClient: QueryClient): void {
  void queryClient.invalidateQueries({ queryKey: matchKeys.all });
  void queryClient.invalidateQueries({ queryKey: jobsKeys.all });
}
