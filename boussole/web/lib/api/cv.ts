import { apiFetch } from "@/lib/api/client";
import type { CvApplyInput, CvDocument, Profile } from "@/lib/api/types";

/** Taille maximale d'un CV importé (openapi.yaml : PDF/DOCX ≤ 10 Mo). */
export const CV_MAX_FILE_BYTES = 10 * 1024 * 1024;

/** Extensions acceptées côté client (contrôle immédiat avant upload, Flux 1 §2). */
export const CV_ACCEPTED_EXTENSIONS = [".pdf", ".docx"] as const;

/** Types MIME acceptés (12 §5 — validation réelle par magic bytes côté API). */
export const CV_ACCEPTED_MIME_TYPES = [
  "application/pdf",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
] as const;

/** Clés React Query du domaine Import CV (SCR-05/SCR-06/SCR-51). */
export const cvKeys = {
  all: ["cv-documents"] as const,
  document: (id: string) => [...cvKeys.all, id] as const,
};

/** Contrôle client immédiat de l'extension (Flux 1 §2 — avant tout upload). */
export function hasAcceptedExtension(filename: string): boolean {
  const lower = filename.toLowerCase();
  return CV_ACCEPTED_EXTENSIONS.some((extension) => lower.endsWith(extension));
}

/**
 * Importer un CV — `POST /cv-documents` (multipart, 202, parsing asynchrone).
 * Erreurs : 413 `too_large`, 415 `unsupported_format`, 429 quota 5/j
 * (`ApiProblem.retryAfter`).
 */
export async function uploadCvDocument(file: File): Promise<CvDocument> {
  const formData = new FormData();
  formData.append("file", file);
  return apiFetch<CvDocument>("/cv-documents", { method: "POST", formData });
}

/** Statut du parsing et résultat d'extraction — `GET /cv-documents/{id}` (polling 2 s ×1,5). */
export async function getCvDocument(id: string, signal?: AbortSignal): Promise<CvDocument> {
  return apiFetch<CvDocument>(`/cv-documents/${encodeURIComponent(id)}`, { signal });
}

/** Le parsing est-il terminé (succès ou échec) ? Pilote l'arrêt du polling. */
export function isCvDocumentSettled(document: CvDocument | undefined): boolean {
  return document !== undefined && (document.status === "parsed" || document.status === "failed");
}

/**
 * Appliquer au profil les éléments cochés de la revue — `POST
 * /cv-documents/{id}/apply` (`item_ids: null` = tout ; `include_headline` /
 * `include_summary` pour les deux champs racine de la proposition).
 * Ne crée que des champs `cv_extraction` : l'existant saisi ou confirmé n'est
 * jamais écrasé (03 Q4). Retourne le profil mis à jour.
 */
export async function applyCvDocument(id: string, input: CvApplyInput): Promise<Profile> {
  return apiFetch<Profile>(`/cv-documents/${encodeURIComponent(id)}/apply`, {
    method: "POST",
    body: input,
  });
}
