-- Boussole — schéma initial PostgreSQL 16
-- Migration Alembic 0001. Extensions requises : vector, pg_trgm, unaccent, citext.
-- Dimension embedding 1024 (hypothèse — voir 08-ai-specification.md).

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS unaccent;
CREATE EXTENSION IF NOT EXISTS citext;

-- ---------- Enums ----------
CREATE TYPE field_source AS ENUM ('cv_extraction', 'user_input', 'user_confirmed');
CREATE TYPE profile_status AS ENUM ('draft', 'validated');
CREATE TYPE seniority_level AS ENUM ('intern','junior','mid','senior','lead','principal','executive');
CREATE TYPE contract_type AS ENUM ('permanent','fixed_term','freelance','internship','apprenticeship','other');
CREATE TYPE remote_policy AS ENUM ('onsite','hybrid','full_remote');
CREATE TYPE remote_preference AS ENUM ('required','preferred','indifferent','onsite_preferred');
CREATE TYPE cefr_level AS ENUM ('A1','A2','B1','B2','C1','C2');
CREATE TYPE cv_status AS ENUM ('uploaded','parsing','parsed','failed');
CREATE TYPE job_status AS ENUM ('active','expired','withdrawn');
CREATE TYPE saved_state AS ENUM ('saved','hidden');
CREATE TYPE application_status AS ENUM ('draft','to_apply','applied','interviewing','offer','rejected','withdrawn');
CREATE TYPE generated_doc_type AS ENUM ('email','cover_letter','cv_variant','cv_optimization');
CREATE TYPE generated_doc_status AS ENUM ('draft','validated','exported');
CREATE TYPE ai_task AS ENUM ('extract_cv','extract_job','explain_match','generate_email','generate_letter','tailor_cv','optimize_cv');
CREATE TYPE deletion_status AS ENUM ('pending','purged');

-- ---------- Identité ----------
CREATE TABLE users (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  email         citext NOT NULL UNIQUE,
  password_hash text,                          -- NULL si OAuth (post-MVP)
  locale        text NOT NULL DEFAULT 'fr',
  created_at    timestamptz NOT NULL DEFAULT now(),
  updated_at    timestamptz NOT NULL DEFAULT now(),
  deleted_at    timestamptz
);

CREATE TABLE consents (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id    uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  kind       text NOT NULL,                    -- 'terms','privacy','ai_debug_sampling'
  version    text NOT NULL,
  granted_at timestamptz NOT NULL DEFAULT now(),
  revoked_at timestamptz
);

CREATE TABLE deletion_requests (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id      uuid NOT NULL REFERENCES users(id),
  requested_at timestamptz NOT NULL DEFAULT now(),
  purge_after  timestamptz NOT NULL,           -- requested_at + 30 jours
  status       deletion_status NOT NULL DEFAULT 'pending'
);

CREATE TABLE audit_log (
  id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  user_id     uuid REFERENCES users(id) ON DELETE SET NULL,
  subject_key text,                            -- hash irréversible conservé après purge
  action      text NOT NULL,
  entity      text,
  entity_id   uuid,
  at          timestamptz NOT NULL DEFAULT now(),
  meta        jsonb NOT NULL DEFAULT '{}'
);

-- ---------- Référentiels ----------
CREATE TABLE skills (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  canonical_label text NOT NULL UNIQUE,
  esco_id         text,
  embedding       vector(1024)
);

CREATE TABLE skill_aliases (
  alias    citext PRIMARY KEY,
  skill_id uuid NOT NULL REFERENCES skills(id) ON DELETE CASCADE
);

CREATE TABLE sectors (
  code       text PRIMARY KEY,                 -- NACE simplifié
  label_fr   text NOT NULL,
  label_en   text NOT NULL,
  parent_code text REFERENCES sectors(code)
);

-- ---------- Profil ----------
CREATE TABLE cv_documents (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  file_key    text NOT NULL,                   -- clé S3
  filename    text NOT NULL,
  mime_type   text NOT NULL,
  size_bytes  int  NOT NULL CHECK (size_bytes <= 10*1024*1024),
  status      cv_status NOT NULL DEFAULT 'uploaded',
  raw_text_key text,                           -- texte extrait, S3
  error_code  text,
  created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE profiles (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id         uuid NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
  status          profile_status NOT NULL DEFAULT 'draft',
  version         int NOT NULL DEFAULT 1,
  headline        text,
  summary         text,
  seniority       seniority_level,
  total_experience_years numeric(4,1),
  embedding       vector(1024),
  source_cv_id    uuid REFERENCES cv_documents(id) ON DELETE SET NULL,
  validated_at    timestamptz,
  updated_at      timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE extraction_runs (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  cv_document_id uuid NOT NULL REFERENCES cv_documents(id) ON DELETE CASCADE,
  prompt_version text NOT NULL,
  model          text NOT NULL,
  status         text NOT NULL,                -- 'success','schema_error','failed'
  output_key     text,                         -- JSON brut validé, S3
  created_at     timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE profile_experiences (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  profile_id  uuid NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
  title       text NOT NULL,
  company     text NOT NULL,
  sector_code text REFERENCES sectors(code),
  start_date  date NOT NULL,
  end_date    date,                            -- NULL = en cours
  description text,
  position    int NOT NULL DEFAULT 0,
  source      field_source NOT NULL,
  confidence  numeric(3,2) NOT NULL DEFAULT 1 CHECK (confidence BETWEEN 0 AND 1),
  CHECK (end_date IS NULL OR end_date >= start_date)
);

CREATE TABLE profile_educations (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  profile_id uuid NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
  degree     text NOT NULL,
  institution text NOT NULL,
  start_year int,
  end_year   int,
  source     field_source NOT NULL,
  confidence numeric(3,2) NOT NULL DEFAULT 1 CHECK (confidence BETWEEN 0 AND 1)
);

CREATE TABLE profile_skills (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  profile_id uuid NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
  skill_id   uuid REFERENCES skills(id),
  label_raw  text NOT NULL,
  source     field_source NOT NULL,
  confidence numeric(3,2) NOT NULL DEFAULT 1 CHECK (confidence BETWEEN 0 AND 1),
  UNIQUE (profile_id, skill_id)
);

CREATE TABLE profile_languages (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  profile_id uuid NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
  lang_code  text NOT NULL,                    -- ISO 639-1
  level      cefr_level NOT NULL,
  source     field_source NOT NULL,
  confidence numeric(3,2) NOT NULL DEFAULT 1 CHECK (confidence BETWEEN 0 AND 1),
  UNIQUE (profile_id, lang_code)
);

-- ---------- Préférences ----------
CREATE TABLE preferences (
  user_id           uuid PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
  remote_pref       remote_preference NOT NULL DEFAULT 'indifferent',
  contract_types    contract_type[] NOT NULL DEFAULT '{permanent}',
  contract_strict   boolean NOT NULL DEFAULT false,
  salary_min        int,                       -- souhaité, EUR brut annuel
  salary_min_strict int,                       -- rédhibitoire
  salary_currency   text NOT NULL DEFAULT 'EUR',
  updated_at        timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE preference_locations (
  id        uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id   uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  label     text NOT NULL,
  lat       double precision NOT NULL,
  lon       double precision NOT NULL,
  radius_km int NOT NULL DEFAULT 30
);

CREATE TABLE preference_titles (
  id        uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id   uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  title     text NOT NULL,
  embedding vector(1024)
);

CREATE TABLE preference_sectors (
  user_id     uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  sector_code text NOT NULL REFERENCES sectors(code),
  mode        text NOT NULL CHECK (mode IN ('preferred','excluded')),
  PRIMARY KEY (user_id, sector_code)
);

CREATE TABLE preference_companies (
  user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  name    citext NOT NULL,
  PRIMARY KEY (user_id, name)
);

CREATE TABLE preference_keywords (
  user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  keyword citext NOT NULL,
  PRIMARY KEY (user_id, keyword)
);

-- ---------- Offres ----------
CREATE TABLE sources (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  slug        text NOT NULL UNIQUE,            -- 'france-travail','greenhouse',…
  name        text NOT NULL,
  kind        text NOT NULL,                   -- 'public_api','ats_feed','partner'
  legal_basis text NOT NULL,                   -- fiche de conformité (résumé + lien)
  terms_url   text,
  active      boolean NOT NULL DEFAULT false,
  created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE job_postings (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  dedup_hash     text NOT NULL UNIQUE,
  title          text NOT NULL,
  company_name   text NOT NULL,
  sector_code    text REFERENCES sectors(code),
  description_text text NOT NULL,
  language       text NOT NULL DEFAULT 'fr',
  seniority      seniority_level,
  seniority_conf numeric(3,2),
  experience_min numeric(4,1),
  experience_max numeric(4,1),
  contract       contract_type,
  contract_conf  numeric(3,2),
  remote         remote_policy,
  remote_conf    numeric(3,2),
  salary_min     int,
  salary_max     int,
  salary_currency text,
  salary_period  text CHECK (salary_period IN ('year','month','day','hour')),
  status         job_status NOT NULL DEFAULT 'active',
  country_code   text,
  first_seen_at  timestamptz NOT NULL DEFAULT now(),
  last_seen_at   timestamptz NOT NULL DEFAULT now(),
  expires_at     timestamptz,
  embedding      vector(1024),
  tsv            tsvector,
  extraction_prompt_version text
);

CREATE TABLE job_sources (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  job_posting_id  uuid NOT NULL REFERENCES job_postings(id) ON DELETE CASCADE,
  source_id       uuid NOT NULL REFERENCES sources(id),
  external_ref    text NOT NULL,
  original_url    text NOT NULL,               -- garantie produit : lien d'origine conservé
  posted_at       timestamptz,
  ingested_at     timestamptz NOT NULL DEFAULT now(),
  raw_payload_key text,                        -- S3
  UNIQUE (source_id, external_ref)
);

CREATE TABLE job_locations (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  job_posting_id uuid NOT NULL REFERENCES job_postings(id) ON DELETE CASCADE,
  raw_label      text NOT NULL,
  lat            double precision,
  lon            double precision,
  country_code   text
);

CREATE TABLE job_skills (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  job_posting_id uuid NOT NULL REFERENCES job_postings(id) ON DELETE CASCADE,
  skill_id       uuid REFERENCES skills(id),
  label_raw      text NOT NULL,
  required       boolean NOT NULL DEFAULT true,
  confidence     numeric(3,2) NOT NULL CHECK (confidence BETWEEN 0 AND 1)
);

CREATE TABLE job_languages (
  job_posting_id uuid NOT NULL REFERENCES job_postings(id) ON DELETE CASCADE,
  lang_code      text NOT NULL,
  min_level      cefr_level NOT NULL,
  confidence     numeric(3,2) NOT NULL CHECK (confidence BETWEEN 0 AND 1),
  PRIMARY KEY (job_posting_id, lang_code)
);

-- ---------- Matching ----------
CREATE TABLE match_results (
  profile_id         uuid NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
  job_posting_id     uuid NOT NULL REFERENCES job_postings(id) ON DELETE CASCADE,
  scoring_version    text NOT NULL,
  score              smallint NOT NULL CHECK (score BETWEEN 0 AND 100),
  confidence         smallint NOT NULL CHECK (confidence BETWEEN 0 AND 100),
  low_data           boolean NOT NULL DEFAULT false,
  blocking_criteria  jsonb NOT NULL DEFAULT '[]',
  unknown_dimensions jsonb NOT NULL DEFAULT '[]',
  dimension_scores   jsonb NOT NULL DEFAULT '[]',
  computed_at        timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (profile_id, job_posting_id)
);

CREATE TABLE match_explanations (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  profile_id     uuid NOT NULL,
  job_posting_id uuid NOT NULL,
  scoring_version text NOT NULL,
  prompt_version text NOT NULL,
  content        jsonb NOT NULL,               -- schéma match_explanation
  created_at     timestamptz NOT NULL DEFAULT now(),
  FOREIGN KEY (profile_id, job_posting_id) REFERENCES match_results(profile_id, job_posting_id) ON DELETE CASCADE,
  UNIQUE (profile_id, job_posting_id, scoring_version, prompt_version)
);

-- ---------- Actions utilisateur ----------
CREATE TABLE saved_jobs (
  user_id        uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  job_posting_id uuid NOT NULL REFERENCES job_postings(id) ON DELETE CASCADE,
  state          saved_state NOT NULL,
  created_at     timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (user_id, job_posting_id)
);

CREATE TABLE applications (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id          uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  job_posting_id   uuid REFERENCES job_postings(id) ON DELETE SET NULL,
  external_title   text,
  external_company text,
  external_url     text,
  status           application_status NOT NULL DEFAULT 'draft',
  applied_at       timestamptz,
  notes            text,
  created_at       timestamptz NOT NULL DEFAULT now(),
  updated_at       timestamptz NOT NULL DEFAULT now(),
  CHECK (job_posting_id IS NOT NULL OR (external_title IS NOT NULL AND external_company IS NOT NULL))
);

CREATE TABLE application_events (
  id             bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  application_id uuid NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
  from_status    application_status,
  to_status      application_status NOT NULL,
  note           text,
  at             timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE generated_documents (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id        uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  application_id uuid REFERENCES applications(id) ON DELETE SET NULL,
  job_posting_id uuid REFERENCES job_postings(id) ON DELETE SET NULL,
  doc_type       generated_doc_type NOT NULL,
  status         generated_doc_status NOT NULL DEFAULT 'draft',
  content        jsonb NOT NULL,
  based_on_profile_version int NOT NULL,
  prompt_version text NOT NULL,
  created_at     timestamptz NOT NULL DEFAULT now(),
  validated_at   timestamptz,
  CHECK (status <> 'exported' OR validated_at IS NOT NULL)
);

-- ---------- IA ----------
CREATE TABLE prompt_versions (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  task          ai_task NOT NULL,
  version       text NOT NULL,
  template_key  text NOT NULL,                 -- S3 / repo
  default_model text NOT NULL,
  active        boolean NOT NULL DEFAULT false,
  created_at    timestamptz NOT NULL DEFAULT now(),
  UNIQUE (task, version)
);

CREATE TABLE ai_calls (
  id             bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  task           ai_task NOT NULL,
  prompt_version text NOT NULL,
  model          text NOT NULL,
  user_id        uuid REFERENCES users(id) ON DELETE SET NULL,
  input_tokens   int,
  output_tokens  int,
  latency_ms     int,
  status         text NOT NULL,                -- 'success','schema_retry','failed'
  error_code     text,
  created_at     timestamptz NOT NULL DEFAULT now()
);

-- ---------- Index ----------
CREATE INDEX idx_users_active ON users (id) WHERE deleted_at IS NULL;
CREATE INDEX idx_jobs_tsv ON job_postings USING gin (tsv);
CREATE INDEX idx_jobs_embedding ON job_postings USING hnsw (embedding vector_cosine_ops);
CREATE INDEX idx_jobs_active_country ON job_postings (country_code, last_seen_at DESC) WHERE status = 'active';
CREATE INDEX idx_jobs_title_trgm ON job_postings USING gin (title gin_trgm_ops);
CREATE INDEX idx_jobs_company_trgm ON job_postings USING gin (company_name gin_trgm_ops);
CREATE INDEX idx_match_by_score ON match_results (profile_id, score DESC) WHERE blocking_criteria = '[]';
CREATE INDEX idx_match_job ON match_results (job_posting_id);
CREATE INDEX idx_applications_user ON applications (user_id, status);
CREATE INDEX idx_saved_user ON saved_jobs (user_id, state);
CREATE INDEX idx_job_skills_job ON job_skills (job_posting_id);
CREATE INDEX idx_ai_calls_task_time ON ai_calls (task, created_at);

-- tsvector maintenu par trigger
CREATE FUNCTION job_postings_tsv_update() RETURNS trigger AS $$
BEGIN
  NEW.tsv :=
    setweight(to_tsvector(CASE WHEN NEW.language = 'fr' THEN 'french' ELSE 'english' END::regconfig, unaccent(coalesce(NEW.title,''))), 'A') ||
    setweight(to_tsvector(CASE WHEN NEW.language = 'fr' THEN 'french' ELSE 'english' END::regconfig, unaccent(coalesce(NEW.company_name,''))), 'B') ||
    setweight(to_tsvector(CASE WHEN NEW.language = 'fr' THEN 'french' ELSE 'english' END::regconfig, unaccent(coalesce(NEW.description_text,''))), 'C');
  RETURN NEW;
END $$ LANGUAGE plpgsql;

CREATE TRIGGER trg_job_postings_tsv BEFORE INSERT OR UPDATE OF title, company_name, description_text, language
ON job_postings FOR EACH ROW EXECUTE FUNCTION job_postings_tsv_update();
