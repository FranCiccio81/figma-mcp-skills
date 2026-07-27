import { apiFetch, withCursor } from "@/lib/api/client";
import type {
  Application,
  ApplicationInput,
  ApplicationStatus,
  ApplicationStatusChange,
  Page,
} from "@/lib/api/types";

/** Ordre d'affichage des statuts (SCR-40, Flux 7 §2 — du brouillon à la sortie). */
export const APPLICATION_STATUS_ORDER: readonly ApplicationStatus[] = [
  "draft",
  "to_apply",
  "applied",
  "interviewing",
  "offer",
  "rejected",
  "withdrawn",
];

/** Paramètres de `GET /applications` (openapi.yaml). */
export interface ApplicationListParams {
  status?: ApplicationStatus;
  /** Max 100 (12 §1). */
  limit?: number;
}

/**
 * Clés React Query du domaine Candidatures (SCR-40/41/42).
 *
 * ⚠️ `GET /applications` est consommé sous DEUX formes qui n'ont pas la même
 * structure de cache : `useInfiniteQuery` (SCR-40 — `{ pages: Page[] }`) et
 * `useQuery` (carte SCR-10 — `Page` brute). Elles DOIVENT porter des clés
 * disjointes, sinon les deux écrans partagent le même objet Query et le
 * consommateur reçoit la structure de l'autre (`pages` absent → TypeError).
 * D'où le discriminant explicite `"infinite"` / le préfixe `"summary"`.
 * Les deux restent sous le préfixe {@link applicationKeys.all} : une
 * invalidation par `applicationKeys.all` continue de couvrir l'ensemble.
 */
export const applicationKeys = {
  all: ["applications"] as const,
  lists: () => [...applicationKeys.all, "list"] as const,
  /** Liste paginée par curseur (`useInfiniteQuery`, SCR-40). */
  infinite: (params: ApplicationListParams) =>
    [...applicationKeys.lists(), "infinite", params] as const,
  /** Première page seule (`useQuery`, carte « Candidatures en cours » SCR-10). */
  summary: (params: ApplicationListParams) =>
    [...applicationKeys.all, "summary", params] as const,
  detail: (id: string) => [...applicationKeys.all, "detail", id] as const,
};

/** Lister les candidatures — `GET /applications` (curseur, filtre statut). */
export async function listApplications(
  params: ApplicationListParams = {},
  cursor?: string | null,
  signal?: AbortSignal,
): Promise<Page<Application>> {
  const extra: Record<string, string> = {};
  if (params.status) extra.status = params.status;
  return apiFetch<Page<Application>>(
    withCursor("/applications", { limit: params.limit, cursor }, extra),
    { signal },
  );
}

/**
 * Créer une candidature — `POST /applications` (Idempotency-Key, 12 §1).
 * Offre interne (`job_posting_id`) ou externe (`external_title` +
 * `external_company` requis, 11 §5 — 422 par champ sinon).
 * Le corps N'ACCEPTE PAS de statut initial : la candidature est toujours créée
 * en `draft` — pour un autre statut, chaîner {@link changeApplicationStatus}.
 */
export async function createApplication(
  input: ApplicationInput,
  idempotencyKey: string,
): Promise<Application> {
  return apiFetch<Application>("/applications", {
    method: "POST",
    body: input,
    idempotencyKey,
  });
}

/** Détail d'une candidature — `GET /applications/{id}` (12 §2). */
export async function getApplication(id: string, signal?: AbortSignal): Promise<Application> {
  return apiFetch<Application>(`/applications/${encodeURIComponent(id)}`, { signal });
}

/** Modifier les notes libres — `PATCH /applications/{id}` (12 §2). */
export async function patchApplication(
  id: string,
  input: Pick<ApplicationInput, "notes">,
): Promise<Application> {
  return apiFetch<Application>(`/applications/${encodeURIComponent(id)}`, {
    method: "PATCH",
    body: input,
  });
}

/**
 * Changer le statut — `POST /applications/{id}/status` (transition historisée,
 * l'historique n'est jamais réécrit). 422 = transition non permise (Flux 7 Q7).
 */
export async function changeApplicationStatus(
  id: string,
  change: ApplicationStatusChange,
): Promise<Application> {
  return apiFetch<Application>(`/applications/${encodeURIComponent(id)}/status`, {
    method: "POST",
    body: change,
  });
}

/**
 * Supprimer un suivi de candidature — `DELETE /applications/{id}` (12 §2).
 * L'historique est définitivement effacé ; les documents générés associés
 * ne sont pas supprimés (Flux 7, point de décision).
 */
export async function deleteApplication(id: string): Promise<void> {
  await apiFetch<undefined>(`/applications/${encodeURIComponent(id)}`, { method: "DELETE" });
}
