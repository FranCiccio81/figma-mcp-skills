import { apiFetch } from "@/lib/api/client";
import type {
  DocType,
  GeneratedContent,
  GeneratedDocument,
  GenerationCreateInput,
  GenerationExport,
  GenerationStatus,
  Page,
} from "@/lib/api/types";

/** Quotas LLM des générations (12 §1 : 10/h, 40/j) — messages M4-b. */
export const GENERATION_QUOTA_HOURLY = 10;
export const GENERATION_QUOTA_DAILY = 40;

/** Filtres de `GET /generations` (openapi.yaml — bibliothèque de documents). */
export interface GenerationListParams {
  doc_type?: DocType;
  status?: GenerationStatus;
  job_id?: string;
  /** Max 100 (12 §1). */
  limit?: number;
}

/** Clés React Query du domaine Générations (SCR-30/31/32, page « Mes documents »). */
export const generationKeys = {
  all: ["generations"] as const,
  lists: () => [...generationKeys.all, "list"] as const,
  list: (params: GenerationListParams) => [...generationKeys.lists(), params] as const,
  detail: (id: string) => [...generationKeys.all, "detail", id] as const,
};

/** Bibliothèque des contenus générés — `GET /generations` (curseur, filtres type/statut/offre). */
export async function listGenerations(
  params: GenerationListParams = {},
  cursor?: string | null,
  signal?: AbortSignal,
): Promise<Page<GeneratedDocument>> {
  const search = new URLSearchParams();
  if (params.doc_type) search.set("doc_type", params.doc_type);
  if (params.status) search.set("status", params.status);
  if (params.job_id) search.set("job_id", params.job_id);
  if (params.limit !== undefined) search.set("limit", String(Math.min(params.limit, 100)));
  if (cursor) search.set("cursor", cursor);
  const query = search.toString();
  return apiFetch<Page<GeneratedDocument>>(query ? `/generations?${query}` : "/generations", {
    signal,
  });
}

/**
 * Créer un contenu — `POST /generations` (202, asynchrone). `Idempotency-Key`
 * générée côté client (UUID) : un double-clic rejoue la même clé et ne crée
 * qu'une génération (12 §1). 429 = quota LLM atteint → message M4-b ;
 * 409 `profile_not_validated` ou `job_expired` selon le contexte.
 */
export async function createGeneration(
  input: GenerationCreateInput,
  idempotencyKey: string,
): Promise<GeneratedDocument> {
  return apiFetch<GeneratedDocument>("/generations", {
    method: "POST",
    body: input,
    idempotencyKey,
  });
}

/** Statut et contenu d'une génération — `GET /generations/{id}` (polling 2 s ×1,5 tant que `pending`). */
export async function getGeneration(id: string, signal?: AbortSignal): Promise<GeneratedDocument> {
  return apiFetch<GeneratedDocument>(`/generations/${encodeURIComponent(id)}`, { signal });
}

/** La génération est-elle stabilisée (plus `pending`) ? Pilote l'arrêt du polling. */
export function isGenerationSettled(document: GeneratedDocument | undefined): boolean {
  return document !== undefined && document.status !== "pending";
}

/**
 * Éditer manuellement le brouillon — `PATCH /generations/{id}`. Le contenu
 * édité est de la responsabilité de l'utilisateur (Flux 5 §6) ; le contrôle
 * d'ancrage devient `null` (non re-vérifié après édition manuelle).
 * 🟡 openapi.yaml ne documente pas le corps de la réponse 200 : le document
 * mis à jour peut être absent (`undefined`) — l'appelant re-fetch alors.
 */
export async function patchGeneration(
  id: string,
  content: GeneratedContent,
): Promise<GeneratedDocument | undefined> {
  return apiFetch<GeneratedDocument | undefined>(`/generations/${encodeURIComponent(id)}`, {
    method: "PATCH",
    body: { content },
  });
}

/**
 * Validation humaine obligatoire avant export (D10) — `POST
 * /generations/{id}/validate`. 🟡 Corps de réponse non documenté (200
 * « Statut = validated ») : peut être `undefined`.
 */
export async function validateGeneration(id: string): Promise<GeneratedDocument | undefined> {
  return apiFetch<GeneratedDocument | undefined>(
    `/generations/${encodeURIComponent(id)}/validate`,
    { method: "POST" },
  );
}

/**
 * Exporter un document validé — `POST /generations/{id}/export`.
 * 409 `generation_not_validated` si le statut n'est pas `validated`
 * (libellé API repris tel quel, Flux 5).
 */
export async function exportGeneration(
  id: string,
  format: GenerationExport["format"],
): Promise<GenerationExport> {
  return apiFetch<GenerationExport>(`/generations/${encodeURIComponent(id)}/export`, {
    method: "POST",
    body: { format },
  });
}
