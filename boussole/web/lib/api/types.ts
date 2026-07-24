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

/* ------------------------------------------------------------------ */
/* Offres — jalon M2 (openapi.yaml : /jobs, /jobs/{id}, /sources)      */
/* ------------------------------------------------------------------ */

/** Politique de télétravail d'une offre (openapi.yaml → RemotePolicy). */
export type RemotePolicy = "onsite" | "hybrid" | "full_remote";

/** Type de contrat (openapi.yaml → ContractType). */
export type ContractType =
  | "permanent"
  | "fixed_term"
  | "freelance"
  | "internship"
  | "apprenticeship"
  | "other";

/** Niveau de séniorité (openapi.yaml → SeniorityLevel — nullable côté API). */
export type SeniorityLevel =
  | "intern"
  | "junior"
  | "mid"
  | "senior"
  | "lead"
  | "principal"
  | "executive";

/** État utilisateur d'une offre (`PUT /jobs/{id}/saved-state`). */
export type SavedState = "saved" | "hidden";

/** Tri de `GET /jobs` — `match` inopérant avant le jalon M3 (profil + scoring). */
export type JobSort = "match" | "date" | "relevance";

/** Résumé de matching embarqué dans une carte d'offre — `null` au jalon M2. */
export interface JobMatchSummary {
  score: number;
  confidence: number;
  low_data: boolean;
  has_blocking: boolean;
}

/** Carte d'offre — item de `GET /jobs` (openapi.yaml → JobCard). */
export interface JobCard {
  id: string;
  title: string;
  company_name: string;
  locations: string[];
  remote: RemotePolicy | null;
  contract: ContractType | null;
  /** « 45–55 k€ » ou `null` si non communiqué (microcopie M3-a — jamais estimé). */
  salary_label: string | null;
  posted_at: string | null;
  /** `null` tant que le matching n'est pas livré (M3) — aucun faux score affiché. */
  match: JobMatchSummary | null;
  saved_state: SavedState | null;
}

/** Source d'origine d'une offre — chaque offre en a au moins une (D13, 04 Flux 4 §2). */
export interface JobSourceLink {
  name: string;
  original_url: string;
  posted_at?: string | null;
}

/** Détail d'une offre — `GET /jobs/{id}` (openapi.yaml → JobDetail, allOf JobCard). */
export interface JobDetail extends JobCard {
  description_text: string;
  language: string;
  seniority: SeniorityLevel | null;
  skills_required: string[];
  skills_nice: string[];
  sources: JobSourceLink[];
  /** Cycle de vie de l'offre (openapi.yaml `JobDetail.status`) — bandeau « offre expirée » (04 Flux 4). */
  status?: "active" | "expired" | "withdrawn";
  /** Date d'expiration si connue (openapi.yaml `JobDetail.expires_at`). */
  expires_at?: string | null;
}

/** Page de résultats de `GET /jobs` (curseur, jamais d'offset). */
export type SearchPage = Page<JobCard>;

/** Source d'offres active — `GET /sources` (transparence, SCR-73). */
export interface SourceInfo {
  slug: string;
  name: string;
  kind: "public_api" | "ats_feed" | "partner";
  last_sync_at: string | null;
}
