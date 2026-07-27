import { apiFetch } from "@/lib/api/client";
import type {
  DeleteAccountInput,
  PrivacyExportRequested,
  PrivacyExportStatus,
  PrivacyExportStatusResponse,
} from "@/lib/api/types";

/** Quota d'exports RGPD (RM-Q-3, router privacy : `EXPORT_DAILY_LIMIT`). */
export const PRIVACY_EXPORT_DAILY_LIMIT = 2;

/** Validité du lien signé de téléchargement, en jours (RM-Q-3, signing.py). */
export const PRIVACY_EXPORT_LINK_TTL_DAYS = 7;

/** Clés React Query du domaine Confidentialité (SCR-71/SCR-72). */
export const privacyKeys = {
  all: ["privacy"] as const,
  export: (id: string) => [...privacyKeys.all, "export", id] as const,
};

/**
 * Demander un export RGPD — `POST /privacy/export` (202, asynchrone).
 * `Idempotency-Key` obligatoire côté client : un rejeu de la même clé renvoie
 * l'export existant SANS consommer le quota (router privacy). Erreur 429
 * (2/j, RM-Q-3) avec `ApiProblem.retryAfter`.
 */
export async function requestPrivacyExport(
  idempotencyKey: string,
): Promise<PrivacyExportRequested> {
  return apiFetch<PrivacyExportRequested>("/privacy/export", {
    method: "POST",
    idempotencyKey,
  });
}

/**
 * Statut de l'export — `GET /privacy/exports/{id}` (polling 2 s ×1,5, 12 §1).
 * À `ready`, `download_url` porte le lien signé relatif (7 j) à utiliser tel
 * quel dans un `<a href>` (même origine ; le téléchargement authentifié
 * `GET /privacy/exports/{id}/download` répond 410 `export_expired` au-delà).
 */
export async function getPrivacyExport(
  id: string,
  signal?: AbortSignal,
): Promise<PrivacyExportStatusResponse> {
  return apiFetch<PrivacyExportStatusResponse>(
    `/privacy/exports/${encodeURIComponent(id)}`,
    { signal },
  );
}

/** L'export est-il stabilisé (`ready` ou `expired`) ? Pilote l'arrêt du polling. */
export function isPrivacyExportSettled(
  data: PrivacyExportStatusResponse | undefined,
): boolean {
  const settled: readonly PrivacyExportStatus[] = ["ready", "expired"];
  return data !== undefined && settled.includes(data.status);
}

/**
 * Supprimer le compte — `DELETE /account` (204) : soft delete immédiat, purge
 * sous 30 jours (D09). L'API invalide la session et efface les cookies ;
 * erreurs : 401 `invalid_credentials` (mot de passe), 429 rate limit global.
 */
export async function deleteAccount(password: string): Promise<void> {
  await apiFetch<undefined>("/account", {
    method: "DELETE",
    body: { password } satisfies DeleteAccountInput,
  });
}
