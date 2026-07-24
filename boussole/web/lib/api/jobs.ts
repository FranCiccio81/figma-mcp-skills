import { apiFetch } from "@/lib/api/client";
import type {
  ContractType,
  JobDetail,
  JobSort,
  RemotePolicy,
  SavedState,
  SearchPage,
  SourceInfo,
} from "@/lib/api/types";

/**
 * Paramètres de recherche de `GET /jobs` (openapi.yaml). Les tableaux
 * (`remote`, `contract`) sont sérialisés en clés répétées (`style: form`,
 * `explode: true`) — raison pour laquelle on n'utilise pas `withCursor`
 * (son `extraQuery` ne porte que des valeurs scalaires).
 */
export interface JobSearchParams {
  q?: string;
  remote?: RemotePolicy[];
  contract?: ContractType[];
  salary_min?: number;
  /** Fraîcheur en jours (`posted_since`). */
  posted_since?: number;
  /** Défaut API : `true` — les offres bloquées restent visibles, badgées. */
  include_blocked?: boolean;
  /** Défaut API : `false` — les offres masquées n'apparaissent pas. */
  include_hidden?: boolean;
  /** Ne renvoyer que les offres sauvegardées. */
  saved_only?: boolean;
  sort?: JobSort;
  /** Max 100 (12 §1). */
  limit?: number;
}

/** Clés React Query du domaine Offres — partagées entre liste, détail et mutations. */
export const jobsKeys = {
  all: ["jobs"] as const,
  searches: () => [...jobsKeys.all, "search"] as const,
  search: (params: JobSearchParams) => [...jobsKeys.searches(), params] as const,
  detail: (id: string) => [...jobsKeys.all, "detail", id] as const,
  sources: ["sources"] as const,
};

/**
 * Recherche d'offres — `GET /jobs` (filtres SQL + full-text + rerank).
 * Pagination par curseur : passer `cursor` (le `pageParam` d'`useInfiniteQuery`,
 * voir `getNextCursor` dans `lib/api/client.ts`).
 */
export async function searchJobs(
  params: JobSearchParams = {},
  cursor?: string | null,
  signal?: AbortSignal,
): Promise<SearchPage> {
  const search = new URLSearchParams();
  if (params.q) search.set("q", params.q);
  for (const remote of params.remote ?? []) search.append("remote", remote);
  for (const contract of params.contract ?? []) search.append("contract", contract);
  if (params.salary_min !== undefined) search.set("salary_min", String(params.salary_min));
  if (params.posted_since !== undefined) search.set("posted_since", String(params.posted_since));
  if (params.include_blocked !== undefined) {
    search.set("include_blocked", String(params.include_blocked));
  }
  if (params.include_hidden !== undefined) {
    search.set("include_hidden", String(params.include_hidden));
  }
  if (params.saved_only !== undefined) search.set("saved_only", String(params.saved_only));
  if (params.sort) search.set("sort", params.sort);
  if (params.limit !== undefined) search.set("limit", String(Math.min(params.limit, 100)));
  if (cursor) search.set("cursor", cursor);

  const query = search.toString();
  return apiFetch<SearchPage>(query ? `/jobs?${query}` : "/jobs", { signal });
}

/** Détail d'une offre — `GET /jobs/{id}` (404 → `ApiProblem.status === 404`). */
export async function getJob(id: string, signal?: AbortSignal): Promise<JobDetail> {
  return apiFetch<JobDetail>(`/jobs/${encodeURIComponent(id)}`, { signal });
}

/** Sauvegarder ou masquer une offre — `PUT /jobs/{id}/saved-state` (204). */
export async function setSavedState(id: string, state: SavedState): Promise<void> {
  await apiFetch<undefined>(`/jobs/${encodeURIComponent(id)}/saved-state`, {
    method: "PUT",
    body: { state },
  });
}

/**
 * Retirer la sauvegarde ou le masquage — `DELETE /jobs/{id}/saved-state` (204).
 * Une offre masquée reste toujours restaurable (03 §conventions).
 */
export async function clearSavedState(id: string): Promise<void> {
  await apiFetch<undefined>(`/jobs/${encodeURIComponent(id)}/saved-state`, {
    method: "DELETE",
  });
}

/** Sources d'offres actives — `GET /sources` (transparence, SCR-73). */
export async function getSources(signal?: AbortSignal): Promise<SourceInfo[]> {
  return apiFetch<SourceInfo[]>("/sources", { signal });
}
