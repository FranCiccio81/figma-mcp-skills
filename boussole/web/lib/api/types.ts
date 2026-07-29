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
  kind: "public_api" | "ats_feed" | "partner" | "demo";
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
  | "low_extraction_confidence"
  /** Limite de l'outil, pas des données : le critère n'a pas pu être évalué. */
  | "unavailable";

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

/* ------------------------------------------------------------------ */
/* Import CV — jalon M4 (openapi.yaml : /cv-documents*)                */
/* ------------------------------------------------------------------ */

/** Cycle de vie du parsing d'un CV importé (openapi.yaml → CvDocument.status). */
export type CvDocumentStatus = "uploaded" | "parsing" | "parsed" | "failed";

/** Code d'échec du parsing (openapi.yaml → CvDocument.error_code) — message dédié par code (04 Flux 1). */
export type CvErrorCode =
  | "unreadable"
  | "image_only_pdf"
  | "too_large"
  | "unsupported_format"
  | "extraction_failed";

/**
 * Champs communs d'un élément proposé à la revue (payload `parsed`, groupé) :
 * `item_id` de sélection (`"experience:0"`…) à renvoyer à
 * `POST /cv-documents/{id}/apply`, provenance `cv_extraction` avec confiance
 * (< 0,5 : décoché par défaut et marqué « À vérifier », 06 §1 / M3-d) et
 * citation du CV justifiant l'extraction (`null` si non disponible).
 */
export interface CvProposalItemBase {
  item_id: string;
  provenance: Provenance;
  evidence_quote: string | null;
}

/** Expérience proposée par l'extraction (mêmes champs que {@link ExperienceInput}). */
export interface CvProposedExperience extends CvProposalItemBase {
  title: string;
  company: string;
  /** Date ISO `YYYY-MM-DD`. */
  start_date: string;
  /** `null` = poste en cours. */
  end_date: string | null;
  description: string | null;
}

/** Formation proposée par l'extraction (mêmes champs que {@link EducationInput}). */
export interface CvProposedEducation extends CvProposalItemBase {
  degree: string;
  institution: string;
  start_year: number | null;
  end_year: number | null;
}

/** Compétence proposée par l'extraction. */
export interface CvProposedSkill extends CvProposalItemBase {
  label: string;
}

/** Langue proposée par l'extraction (niveau CECRL). */
export interface CvProposedLanguage extends CvProposalItemBase {
  lang_code: string;
  level: CefrLevel;
}

/**
 * Proposition d'extraction GROUPÉE — `GET /cv-documents/{id}` (`status=parsed`).
 * `headline`/`summary` sont proposés à part (cases dédiées `include_headline` /
 * `include_summary`, sans `item_id`) ; les listes portent les `item_id` cochés
 * à renvoyer à `POST /cv-documents/{id}/apply`.
 */
export interface CvProposal {
  headline: string | null;
  summary: string | null;
  experiences: CvProposedExperience[];
  educations: CvProposedEducation[];
  skills: CvProposedSkill[];
  languages: CvProposedLanguage[];
}

/** Document CV importé — `POST /cv-documents` (202) puis `GET /cv-documents/{id}` (polling). */
export interface CvDocument {
  id: string;
  filename: string;
  status: CvDocumentStatus;
  error_code?: CvErrorCode | null;
  /** Sections partiellement extraites (`status=parsed`) — bandeau « À vérifier » (04 Flux 1). */
  extraction_warnings?: string[];
  /** Proposition groupée à revoir (`status=parsed`) — voir {@link CvProposal}. */
  proposal?: CvProposal;
  /** Identifiant de corrélation problem+json, exposé en détail repliable. */
  trace_id?: string;
}

/**
 * Corps de `POST /cv-documents/{id}/apply` — applique au profil les seuls
 * éléments cochés lors de la revue. `item_ids: null` (ou absent) = tout
 * appliquer ; `include_headline`/`include_summary` pilotent les deux champs
 * racine proposés hors liste. L'existant `user_input`/`user_confirmed` n'est
 * jamais écrasé (03 Q4 : jamais d'écrasement automatique).
 */
export interface CvApplyInput {
  item_ids: string[] | null;
  include_headline: boolean;
  include_summary: boolean;
}

/* ------------------------------------------------------------------ */
/* Générations — jalon M4 (openapi.yaml : /generations*)               */
/* ------------------------------------------------------------------ */

/** Type de contenu généré (openapi.yaml → GeneratedDocument.doc_type). */
export type DocType = "email" | "cover_letter" | "cv_variant" | "cv_optimization";

/** Cycle de vie d'une génération (openapi.yaml → GeneratedDocument.status, D10). */
export type GenerationStatus = "pending" | "draft" | "validated" | "exported" | "failed";

/** Ton de rédaction (openapi.yaml → options.tone — valeurs API en français). */
export type GenerationTone = "sobre" | "chaleureux" | "direct";

/** Langue de rédaction (openapi.yaml → options.language). */
export type GenerationLanguage = "fr" | "en";

/** Longueur cible (openapi.yaml → options.length — valeurs API en français). */
export type GenerationLength = "court" | "standard";

/** Options de génération (SCR-30). */
export interface GenerationOptions {
  tone?: GenerationTone;
  language?: GenerationLanguage;
  length?: GenerationLength;
}

/** Affirmation ancrée du contenu généré, reliée à sa source profil (12 §4). */
export interface GenerationClaim {
  claim: string;
  /** Référence profil, ex. `experience:2f00…` — lien « Voir la source ». */
  profile_ref: string;
}

/**
 * 🟡 Changement proposé par une variante de CV (Flux 6, question ouverte Q6 :
 * granularité du diff non contractualisée — champs supposés de `content.changes`).
 */
export interface CvVariantChange {
  /** Section du CV concernée (ex. « Expériences »). */
  section: string;
  kind: "emphasized" | "reworded" | "removed";
  /** Texte du canonique (`null` pour un simple réordonnancement). */
  before?: string | null;
  /** Texte de la variante (`null` pour un retrait). */
  after?: string | null;
}

/**
 * Contenu d'une génération (openapi.yaml → GeneratedDocument.content, objet
 * libre — champs connus d'après l'exemple 12 §4 ; `changes` 🟡 pour le diff CV).
 */
export interface GeneratedContent {
  body?: string;
  claims?: GenerationClaim[];
  /** 🟡 Diff par changement des variantes CV (Flux 6 §3). */
  changes?: CvVariantChange[];
  [extra: string]: unknown;
}

/** Contrôle d'ancrage (openapi.yaml → GeneratedDocument.anchoring_check). */
export interface AnchoringCheck {
  status: "passed" | "failed";
  unanchored_claims: string[];
}

/** Document généré — `GET /generations/{id}` (openapi.yaml → GeneratedDocument). */
export interface GeneratedDocument {
  id: string;
  doc_type: DocType;
  status: GenerationStatus;
  based_on_profile_version: number;
  prompt_version: string;
  content: GeneratedContent | null;
  /** `null` = contrôle non disponible (génération en cours, ou document édité manuellement). */
  anchoring_check: AnchoringCheck | null;
  /** 🟡 Offre cible — présent car `GET /generations?job_id=` filtre dessus (openapi.yaml). */
  job_id?: string | null;
  /** 🟡 Candidature liée le cas échéant. */
  application_id?: string | null;
  /** 🟡 Date de création (affichage bibliothèque) — non listée dans le schéma. */
  created_at?: string | null;
  /**
   * 🟡 Options de rédaction retenues à la création (ton / langue / longueur).
   * Portées par la table `generations` côté API mais PAS encore par
   * `GeneratedDocumentOut` : traitées comme optionnelles — « Réessayer » les
   * rejoue si elles arrivent, et retombe sinon sur les défauts serveur.
   */
  options?: GenerationOptions | null;
  /**
   * Code d'échec de la génération (`status = failed`) — champ additif exposé
   * par `GeneratedDocumentOut`, affiché dans le message d'échec (SCR-31).
   */
  error_code?: string | null;
}

/** Corps de `POST /generations` (Idempotency-Key requis, 12 §1). */
export interface GenerationCreateInput {
  doc_type: DocType;
  /** Requis sauf `cv_optimization` (openapi.yaml). */
  job_id?: string | null;
  application_id?: string | null;
  options?: GenerationOptions;
}

/** Réponse de `POST /generations/{id}/export` (texte inline ou lien signé 7 j). */
export interface GenerationExport {
  format: "text" | "pdf" | "docx";
  content: string | null;
  download_url: string | null;
}

/* ------------------------------------------------------------------ */
/* Candidatures — jalon M4 (openapi.yaml : /applications*)             */
/* ------------------------------------------------------------------ */

/** Statut d'une candidature (openapi.yaml → ApplicationStatus, ordre du flux 7). */
export type ApplicationStatus =
  | "draft"
  | "to_apply"
  | "applied"
  | "interviewing"
  | "offer"
  | "rejected"
  | "withdrawn";

/**
 * Corps de `POST /applications` — offre interne (`job_posting_id`) OU externe
 * (`external_title` + `external_company`, 11 §5).
 */
export interface ApplicationInput {
  job_posting_id?: string | null;
  external_title?: string | null;
  external_company?: string | null;
  external_url?: string | null;
  notes?: string | null;
}

/** Transition historisée d'une candidature (openapi.yaml → Application.events[]). */
export interface ApplicationEvent {
  from_status: ApplicationStatus | null;
  to_status: ApplicationStatus;
  at: string;
  note: string | null;
}

/** Candidature suivie (openapi.yaml → Application, allOf ApplicationInput). */
export interface Application extends ApplicationInput {
  id: string;
  status: ApplicationStatus;
  applied_at: string | null;
  events: ApplicationEvent[];
  /** 🟡 Intitulé de l'offre interne, dénormalisé par l'API (carte SCR-40 : poste + entreprise). */
  job_title?: string | null;
  /** 🟡 Entreprise de l'offre interne, dénormalisée par l'API. */
  job_company?: string | null;
}

/** Corps de `POST /applications/{id}/status` (transition historisée). */
export interface ApplicationStatusChange {
  to_status: ApplicationStatus;
  /** Note optionnelle ≤ 1000 caractères, historisée avec la transition. */
  note?: string | null;
}

/* ------------------------------------------------------------------ */
/* Confidentialité & données — jalon M5 (openapi.yaml : /privacy/*,    */
/* /account — feature Q, D09)                                          */
/* ------------------------------------------------------------------ */

/**
 * Statut d'un export RGPD (openapi.yaml → `/privacy/exports/{id}`).
 * « expired » est dérivé côté API de la date d'expiration du lien (7 jours) —
 * jamais stocké (router privacy `_effective_status`).
 */
export type PrivacyExportStatus = "pending" | "ready" | "expired";

/** Réponse 202 de `POST /privacy/export` (export asynchrone, quota 2/j). */
export interface PrivacyExportRequested {
  id: string;
  status: PrivacyExportStatus;
}

/**
 * Statut de l'export — `GET /privacy/exports/{id}`. `download_url` n'est
 * présent qu'à `ready` : URL relative signée HMAC servie par
 * `GET /privacy/exports/{id}/download?expires=…&sig=…` (même origine via le
 * proxy Next, préfixe `/api/v1` inclus côté API — à utiliser telle quelle).
 */
export interface PrivacyExportStatusResponse extends PrivacyExportRequested {
  download_url?: string | null;
}

/** Corps de `DELETE /account` — confirmation par mot de passe (RM-Q-4). */
export interface DeleteAccountInput {
  password: string;
}
