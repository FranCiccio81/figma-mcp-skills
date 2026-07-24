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

/** Tri de `GET /jobs` (openapi.yaml — défaut API : `match`, profil validé requis). */
export type JobSort = "match" | "date" | "relevance";

/** Résumé de matching embarqué dans une carte d'offre (M1-a — `null` = rien d'affiché). */
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
  /** `null` si non scorée (profil non validé…) — aucun faux score affiché. */
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

/* ------------------------------------------------------------------ */
/* Profil & provenance — jalon M3 (openapi.yaml : /profile*)           */
/* ------------------------------------------------------------------ */

/** Origine d'un champ de profil (D05) — pilote les badges « Extrait du CV ». */
export type ProvenanceSource = "cv_extraction" | "user_input" | "user_confirmed";

/**
 * Provenance et confiance d'un champ extrait (openapi.yaml → Provenance).
 * `confidence` (0–1) n'est significative que pour `cv_extraction` : en dessous
 * de 0,5 la donnée est traitée comme inconnue par le moteur (06 §1, M3-d).
 */
export interface Provenance {
  source: ProvenanceSource;
  confidence?: number;
}

/** Niveau de langue CECRL (openapi.yaml → CefrLevel). */
export type CefrLevel = "A1" | "A2" | "B1" | "B2" | "C1" | "C2";

/** Statut du profil — le tri `match` et la génération exigent `validated`. */
export type ProfileStatus = "draft" | "validated";

/** Corps de création/édition d'une expérience (openapi.yaml → ExperienceInput). */
export interface ExperienceInput {
  title: string;
  company: string;
  sector_code?: string | null;
  /** Date ISO `YYYY-MM-DD`. */
  start_date: string;
  /** `null` = poste en cours. */
  end_date?: string | null;
  description?: string | null;
}

/** Expérience du profil (openapi.yaml → Experience). */
export interface Experience extends ExperienceInput {
  id: string;
  provenance?: Provenance;
}

/**
 * Formation — alignée sur l'API (`profile_educations` : degree, institution,
 * années entières 1900–2100, pas de description).
 */
export interface EducationInput {
  degree: string;
  institution: string;
  start_year?: number | null;
  end_year?: number | null;
}

/** Formation du profil. */
export interface Education extends EducationInput {
  id: string;
  provenance?: Provenance;
}

/** Compétence du profil (openapi.yaml → Profile.skills[]). */
export interface ProfileSkill {
  id: string;
  label: string;
  provenance?: Provenance;
}

/** Corps de création d'une compétence (source = user_input). */
export interface ProfileSkillInput {
  label: string;
}

/**
 * Langue du profil (openapi.yaml → Profile.languages[]).
 * 🟡 `id` absent du schéma openapi mais requis pour le CRUD sous-ressource
 * (12 §2 : « idem experiences ») — supposé fourni par l'API.
 */
export interface ProfileLanguage {
  id: string;
  lang_code: string;
  level: CefrLevel;
  provenance?: Provenance;
}

/** Corps de création/édition d'une langue. */
export interface ProfileLanguageInput {
  lang_code: string;
  level: CefrLevel;
}

/** Profil complet avec provenance par champ — `GET /profile` (openapi.yaml → Profile). */
export interface Profile {
  id: string;
  status: ProfileStatus;
  version: number;
  headline: string | null;
  summary: string | null;
  seniority: SeniorityLevel | null;
  total_experience_years: number | null;
  experiences: Experience[];
  educations: Education[];
  skills: ProfileSkill[];
  languages: ProfileLanguage[];
}

/** Corps de `PATCH /profile` — champs racine uniquement. */
export interface ProfilePatch {
  headline?: string | null;
  summary?: string | null;
  seniority?: SeniorityLevel | null;
}

/* ------------------------------------------------------------------ */
/* Préférences — jalon M3 (openapi.yaml : /preferences)                */
/* ------------------------------------------------------------------ */

/** Préférence de télétravail du candidat (openapi.yaml → RemotePreference). */
export type RemotePreference = "required" | "preferred" | "indifferent" | "onsite_preferred";

/**
 * Lieu accepté avec rayon (openapi.yaml → Preferences.locations[]).
 * 🟡 `lat`/`lon` sont requis par l'API mais le géocodage des villes n'arrive
 * qu'au jalon M4 : l'UI saisit `label` en texte libre et envoie `0`/`0` pour
 * les nouveaux lieux (valeurs existantes préservées à l'édition).
 */
export interface PreferenceLocation {
  label: string;
  lat: number;
  lon: number;
  /** Défaut API : 30 km. */
  radius_km?: number;
}

/** Préférences de recherche — `GET`/`PUT /preferences` (payload complet). */
export interface Preferences {
  remote_pref?: RemotePreference;
  contract_types: ContractType[];
  /** « strict » : les autres contrats deviennent des critères bloquants. */
  contract_strict: boolean;
  /** Salaire souhaité (€ brut/an) — guide le score. */
  salary_min: number | null;
  /** Minimum strict (€ brut/an) — en dessous : bloquant `salary_below_minimum`. */
  salary_min_strict: number | null;
  locations: PreferenceLocation[];
  target_titles: string[];
  sectors_preferred: string[];
  sectors_excluded: string[];
  target_companies: string[];
  keywords: string[];
}

/* ------------------------------------------------------------------ */
/* Matching — jalon M3 (openapi.yaml : /jobs/{id}/match, /matches,     */
/* /jobs/{id}/explanation)                                             */
/* ------------------------------------------------------------------ */

/**
 * Critère bloquant (openapi.yaml → MatchResult.blocking_criteria[]).
 * `label` porte la microcopie M2 interpolée côté serveur (12 §4 —
 * libellés API repris tels quels) ; les codes sont ceux de 06 §3.
 */
export interface BlockingCriterion {
  code: string;
  label?: string;
}

/** Côté manquant d'une dimension inconnue (openapi.yaml → unknown_dimensions[].reason). */
export type UnknownDimensionReason =
  | "job_not_provided"
  | "profile_not_provided"
  | "low_extraction_confidence";

/** Dimension non évaluable, listée sous « Non précisé » (M3-a/M3-b — jamais estimée). */
export interface UnknownDimension {
  dimension: string;
  reason: UnknownDimensionReason;
  /** Libellé API repris tel quel (ex. « Salaire non communiqué »). */
  label?: string;
}

/** Compétence requise couverte par une compétence proche (06 dim. 1). */
export interface DimensionRelatedSkill {
  required: string;
  matched_with: string;
}

/**
 * Valeurs comparées d'une dimension (openapi.yaml → dimensions[].details,
 * objet libre — champs connus d'après l'exemple de 12 §4).
 */
export interface DimensionDetails {
  /** Compétences requises couvertes nominativement. */
  matched?: string[];
  /** Compétences couvertes par proximité. */
  related?: DimensionRelatedSkill[];
  /** Compétences requises manquantes — alimentent les lacunes. */
  missing?: string[];
  /** Distance au lieu retenu (dimension localisation). */
  distance_km?: number;
  /** Lieu accepté retenu (dimension localisation). */
  matched_location?: string;
  [extra: string]: unknown;
}

/** Sous-score d'une dimension (openapi.yaml → MatchResult.dimensions[]). */
export interface DimensionScore {
  dimension: string;
  /** 0–1. */
  subscore: number;
  weight: number;
  /** `false` = dimension inconnue (`k=0`) — n'entre pas dans le score. */
  known: boolean;
  details?: DimensionDetails;
}

/** Résultat de matching — `GET /jobs/{id}/match` (openapi.yaml → MatchResult, D03). */
export interface MatchResult {
  job_id: string;
  profile_version: number;
  scoring_version: string;
  /** Compatibilité 0–100, calculée sur les seules dimensions connues. */
  score: number;
  /** Part des informations réellement disponibles, 0–100 — jamais fusionnée au score. */
  confidence: number;
  /** `true` si < 40 % du poids est connu — score affiché grisé mais lisible (M1-d). */
  low_data: boolean;
  blocking_criteria: BlockingCriterion[];
  unknown_dimensions: UnknownDimension[];
  dimensions: DimensionScore[];
}

/** Reformulation LLM des faits d'explication — `POST /jobs/{id}/explanation` (D14). */
export interface MatchExplanation {
  summary: string;
  strengths: string[];
  gaps: string[];
  uncertainties: string[];
  blocking_notes: string[];
  prompt_version: string;
}
