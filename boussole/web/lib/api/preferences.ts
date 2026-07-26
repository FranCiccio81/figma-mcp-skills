import { apiFetch } from "@/lib/api/client";
import type { Preferences } from "@/lib/api/types";

/** Clés React Query du domaine Préférences (SCR-07). */
export const preferencesKeys = {
  root: ["preferences"] as const,
};

/** Lire les préférences — `GET /preferences` (vide au premier passage). */
export async function getPreferences(signal?: AbortSignal): Promise<Preferences> {
  return apiFetch<Preferences>("/preferences", { signal });
}

/**
 * Remplacer les préférences — `PUT /preferences` (payload complet : l'UI
 * envoie toujours l'état entier du formulaire, Flux 2 §5). Déclenche un
 * re-scoring asynchrone côté serveur (06 §4) : l'appelant doit invalider les
 * caches match (voir `invalidateMatchDependentQueries`).
 */
export async function putPreferences(preferences: Preferences): Promise<void> {
  await apiFetch<undefined>("/preferences", { method: "PUT", body: preferences });
}
