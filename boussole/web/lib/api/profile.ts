import { apiFetch } from "@/lib/api/client";
import type {
  Education,
  EducationInput,
  Experience,
  ExperienceInput,
  Profile,
  ProfileLanguage,
  ProfileLanguageInput,
  ProfilePatch,
  ProfileSkill,
  ProfileSkillInput,
} from "@/lib/api/types";

/** Clés React Query du domaine Profil (SCR-06/SCR-50). */
export const profileKeys = {
  root: ["profile"] as const,
};

/** Profil complet avec provenance et confiance par champ — `GET /profile`. */
export async function getProfile(signal?: AbortSignal): Promise<Profile> {
  return apiFetch<Profile>("/profile", { signal });
}

/** Modifier les champs racine — `PATCH /profile` (version incrémentée). */
export async function patchProfile(patch: ProfilePatch): Promise<Profile> {
  return apiFetch<Profile>("/profile", { method: "PATCH", body: patch });
}

/**
 * Valider le profil — `POST /profile/validate` (promotion `cv_extraction` →
 * `user_confirmed`). Préconditions : ≥ 3 compétences ET ≥ 1 expérience ou
 * formation, sinon 409 avec messages ciblés (`ApiProblem.errors`).
 */
export async function validateProfile(): Promise<Profile> {
  return apiFetch<Profile>("/profile/validate", { method: "POST" });
}

/* --- Expériences — POST/PATCH/DELETE /profile/experiences[/{id}] ---- */

/** Ajouter une expérience (source = user_input). */
export async function createExperience(input: ExperienceInput): Promise<Experience> {
  return apiFetch<Experience>("/profile/experiences", { method: "POST", body: input });
}

/** Modifier une expérience (la provenance passe à user_input). */
export async function updateExperience(
  id: string,
  input: ExperienceInput,
): Promise<Experience> {
  return apiFetch<Experience>(`/profile/experiences/${encodeURIComponent(id)}`, {
    method: "PATCH",
    body: input,
  });
}

/** Supprimer une expérience (204). */
export async function deleteExperience(id: string): Promise<void> {
  await apiFetch<undefined>(`/profile/experiences/${encodeURIComponent(id)}`, {
    method: "DELETE",
  });
}

/* --- Formations — 12 §2 : « idem educations, skills, languages » ----- */

/** Ajouter une formation. */
export async function createEducation(input: EducationInput): Promise<Education> {
  return apiFetch<Education>("/profile/educations", { method: "POST", body: input });
}

/** Modifier une formation. */
export async function updateEducation(id: string, input: EducationInput): Promise<Education> {
  return apiFetch<Education>(`/profile/educations/${encodeURIComponent(id)}`, {
    method: "PATCH",
    body: input,
  });
}

/** Supprimer une formation (204). */
export async function deleteEducation(id: string): Promise<void> {
  await apiFetch<undefined>(`/profile/educations/${encodeURIComponent(id)}`, {
    method: "DELETE",
  });
}

/* --- Compétences ----------------------------------------------------- */

/** Ajouter une compétence. */
export async function createSkill(input: ProfileSkillInput): Promise<ProfileSkill> {
  return apiFetch<ProfileSkill>("/profile/skills", { method: "POST", body: input });
}

/** Supprimer une compétence (204). */
export async function deleteSkill(id: string): Promise<void> {
  await apiFetch<undefined>(`/profile/skills/${encodeURIComponent(id)}`, { method: "DELETE" });
}

/* --- Langues ---------------------------------------------------------- */

/** Ajouter une langue (code ISO + niveau CECRL). */
export async function createLanguage(input: ProfileLanguageInput): Promise<ProfileLanguage> {
  return apiFetch<ProfileLanguage>("/profile/languages", { method: "POST", body: input });
}

/** Modifier une langue. */
export async function updateLanguage(
  id: string,
  input: ProfileLanguageInput,
): Promise<ProfileLanguage> {
  return apiFetch<ProfileLanguage>(`/profile/languages/${encodeURIComponent(id)}`, {
    method: "PATCH",
    body: input,
  });
}

/** Supprimer une langue (204). */
export async function deleteLanguage(id: string): Promise<void> {
  await apiFetch<undefined>(`/profile/languages/${encodeURIComponent(id)}`, {
    method: "DELETE",
  });
}
