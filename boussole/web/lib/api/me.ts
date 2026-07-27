import { apiFetch } from "@/lib/api/client";
import type { Me } from "@/lib/api/types";

/** Clés React Query de l'utilisateur courant (checklist d'onboarding, SCR-10). */
export const meKeys = {
  root: ["me"] as const,
};

/** Utilisateur courant et état d'onboarding — `GET /me` (03 §3 : jamais d'état local seul). */
export async function getMe(signal?: AbortSignal): Promise<Me> {
  return apiFetch<Me>("/me", { signal });
}
