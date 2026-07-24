/**
 * Types API minimaux écrits à la main pour le jalon M1 (auth + /me + conventions).
 *
 * TODO (M2+) : générer l'intégralité des types depuis `cv-job-matching/openapi.yaml`
 * via openapi-typescript (`make openapi-gen`, convention 15 §B — « jamais écrits à
 * la main ») et supprimer ce fichier au profit du module généré.
 */

/** Violation de champ dans une erreur RFC 9457 (12 §1). */
export interface ProblemFieldError {
  field: string;
  code: string;
  message: string;
}

/** Erreur RFC 9457 `application/problem+json` (12 §1). */
export interface Problem {
  type?: string;
  title?: string;
  status: number;
  detail?: string;
  trace_id?: string;
  errors?: ProblemFieldError[];
}

/** État d'onboarding retourné par `GET /me` — pilote l'aiguillage des écrans (03 §3). */
export interface OnboardingState {
  cv_imported: boolean;
  profile_validated: boolean;
  preferences_set: boolean;
}

/** Utilisateur courant — `GET /me`. */
export interface Me {
  id: string;
  email: string;
  locale: string;
  onboarding: OnboardingState;
}

/** Corps de `POST /auth/login` (204 en succès — cookie httpOnly posé). */
export interface LoginInput {
  email: string;
  password: string;
}

/** Corps de `POST /auth/register` (201 en succès — session ouverte). */
export interface RegisterInput {
  email: string;
  password: string;
  locale?: string;
  accepted_terms_version: string;
  accepted_privacy_version: string;
}

/** Page paginée par curseur — jamais d'offset (12 §1). */
export interface Page<T> {
  items: T[];
  next_cursor: string | null;
}
