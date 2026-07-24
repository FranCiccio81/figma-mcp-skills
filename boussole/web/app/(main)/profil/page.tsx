"use client";

// SCR-50 — M3
// Profil canonique (Flux 1 §4–6) : sections infos / expériences / formations /
// compétences / langues avec badge de provenance par champ (M3-d — affiché
// uniquement pour `cv_extraction`), édition inline RHF+Zod par expansion,
// ajout/suppression, CTA « Valider mon profil » (préconditions ≥ 3
// compétences ET ≥ 1 expérience ou formation ; 409 → messages ciblés).
// Toute mutation invalide les caches match : le score dépend du profil.

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import clsx from "clsx";
import { Plus } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { useCallback, useId, useMemo, useRef, useState, type TextareaHTMLAttributes } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { ProvenanceBadge } from "@/components/profile/provenance-badge";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { FormField, fieldDescribedBy } from "@/components/ui/form-field";
import { Input } from "@/components/ui/input";
import { isApiProblem } from "@/lib/api/client";
import { invalidateMatchDependentQueries } from "@/lib/api/matching";
import {
  createEducation,
  createExperience,
  createLanguage,
  createSkill,
  deleteEducation,
  deleteExperience,
  deleteLanguage,
  deleteSkill,
  getProfile,
  patchProfile,
  profileKeys,
  updateEducation,
  updateExperience,
  updateLanguage,
  validateProfile,
} from "@/lib/api/profile";
import type {
  CefrLevel,
  Education,
  EducationInput,
  Experience,
  ExperienceInput,
  Profile,
  SeniorityLevel,
} from "@/lib/api/types";
import { formatDate } from "@/lib/format";

/** Préconditions de `POST /profile/validate` (openapi.yaml). */
const VALIDATE_MIN_SKILLS = 3;

const SENIORITY_OPTIONS: SeniorityLevel[] = [
  "intern",
  "junior",
  "mid",
  "senior",
  "lead",
  "principal",
  "executive",
];

const CEFR_LEVELS: CefrLevel[] = ["A1", "A2", "B1", "B2", "C1", "C2"];

/** Zone de texte alignée sur les tokens de `Input` (résumé, descriptions). */
function Textarea(props: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  const { className, ...rest } = props;
  return (
    <textarea
      className={clsx(
        "min-h-24 w-full rounded-md border border-border bg-surface px-3 py-2 text-sm text-content",
        "placeholder:text-content-secondary",
        "focus:border-action-primary focus:shadow-input-focus focus:outline-none",
        "disabled:cursor-not-allowed disabled:opacity-50",
        "aria-[invalid=true]:border-feedback-error",
        className,
      )}
      {...rest}
    />
  );
}

/** Classe partagée des `select` (mêmes tokens que `Input`). */
const selectClass =
  "h-11 w-full rounded-md border border-border bg-surface px-3 text-sm text-content focus:border-action-primary focus:shadow-input-focus focus:outline-none disabled:cursor-not-allowed disabled:opacity-50";

/** Message d'erreur générique d'une mutation (422 mappé en amont si possible). */
function mutationErrorMessage(error: unknown, fallback: string): string {
  if (isApiProblem(error)) {
    if (error.errors.length > 0) return error.errors.map((e) => e.message).join(" ");
    if (error.detail) return error.detail;
  }
  return fallback;
}

/** En-tête de section avec action « Ajouter » optionnelle. */
function SectionCard({
  titleId,
  title,
  action,
  children,
}: {
  titleId: string;
  title: string;
  action?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section
      aria-labelledby={titleId}
      className="space-y-4 rounded-lg border border-border bg-surface p-4"
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 id={titleId} className="text-lg font-semibold text-content">
          {title}
        </h2>
        {action}
      </div>
      {children}
    </section>
  );
}

/* ------------------------------------------------------------------ */
/* Infos racine (headline, résumé, séniorité) — PATCH /profile         */
/* ------------------------------------------------------------------ */

function RootInfoSection({
  profile,
  onChanged,
}: {
  profile: Profile;
  onChanged: (announcementKey: "saved" | "deleted") => void;
}) {
  const t = useTranslations("profile");
  const tJobs = useTranslations("jobs");
  const baseId = useId();
  const [editing, setEditing] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);

  const schema = useMemo(
    () =>
      z.object({
        headline: z.string().max(200),
        summary: z.string().max(2000),
        seniority: z.union([z.enum(SENIORITY_OPTIONS as [SeniorityLevel, ...SeniorityLevel[]]), z.literal("")]),
      }),
    [],
  );
  type FormValues = z.infer<typeof schema>;

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    values: {
      headline: profile.headline ?? "",
      summary: profile.summary ?? "",
      seniority: profile.seniority ?? "",
    },
  });

  const mutation = useMutation({
    mutationFn: (values: FormValues) =>
      patchProfile({
        headline: values.headline.trim() || null,
        summary: values.summary.trim() || null,
        seniority: values.seniority === "" ? null : values.seniority,
      }),
    onSuccess: () => {
      setEditing(false);
      setServerError(null);
      onChanged("saved");
    },
    onError: (error) => setServerError(mutationErrorMessage(error, t("actionError"))),
  });

  const headlineId = `${baseId}-headline`;
  const summaryId = `${baseId}-summary`;
  const seniorityId = `${baseId}-seniority`;

  return (
    <SectionCard
      titleId={`${baseId}-title`}
      title={t("info.title")}
      action={
        !editing ? (
          <Button variant="secondary" onClick={() => setEditing(true)}>
            {t("actions.edit")}
          </Button>
        ) : undefined
      }
    >
      {editing ? (
        <form
          noValidate
          onSubmit={handleSubmit((values) => mutation.mutate(values))}
          className="space-y-4"
        >
          {serverError ? <Alert variant="error">{serverError}</Alert> : null}
          <FormField id={headlineId} label={t("info.headlineLabel")} error={errors.headline?.message}>
            <Input
              id={headlineId}
              aria-invalid={errors.headline ? true : undefined}
              aria-describedby={fieldDescribedBy(headlineId, { error: Boolean(errors.headline) })}
              {...register("headline")}
            />
          </FormField>
          <FormField id={summaryId} label={t("info.summaryLabel")} error={errors.summary?.message}>
            <Textarea
              id={summaryId}
              aria-invalid={errors.summary ? true : undefined}
              aria-describedby={fieldDescribedBy(summaryId, { error: Boolean(errors.summary) })}
              {...register("summary")}
            />
          </FormField>
          <FormField id={seniorityId} label={t("info.seniorityLabel")}>
            <select id={seniorityId} className={selectClass} {...register("seniority")}>
              <option value="">{t("info.notProvided")}</option>
              {SENIORITY_OPTIONS.map((level) => (
                <option key={level} value={level}>
                  {tJobs(`seniority.${level}`)}
                </option>
              ))}
            </select>
          </FormField>
          <div className="flex flex-wrap gap-3">
            <Button type="submit" disabled={mutation.isPending} aria-busy={mutation.isPending}>
              {t("actions.save")}
            </Button>
            <Button
              variant="secondary"
              onClick={() => {
                reset();
                setServerError(null);
                setEditing(false);
              }}
            >
              {t("actions.cancel")}
            </Button>
          </div>
        </form>
      ) : (
        <dl className="grid gap-x-8 gap-y-3 text-sm sm:grid-cols-2">
          <div>
            <dt className="font-medium text-content">{t("info.headlineLabel")}</dt>
            <dd className="text-content-secondary">{profile.headline || t("info.notProvided")}</dd>
          </div>
          <div>
            <dt className="font-medium text-content">{t("info.seniorityLabel")}</dt>
            <dd className="text-content-secondary">
              {profile.seniority ? tJobs(`seniority.${profile.seniority}`) : t("info.notProvided")}
            </dd>
          </div>
          <div className="sm:col-span-2">
            <dt className="font-medium text-content">{t("info.summaryLabel")}</dt>
            <dd className="whitespace-pre-wrap text-content-secondary">
              {profile.summary || t("info.notProvided")}
            </dd>
          </div>
          {profile.total_experience_years !== null ? (
            <div className="sm:col-span-2">
              <dt className="font-medium text-content">{t("info.totalYearsLabel")}</dt>
              <dd className="text-content-secondary">
                {t("info.totalYears", { years: profile.total_experience_years })}
              </dd>
            </div>
          ) : null}
        </dl>
      )}
    </SectionCard>
  );
}

/* ------------------------------------------------------------------ */
/* Expériences / Formations — formulaires RHF+Zod en expansion         */
/* ------------------------------------------------------------------ */

function ExperienceForm({
  initial,
  pending,
  serverError,
  onSubmit,
  onCancel,
}: {
  initial?: Experience;
  pending: boolean;
  serverError: string | null;
  onSubmit: (values: ExperienceInput) => void;
  onCancel: () => void;
}) {
  const t = useTranslations("profile.experiences");
  const tv = useTranslations("validation");
  const tActions = useTranslations("profile.actions");
  const baseId = useId();

  const schema = useMemo(
    () =>
      z.object({
        title: z.string().min(1, tv("required")).max(200),
        company: z.string().min(1, tv("required")).max(200),
        start_date: z.string().min(1, tv("required")),
        end_date: z.string(),
        description: z.string().max(3000),
      }),
    [tv],
  );
  type FormValues = z.infer<typeof schema>;

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      title: initial?.title ?? "",
      company: initial?.company ?? "",
      start_date: initial?.start_date ?? "",
      end_date: initial?.end_date ?? "",
      description: initial?.description ?? "",
    },
  });

  const ids = {
    title: `${baseId}-title`,
    company: `${baseId}-company`,
    start: `${baseId}-start`,
    end: `${baseId}-end`,
    description: `${baseId}-description`,
  };

  return (
    <form
      noValidate
      onSubmit={handleSubmit((values) =>
        onSubmit({
          title: values.title.trim(),
          company: values.company.trim(),
          start_date: values.start_date,
          end_date: values.end_date || null,
          description: values.description.trim() || null,
        }),
      )}
      className="space-y-4 rounded-md border border-border bg-surface-muted p-4"
    >
      {serverError ? <Alert variant="error">{serverError}</Alert> : null}
      <div className="grid gap-4 sm:grid-cols-2">
        <FormField id={ids.title} label={t("form.titleLabel")} required error={errors.title?.message}>
          <Input
            id={ids.title}
            autoFocus
            aria-invalid={errors.title ? true : undefined}
            aria-describedby={fieldDescribedBy(ids.title, { error: Boolean(errors.title) })}
            {...register("title")}
          />
        </FormField>
        <FormField
          id={ids.company}
          label={t("form.companyLabel")}
          required
          error={errors.company?.message}
        >
          <Input
            id={ids.company}
            aria-invalid={errors.company ? true : undefined}
            aria-describedby={fieldDescribedBy(ids.company, { error: Boolean(errors.company) })}
            {...register("company")}
          />
        </FormField>
        <FormField
          id={ids.start}
          label={t("form.startLabel")}
          required
          error={errors.start_date?.message}
        >
          <Input
            id={ids.start}
            type="date"
            aria-invalid={errors.start_date ? true : undefined}
            aria-describedby={fieldDescribedBy(ids.start, { error: Boolean(errors.start_date) })}
            {...register("start_date")}
          />
        </FormField>
        <FormField id={ids.end} label={t("form.endLabel")} description={t("form.endHint")}>
          <Input
            id={ids.end}
            type="date"
            aria-describedby={fieldDescribedBy(ids.end, { description: true })}
            {...register("end_date")}
          />
        </FormField>
      </div>
      <FormField
        id={ids.description}
        label={t("form.descriptionLabel")}
        error={errors.description?.message}
      >
        <Textarea id={ids.description} {...register("description")} />
      </FormField>
      <div className="flex flex-wrap gap-3">
        <Button type="submit" disabled={pending} aria-busy={pending}>
          {tActions("save")}
        </Button>
        <Button variant="secondary" onClick={onCancel}>
          {tActions("cancel")}
        </Button>
      </div>
    </form>
  );
}

function ExperiencesSection({
  profile,
  onChanged,
}: {
  profile: Profile;
  onChanged: (announcementKey: "saved" | "deleted") => void;
}) {
  const t = useTranslations("profile.experiences");
  const tProfile = useTranslations("profile");
  const locale = useLocale();
  const baseId = useId();
  const [editingId, setEditingId] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);
  const [listError, setListError] = useState<string | null>(null);

  const saveMutation = useMutation({
    mutationFn: ({ id, input }: { id: string | null; input: ExperienceInput }) =>
      id ? updateExperience(id, input) : createExperience(input),
    onSuccess: () => {
      setEditingId(null);
      setAdding(false);
      setServerError(null);
      onChanged("saved");
    },
    onError: (error) => setServerError(mutationErrorMessage(error, tProfile("actionError"))),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteExperience(id),
    onSuccess: () => {
      setListError(null);
      onChanged("deleted");
    },
    onError: (error) => setListError(mutationErrorMessage(error, tProfile("actionError"))),
  });

  const period = (experience: Experience) => {
    const start = formatDate(experience.start_date, locale) ?? experience.start_date;
    const end = experience.end_date
      ? (formatDate(experience.end_date, locale) ?? experience.end_date)
      : t("current");
    return `${start} – ${end}`;
  };

  return (
    <SectionCard
      titleId={`${baseId}-title`}
      title={t("title")}
      action={
        !adding ? (
          <Button
            variant="secondary"
            onClick={() => {
              setAdding(true);
              setEditingId(null);
              setServerError(null);
            }}
          >
            <Plus aria-hidden="true" className="h-4 w-4" />
            {t("add")}
          </Button>
        ) : undefined
      }
    >
      {listError ? <Alert variant="error">{listError}</Alert> : null}
      {adding ? (
        <ExperienceForm
          pending={saveMutation.isPending}
          serverError={serverError}
          onSubmit={(input) => saveMutation.mutate({ id: null, input })}
          onCancel={() => {
            setAdding(false);
            setServerError(null);
          }}
        />
      ) : null}
      {profile.experiences.length === 0 && !adding ? (
        <p className="text-sm text-content-secondary">{t("empty")}</p>
      ) : (
        <ul className="space-y-3">
          {profile.experiences.map((experience) => (
            <li key={experience.id} className="rounded-md border border-border p-3">
              {editingId === experience.id ? (
                <ExperienceForm
                  initial={experience}
                  pending={saveMutation.isPending}
                  serverError={serverError}
                  onSubmit={(input) => saveMutation.mutate({ id: experience.id, input })}
                  onCancel={() => {
                    setEditingId(null);
                    setServerError(null);
                  }}
                />
              ) : (
                <div className="space-y-1.5">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="text-sm font-semibold text-content">
                      {experience.title} — {experience.company}
                    </p>
                    <ProvenanceBadge provenance={experience.provenance} />
                  </div>
                  <p className="text-sm text-content-secondary">{period(experience)}</p>
                  {experience.description ? (
                    <p className="whitespace-pre-wrap text-sm text-content-secondary">
                      {experience.description}
                    </p>
                  ) : null}
                  <div className="flex flex-wrap gap-2 pt-1">
                    <Button
                      variant="ghost"
                      aria-label={t("editAria", { label: experience.title })}
                      onClick={() => {
                        setEditingId(experience.id);
                        setAdding(false);
                        setServerError(null);
                      }}
                    >
                      {tProfile("actions.edit")}
                    </Button>
                    <Button
                      variant="ghost"
                      aria-label={t("deleteAria", { label: experience.title })}
                      disabled={deleteMutation.isPending}
                      onClick={() => deleteMutation.mutate(experience.id)}
                    >
                      {tProfile("actions.delete")}
                    </Button>
                  </div>
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </SectionCard>
  );
}

function EducationForm({
  initial,
  pending,
  serverError,
  onSubmit,
  onCancel,
}: {
  initial?: Education;
  pending: boolean;
  serverError: string | null;
  onSubmit: (values: EducationInput) => void;
  onCancel: () => void;
}) {
  const t = useTranslations("profile.educations");
  const tv = useTranslations("validation");
  const tActions = useTranslations("profile.actions");
  const baseId = useId();

  const schema = useMemo(
    () =>
      z.object({
        degree: z.string().min(1, tv("required")).max(200),
        school: z.string().min(1, tv("required")).max(200),
        start_date: z.string(),
        end_date: z.string(),
        description: z.string().max(3000),
      }),
    [tv],
  );
  type FormValues = z.infer<typeof schema>;

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      degree: initial?.degree ?? "",
      school: initial?.school ?? "",
      start_date: initial?.start_date ?? "",
      end_date: initial?.end_date ?? "",
      description: initial?.description ?? "",
    },
  });

  const ids = {
    degree: `${baseId}-degree`,
    school: `${baseId}-school`,
    start: `${baseId}-start`,
    end: `${baseId}-end`,
    description: `${baseId}-description`,
  };

  return (
    <form
      noValidate
      onSubmit={handleSubmit((values) =>
        onSubmit({
          degree: values.degree.trim(),
          school: values.school.trim(),
          start_date: values.start_date || null,
          end_date: values.end_date || null,
          description: values.description.trim() || null,
        }),
      )}
      className="space-y-4 rounded-md border border-border bg-surface-muted p-4"
    >
      {serverError ? <Alert variant="error">{serverError}</Alert> : null}
      <div className="grid gap-4 sm:grid-cols-2">
        <FormField id={ids.degree} label={t("degreeLabel")} required error={errors.degree?.message}>
          <Input
            id={ids.degree}
            autoFocus
            aria-invalid={errors.degree ? true : undefined}
            aria-describedby={fieldDescribedBy(ids.degree, { error: Boolean(errors.degree) })}
            {...register("degree")}
          />
        </FormField>
        <FormField id={ids.school} label={t("schoolLabel")} required error={errors.school?.message}>
          <Input
            id={ids.school}
            aria-invalid={errors.school ? true : undefined}
            aria-describedby={fieldDescribedBy(ids.school, { error: Boolean(errors.school) })}
            {...register("school")}
          />
        </FormField>
        <FormField id={ids.start} label={t("startLabel")}>
          <Input id={ids.start} type="date" {...register("start_date")} />
        </FormField>
        <FormField id={ids.end} label={t("endLabel")}>
          <Input id={ids.end} type="date" {...register("end_date")} />
        </FormField>
      </div>
      <FormField id={ids.description} label={t("descriptionLabel")}>
        <Textarea id={ids.description} {...register("description")} />
      </FormField>
      <div className="flex flex-wrap gap-3">
        <Button type="submit" disabled={pending} aria-busy={pending}>
          {tActions("save")}
        </Button>
        <Button variant="secondary" onClick={onCancel}>
          {tActions("cancel")}
        </Button>
      </div>
    </form>
  );
}

function EducationsSection({
  profile,
  onChanged,
}: {
  profile: Profile;
  onChanged: (announcementKey: "saved" | "deleted") => void;
}) {
  const t = useTranslations("profile.educations");
  const tProfile = useTranslations("profile");
  const baseId = useId();
  const [editingId, setEditingId] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);
  const [listError, setListError] = useState<string | null>(null);

  const saveMutation = useMutation({
    mutationFn: ({ id, input }: { id: string | null; input: EducationInput }) =>
      id ? updateEducation(id, input) : createEducation(input),
    onSuccess: () => {
      setEditingId(null);
      setAdding(false);
      setServerError(null);
      onChanged("saved");
    },
    onError: (error) => setServerError(mutationErrorMessage(error, tProfile("actionError"))),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteEducation(id),
    onSuccess: () => {
      setListError(null);
      onChanged("deleted");
    },
    onError: (error) => setListError(mutationErrorMessage(error, tProfile("actionError"))),
  });

  return (
    <SectionCard
      titleId={`${baseId}-title`}
      title={t("title")}
      action={
        !adding ? (
          <Button
            variant="secondary"
            onClick={() => {
              setAdding(true);
              setEditingId(null);
              setServerError(null);
            }}
          >
            <Plus aria-hidden="true" className="h-4 w-4" />
            {t("add")}
          </Button>
        ) : undefined
      }
    >
      {listError ? <Alert variant="error">{listError}</Alert> : null}
      {adding ? (
        <EducationForm
          pending={saveMutation.isPending}
          serverError={serverError}
          onSubmit={(input) => saveMutation.mutate({ id: null, input })}
          onCancel={() => {
            setAdding(false);
            setServerError(null);
          }}
        />
      ) : null}
      {profile.educations.length === 0 && !adding ? (
        <p className="text-sm text-content-secondary">{t("empty")}</p>
      ) : (
        <ul className="space-y-3">
          {profile.educations.map((education) => (
            <li key={education.id} className="rounded-md border border-border p-3">
              {editingId === education.id ? (
                <EducationForm
                  initial={education}
                  pending={saveMutation.isPending}
                  serverError={serverError}
                  onSubmit={(input) => saveMutation.mutate({ id: education.id, input })}
                  onCancel={() => {
                    setEditingId(null);
                    setServerError(null);
                  }}
                />
              ) : (
                <div className="space-y-1.5">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="text-sm font-semibold text-content">
                      {education.degree} — {education.school}
                    </p>
                    <ProvenanceBadge provenance={education.provenance} />
                  </div>
                  {education.description ? (
                    <p className="whitespace-pre-wrap text-sm text-content-secondary">
                      {education.description}
                    </p>
                  ) : null}
                  <div className="flex flex-wrap gap-2 pt-1">
                    <Button
                      variant="ghost"
                      aria-label={t("editAria", { label: education.degree })}
                      onClick={() => {
                        setEditingId(education.id);
                        setAdding(false);
                        setServerError(null);
                      }}
                    >
                      {tProfile("actions.edit")}
                    </Button>
                    <Button
                      variant="ghost"
                      aria-label={t("deleteAria", { label: education.degree })}
                      disabled={deleteMutation.isPending}
                      onClick={() => deleteMutation.mutate(education.id)}
                    >
                      {tProfile("actions.delete")}
                    </Button>
                  </div>
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </SectionCard>
  );
}

/* ------------------------------------------------------------------ */
/* Compétences / Langues                                               */
/* ------------------------------------------------------------------ */

function SkillsSection({
  profile,
  onChanged,
}: {
  profile: Profile;
  onChanged: (announcementKey: "saved" | "deleted") => void;
}) {
  const t = useTranslations("profile.skills");
  const tProfile = useTranslations("profile");
  const tv = useTranslations("validation");
  const baseId = useId();
  const [serverError, setServerError] = useState<string | null>(null);

  const schema = useMemo(() => z.object({ label: z.string().min(1, tv("required")).max(100) }), [tv]);
  type FormValues = z.infer<typeof schema>;

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<FormValues>({ resolver: zodResolver(schema), defaultValues: { label: "" } });

  const addMutation = useMutation({
    mutationFn: (values: FormValues) => createSkill({ label: values.label.trim() }),
    onSuccess: () => {
      reset();
      setServerError(null);
      onChanged("saved");
    },
    onError: (error) => setServerError(mutationErrorMessage(error, tProfile("actionError"))),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteSkill(id),
    onSuccess: () => onChanged("deleted"),
    onError: (error) => setServerError(mutationErrorMessage(error, tProfile("actionError"))),
  });

  const inputId = `${baseId}-skill`;

  return (
    <SectionCard titleId={`${baseId}-title`} title={t("title")}>
      {serverError ? <Alert variant="error">{serverError}</Alert> : null}
      <form
        noValidate
        onSubmit={handleSubmit((values) => addMutation.mutate(values))}
        className="flex flex-wrap items-end gap-3"
      >
        <div className="min-w-52 flex-1">
          <FormField id={inputId} label={t("inputLabel")} error={errors.label?.message}>
            <Input
              id={inputId}
              aria-invalid={errors.label ? true : undefined}
              aria-describedby={fieldDescribedBy(inputId, { error: Boolean(errors.label) })}
              {...register("label")}
            />
          </FormField>
        </div>
        <Button type="submit" disabled={addMutation.isPending} aria-busy={addMutation.isPending}>
          {t("add")}
        </Button>
      </form>
      {profile.skills.length === 0 ? (
        <p className="text-sm text-content-secondary">{t("empty")}</p>
      ) : (
        <ul className="flex flex-wrap gap-2">
          {profile.skills.map((skill) => (
            <li
              key={skill.id}
              className="flex items-center gap-2 rounded-md border border-border bg-surface-muted px-2 py-1 text-sm text-content"
            >
              <span>{skill.label}</span>
              <ProvenanceBadge provenance={skill.provenance} />
              <button
                type="button"
                aria-label={t("removeAria", { label: skill.label })}
                disabled={deleteMutation.isPending}
                onClick={() => deleteMutation.mutate(skill.id)}
                className="inline-flex h-11 min-w-6 items-center justify-center rounded-sm px-1 font-semibold text-content-secondary hover:text-feedback-error focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
              >
                <span aria-hidden="true">×</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </SectionCard>
  );
}

function LanguagesSection({
  profile,
  onChanged,
}: {
  profile: Profile;
  onChanged: (announcementKey: "saved" | "deleted") => void;
}) {
  const t = useTranslations("profile.languages");
  const tProfile = useTranslations("profile");
  const tv = useTranslations("validation");
  const baseId = useId();
  const [serverError, setServerError] = useState<string | null>(null);

  const schema = useMemo(
    () =>
      z.object({
        lang_code: z
          .string()
          .regex(/^[a-zA-Z]{2}$/, tv("langCode"))
          .transform((code) => code.toLowerCase()),
        level: z.enum(CEFR_LEVELS as [CefrLevel, ...CefrLevel[]]),
      }),
    [tv],
  );
  type FormValues = z.infer<typeof schema>;

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { lang_code: "", level: "B2" },
  });

  const addMutation = useMutation({
    mutationFn: (values: FormValues) => createLanguage(values),
    onSuccess: () => {
      reset();
      setServerError(null);
      onChanged("saved");
    },
    onError: (error) => setServerError(mutationErrorMessage(error, tProfile("actionError"))),
  });

  const levelMutation = useMutation({
    mutationFn: ({ id, lang_code, level }: { id: string; lang_code: string; level: CefrLevel }) =>
      updateLanguage(id, { lang_code, level }),
    onSuccess: () => onChanged("saved"),
    onError: (error) => setServerError(mutationErrorMessage(error, tProfile("actionError"))),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteLanguage(id),
    onSuccess: () => onChanged("deleted"),
    onError: (error) => setServerError(mutationErrorMessage(error, tProfile("actionError"))),
  });

  const codeId = `${baseId}-code`;
  const levelId = `${baseId}-level`;

  return (
    <SectionCard titleId={`${baseId}-title`} title={t("title")}>
      {serverError ? <Alert variant="error">{serverError}</Alert> : null}
      <form
        noValidate
        onSubmit={handleSubmit((values) => addMutation.mutate(values))}
        className="flex flex-wrap items-end gap-3"
      >
        <div className="w-40">
          <FormField id={codeId} label={t("codeLabel")} error={errors.lang_code?.message}>
            <Input
              id={codeId}
              maxLength={2}
              aria-invalid={errors.lang_code ? true : undefined}
              aria-describedby={fieldDescribedBy(codeId, { error: Boolean(errors.lang_code) })}
              {...register("lang_code")}
            />
          </FormField>
        </div>
        <div className="w-40">
          <FormField id={levelId} label={t("levelLabel")}>
            <select id={levelId} className={selectClass} {...register("level")}>
              {CEFR_LEVELS.map((level) => (
                <option key={level} value={level}>
                  {level}
                </option>
              ))}
            </select>
          </FormField>
        </div>
        <Button type="submit" disabled={addMutation.isPending} aria-busy={addMutation.isPending}>
          {t("add")}
        </Button>
      </form>
      {profile.languages.length === 0 ? (
        <p className="text-sm text-content-secondary">{t("empty")}</p>
      ) : (
        <ul className="space-y-2">
          {profile.languages.map((language) => (
            <li
              key={language.id}
              className="flex flex-wrap items-center gap-3 rounded-md border border-border p-3"
            >
              <span className="text-sm font-medium uppercase text-content">
                {language.lang_code}
              </span>
              <label className="sr-only" htmlFor={`${baseId}-level-${language.id}`}>
                {t("levelAria", { label: language.lang_code })}
              </label>
              <select
                id={`${baseId}-level-${language.id}`}
                value={language.level}
                disabled={levelMutation.isPending}
                onChange={(event) =>
                  levelMutation.mutate({
                    id: language.id,
                    lang_code: language.lang_code,
                    level: event.target.value as CefrLevel,
                  })
                }
                className={clsx(selectClass, "h-11 w-24")}
              >
                {CEFR_LEVELS.map((level) => (
                  <option key={level} value={level}>
                    {level}
                  </option>
                ))}
              </select>
              <ProvenanceBadge provenance={language.provenance} />
              <Button
                variant="ghost"
                aria-label={t("removeAria", { label: language.lang_code })}
                disabled={deleteMutation.isPending}
                onClick={() => deleteMutation.mutate(language.id)}
              >
                {tProfile("actions.delete")}
              </Button>
            </li>
          ))}
        </ul>
      )}
    </SectionCard>
  );
}

/* ------------------------------------------------------------------ */
/* Page                                                                */
/* ------------------------------------------------------------------ */

export default function ProfilePage() {
  const t = useTranslations("profile");
  const queryClient = useQueryClient();
  const [announcement, setAnnouncement] = useState<string | null>(null);
  const [validateError, setValidateError] = useState<string | null>(null);
  const [validated, setValidated] = useState(false);
  const validateSuccessRef = useRef<HTMLDivElement>(null);

  const profileQuery = useQuery({
    queryKey: profileKeys.root,
    queryFn: ({ signal }) => getProfile(signal),
  });

  /**
   * Après toute mutation du profil : re-fetch du profil et invalidation de
   * tous les caches match — le score dépend du profil (06 §4). L'annonce
   * passe par la région `aria-live` de la page.
   */
  const handleChanged = useCallback(
    (announcementKey: "saved" | "deleted") => {
      void queryClient.invalidateQueries({ queryKey: profileKeys.root });
      invalidateMatchDependentQueries(queryClient);
      setAnnouncement(t(`announce.${announcementKey}`));
    },
    [queryClient, t],
  );

  const validateMutation = useMutation({
    mutationFn: () => validateProfile(),
    onSuccess: (profile) => {
      setValidateError(null);
      setValidated(true);
      queryClient.setQueryData(profileKeys.root, profile);
      invalidateMatchDependentQueries(queryClient);
      requestAnimationFrame(() => validateSuccessRef.current?.focus());
    },
    onError: (error) => {
      // 409 : préconditions non remplies — messages ciblés de l'API.
      setValidated(false);
      setValidateError(mutationErrorMessage(error, t("validate.errorFallback")));
    },
  });

  if (profileQuery.isPending) {
    return (
      <section aria-labelledby="profile-title" className="space-y-6">
        <h1 id="profile-title" className="text-2xl font-semibold text-content">
          {t("title")}
        </h1>
        <div role="status" aria-live="polite" className="space-y-4">
          <span className="sr-only">{t("loading")}</span>
          <div aria-hidden="true" className="h-32 animate-pulse rounded-lg bg-surface-muted" />
          <div aria-hidden="true" className="h-64 animate-pulse rounded-lg bg-surface-muted" />
        </div>
      </section>
    );
  }

  if (profileQuery.isError) {
    return (
      <section aria-labelledby="profile-title" className="space-y-6">
        <h1 id="profile-title" className="text-2xl font-semibold text-content">
          {t("title")}
        </h1>
        <Alert variant="error" title={t("errorTitle")}>
          <Button variant="secondary" onClick={() => void profileQuery.refetch()}>
            {t("retry")}
          </Button>
        </Alert>
      </section>
    );
  }

  const profile = profileQuery.data;
  const preconditionsMet =
    profile.skills.length >= VALIDATE_MIN_SKILLS &&
    profile.experiences.length + profile.educations.length >= 1;

  return (
    <section aria-labelledby="profile-title" className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 id="profile-title" className="text-2xl font-semibold text-content">
          {t("title")}
        </h1>
        <p className="flex flex-wrap items-center gap-2 text-sm text-content-secondary">
          <span
            className={clsx(
              "rounded-md px-2 py-0.5 text-xs font-medium",
              profile.status === "validated"
                ? "bg-feedback-success-surface text-feedback-success"
                : "bg-feedback-warning-surface text-feedback-warning",
            )}
          >
            {profile.status === "validated" ? t("status.validated") : t("status.draft")}
          </span>
          {t("version", { version: profile.version })}
        </p>
      </div>

      {/* Annonce des mutations (aria-live) — modifications, suppressions. */}
      <p role="status" aria-live="polite" className="sr-only">
        {announcement}
      </p>

      {validated ? (
        <Alert ref={validateSuccessRef} tabIndex={-1} variant="success">
          {t("validate.success")}
        </Alert>
      ) : null}

      <RootInfoSection profile={profile} onChanged={handleChanged} />
      <ExperiencesSection profile={profile} onChanged={handleChanged} />
      <EducationsSection profile={profile} onChanged={handleChanged} />
      <SkillsSection profile={profile} onChanged={handleChanged} />
      <LanguagesSection profile={profile} onChanged={handleChanged} />

      {/* CTA de validation (Flux 1 §6) — actif si ≥ 3 compétences ET ≥ 1
          expérience ou formation ; sinon bouton désactivé + explication. */}
      <div className="space-y-3 rounded-lg border border-border bg-surface p-4">
        {validateError ? <Alert variant="error">{validateError}</Alert> : null}
        <Button
          onClick={() => validateMutation.mutate()}
          disabled={!preconditionsMet || validateMutation.isPending}
          aria-busy={validateMutation.isPending}
          aria-describedby={!preconditionsMet ? "profile-validate-hint" : undefined}
        >
          {t("validate.cta")}
        </Button>
        {!preconditionsMet ? (
          <p id="profile-validate-hint" className="text-sm text-content-secondary">
            {t("validate.preconditions", { minSkills: VALIDATE_MIN_SKILLS })}
          </p>
        ) : null}
      </div>
    </section>
  );
}
