"use client";

// SCR-40 (+ détail SCR-41 en expansion, ajout SCR-42) — M4
// Suivi des candidatures (Flux 7) : sections accessibles par statut (PAS de
// drag-and-drop — le changement de statut passe par un menu accessible,
// historisé), création manuelle (offre externe) et pré-remplissage depuis le
// détail d'offre (`?suivre={job_posting_id}`), notes éditables (PATCH),
// frise des événements historisés (dates formatées), suppression avec
// confirmation. Chaque changement de statut est annoncé (`aria-live`).

import { zodResolver } from "@hookform/resolvers/zod";
import {
  useInfiniteQuery,
  useMutation,
  useQueryClient,
} from "@tanstack/react-query";
import { FileText, Plus, Send } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import { Suspense, useId, useMemo, useRef, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { FormField, fieldDescribedBy } from "@/components/ui/form-field";
import { Input } from "@/components/ui/input";
import {
  APPLICATION_STATUS_ORDER,
  applicationKeys,
  changeApplicationStatus,
  createApplication,
  deleteApplication,
  listApplications,
  patchApplication,
} from "@/lib/api/applications";
import { getNextCursor, isApiProblem } from "@/lib/api/client";
import type { Application, ApplicationStatus, Page } from "@/lib/api/types";
import { formatDateTime } from "@/lib/format";

const PAGE_SIZE = 100;

/** Statuts initiaux proposés à la création (Flux 7 §1 : `to_apply` ou `applied`). */
const INITIAL_STATUSES: readonly ApplicationStatus[] = ["to_apply", "applied"];

const selectClass =
  "h-11 rounded-md border border-border bg-surface px-3 text-sm text-content focus:border-action-primary focus:shadow-input-focus focus:outline-none disabled:cursor-not-allowed disabled:opacity-50";

type StatusTranslator = (key: ApplicationStatus) => string;

/** Nom affiché d'une candidature : externe, ou offre interne dénormalisée 🟡. */
function applicationName(application: Application, fallback: string): string {
  return application.external_title ?? application.job_title ?? fallback;
}

/* ------------------------------------------------------------------ */
/* Frise des événements (SCR-41) — liste ordonnée datée                */
/* ------------------------------------------------------------------ */

function EventTimeline({
  application,
  statusLabel,
}: {
  application: Application;
  statusLabel: StatusTranslator;
}) {
  const t = useTranslations("applications.timeline");
  const locale = useLocale();
  const titleId = useId();

  return (
    <div className="space-y-2">
      <h4 id={titleId} className="text-sm font-semibold text-content">
        {t("title")}
      </h4>
      {application.events.length === 0 ? (
        <p className="text-sm text-content-secondary">{t("empty")}</p>
      ) : (
        <ol aria-labelledby={titleId} className="space-y-2 border-l-2 border-border pl-4">
          {application.events.map((event, index) => {
            const date = formatDateTime(event.at, locale);
            return (
              <li key={`${event.at}-${index}`} className="space-y-0.5 text-sm">
                <p className="font-medium text-content">
                  {event.from_status
                    ? t("transition", {
                        from: statusLabel(event.from_status),
                        to: statusLabel(event.to_status),
                      })
                    : t("initial", { to: statusLabel(event.to_status) })}
                </p>
                {date ? <p className="text-content-secondary">{date}</p> : null}
                {event.note ? (
                  <p className="whitespace-pre-wrap text-content-secondary">{event.note}</p>
                ) : null}
              </li>
            );
          })}
        </ol>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Carte de candidature (statut, notes, frise, suppression)            */
/* ------------------------------------------------------------------ */

function ApplicationCard({
  application,
  onAnnounce,
}: {
  application: Application;
  onAnnounce: (message: string) => void;
}) {
  const t = useTranslations("applications");
  const locale = useLocale();
  const queryClient = useQueryClient();
  const baseId = useId();

  const [expanded, setExpanded] = useState(false);
  const [confirmingDelete, setConfirmingDelete] = useState(false);
  const [editingNotes, setEditingNotes] = useState(false);
  const [notesDraft, setNotesDraft] = useState("");
  const [cardError, setCardError] = useState<string | null>(null);

  const statusLabel: StatusTranslator = (status) => t(`status.${status}`);
  const name = applicationName(application, t("card.linkedJob"));

  const invalidate = () =>
    void queryClient.invalidateQueries({ queryKey: applicationKeys.all });

  const statusMutation = useMutation({
    mutationFn: (to_status: ApplicationStatus) =>
      changeApplicationStatus(application.id, { to_status }),
    onSuccess: (_data, to_status) => {
      setCardError(null);
      invalidate();
      onAnnounce(t("card.statusUpdated", { status: statusLabel(to_status) }));
    },
    onError: (error) => {
      // 422 : transition non permise (Flux 7, matrice Q7).
      if (isApiProblem(error) && error.status === 422) {
        setCardError(t("card.transitionRejected", { status: statusLabel(application.status) }));
      } else {
        setCardError(t("card.actionError"));
      }
    },
  });

  const notesMutation = useMutation({
    mutationFn: (notes: string) =>
      patchApplication(application.id, { notes: notes.trim() || null }),
    onSuccess: () => {
      setCardError(null);
      setEditingNotes(false);
      invalidate();
      onAnnounce(t("notes.saved"));
    },
    onError: () => setCardError(t("notes.error")),
  });

  const deleteMutation = useMutation({
    mutationFn: () => deleteApplication(application.id),
    onSuccess: () => {
      invalidate();
      onAnnounce(t("delete.deleted"));
    },
    onError: () => {
      setConfirmingDelete(false);
      setCardError(t("delete.error"));
    },
  });

  const lastEvent = application.events.at(-1);
  const lastEventDate = formatDateTime(lastEvent?.at ?? application.applied_at, locale);
  const detailsId = `${baseId}-details`;
  const statusSelectId = `${baseId}-status`;
  const notesId = `${baseId}-notes`;
  // Hypothèse Q7 🟡 : toutes les transitions sont permises sauf depuis `withdrawn`.
  const statusLocked = application.status === "withdrawn";

  return (
    <li className="space-y-3 rounded-lg border border-border bg-surface p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 space-y-0.5">
          <p className="text-base font-semibold text-content">{name}</p>
          {(application.external_company ?? application.job_company) ? (
            <p className="text-sm text-content-secondary">
              {application.external_company ?? application.job_company}
            </p>
          ) : null}
          {lastEventDate ? (
            <p className="text-sm text-content-secondary">
              {t("card.lastEvent", { date: lastEventDate })}
            </p>
          ) : null}
        </div>

        <div className="space-y-1.5">
          <label htmlFor={statusSelectId} className="sr-only">
            {t("card.statusLabel", { name })}
          </label>
          <select
            id={statusSelectId}
            value={application.status}
            disabled={statusMutation.isPending || statusLocked}
            aria-describedby={statusLocked ? `${baseId}-locked` : undefined}
            onChange={(event) =>
              statusMutation.mutate(event.target.value as ApplicationStatus)
            }
            className={selectClass}
          >
            {APPLICATION_STATUS_ORDER.map((status) => (
              <option key={status} value={status}>
                {statusLabel(status)}
              </option>
            ))}
          </select>
          {statusLocked ? (
            <p id={`${baseId}-locked`} className="max-w-52 text-xs text-content-secondary">
              {t("card.withdrawnLocked")}
            </p>
          ) : null}
        </div>
      </div>

      {cardError ? <Alert variant="error">{cardError}</Alert> : null}

      <div className="flex flex-wrap gap-2">
        {application.job_posting_id ? (
          <Link
            href={`/offres/${application.job_posting_id}`}
            className="inline-flex min-h-11 items-center text-sm font-medium text-action-primary underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
          >
            {t("card.viewJob")}
          </Link>
        ) : null}
        {application.external_url ? (
          <a
            href={application.external_url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex min-h-11 items-center text-sm font-medium text-action-primary underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
          >
            {t("card.viewExternal")}
          </a>
        ) : null}
        <button
          type="button"
          aria-expanded={expanded}
          aria-controls={detailsId}
          onClick={() => setExpanded((open) => !open)}
          className="inline-flex min-h-11 items-center rounded-sm text-sm font-medium text-content-secondary underline-offset-4 hover:text-content hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
        >
          {t("card.detailsToggle")}
        </button>
      </div>

      {expanded ? (
        <div id={detailsId} className="space-y-4 border-t border-border pt-3">
          <EventTimeline application={application} statusLabel={statusLabel} />

          {/* Notes libres (PATCH /applications/{id}). */}
          <div className="space-y-2">
            <h4 className="text-sm font-semibold text-content">{t("notes.label")}</h4>
            {editingNotes ? (
              <div className="space-y-2">
                <label htmlFor={notesId} className="sr-only">
                  {t("notes.label")}
                </label>
                <textarea
                  id={notesId}
                  value={notesDraft}
                  onChange={(event) => setNotesDraft(event.target.value)}
                  rows={4}
                  className="w-full rounded-md border border-border bg-surface px-3 py-2 text-sm text-content focus:border-action-primary focus:shadow-input-focus focus:outline-none"
                />
                <div className="flex flex-wrap gap-2">
                  <Button
                    onClick={() => notesMutation.mutate(notesDraft)}
                    disabled={notesMutation.isPending}
                    aria-busy={notesMutation.isPending}
                  >
                    {t("notes.save")}
                  </Button>
                  <Button variant="secondary" onClick={() => setEditingNotes(false)}>
                    {t("notes.cancel")}
                  </Button>
                </div>
              </div>
            ) : (
              <div className="space-y-2">
                {application.notes ? (
                  <p className="whitespace-pre-wrap text-sm text-content-secondary">
                    {application.notes}
                  </p>
                ) : (
                  <p className="text-sm text-content-secondary">{t("notes.empty")}</p>
                )}
                <Button
                  variant="secondary"
                  onClick={() => {
                    setNotesDraft(application.notes ?? "");
                    setEditingNotes(true);
                  }}
                >
                  {t("notes.edit")}
                </Button>
              </div>
            )}
          </div>

          {/* Suppression avec confirmation (Flux 7, microcopie exacte). */}
          <div className="space-y-2">
            {confirmingDelete ? (
              <div className="space-y-2">
                <Alert variant="warning">{t("delete.confirmBody")}</Alert>
                <div className="flex flex-wrap gap-2">
                  <Button
                    variant="destructive"
                    onClick={() => deleteMutation.mutate()}
                    disabled={deleteMutation.isPending}
                    aria-busy={deleteMutation.isPending}
                  >
                    {t("delete.confirm")}
                  </Button>
                  <Button variant="secondary" onClick={() => setConfirmingDelete(false)}>
                    {t("delete.cancel")}
                  </Button>
                </div>
              </div>
            ) : (
              <Button variant="ghost" onClick={() => setConfirmingDelete(true)}>
                {t("delete.cta")}
              </Button>
            )}
          </div>
        </div>
      ) : null}
    </li>
  );
}

/* ------------------------------------------------------------------ */
/* Formulaire d'ajout (SCR-42, + pré-rempli depuis SCR-21)             */
/* ------------------------------------------------------------------ */

function CreateApplicationForm({
  linkedJobId,
  linkedJobTitle,
  linkedJobCompany,
  existingJobIds,
  onCreated,
  onCancel,
}: {
  /** `?suivre={job_posting_id}` — candidature interne pré-remplie (Flux 7 §1a). */
  linkedJobId: string | null;
  linkedJobTitle: string | null;
  linkedJobCompany: string | null;
  /** Ids d'offres déjà suivies — détection de doublon côté client (Q7). */
  existingJobIds: ReadonlySet<string>;
  onCreated: (application: Application) => void;
  onCancel: () => void;
}) {
  const t = useTranslations("applications.form");
  const tStatus = useTranslations("applications");
  const tv = useTranslations("validation");
  const queryClient = useQueryClient();
  const baseId = useId();
  const [serverError, setServerError] = useState<string | null>(null);
  // Idempotency-Key stable pour la durée du formulaire (double-clic = rejeu).
  const idempotencyKeyRef = useRef<string>(crypto.randomUUID());

  const isLinked = linkedJobId !== null;
  const duplicate = isLinked && existingJobIds.has(linkedJobId);

  const schema = useMemo(
    () =>
      z.object({
        external_title: isLinked ? z.string() : z.string().min(1, tv("required")).max(200),
        external_company: isLinked ? z.string() : z.string().min(1, tv("required")).max(200),
        external_url: z
          .string()
          .refine((value) => value === "" || /^https?:\/\/\S+$/.test(value), {
            message: t("urlInvalid"),
          }),
        notes: z.string(),
        status: z.enum(INITIAL_STATUSES as [ApplicationStatus, ...ApplicationStatus[]]),
      }),
    [isLinked, t, tv],
  );
  type FormValues = z.infer<typeof schema>;

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      external_title: "",
      external_company: "",
      external_url: "",
      notes: "",
      // Depuis une offre : « J'ai postulé » → `applied` ; externe : `to_apply` 🟡.
      status: isLinked ? "applied" : "to_apply",
    },
  });

  const createMutation = useMutation({
    // `POST /applications` n'accepte AUCUN statut initial : la candidature est
    // toujours créée en `draft`, puis la transition choisie est chaînée via
    // `POST /applications/{id}/status` (historisée) dans la même mutation.
    mutationFn: async (values: FormValues) => {
      const application = await createApplication(
        isLinked
          ? {
              job_posting_id: linkedJobId,
              notes: values.notes.trim() || null,
            }
          : {
              external_title: values.external_title.trim(),
              external_company: values.external_company.trim(),
              external_url: values.external_url.trim() || null,
              notes: values.notes.trim() || null,
            },
        idempotencyKeyRef.current,
      );
      const toStatus: ApplicationStatus = values.status;
      if (toStatus === "draft") return application;
      try {
        return await changeApplicationStatus(application.id, { to_status: toStatus });
      } catch (error) {
        // Choix documenté : si cette 2e étape échoue, la candidature EXISTE
        // déjà (en `draft`). On rafraîchit la liste pour rendre sa carte
        // visible, on affiche l'erreur standard du formulaire (onError), et
        // l'utilisateur peut changer le statut manuellement depuis la carte.
        // Un nouvel envoi rejoue la création (même Idempotency-Key) puis
        // retente la transition.
        void queryClient.invalidateQueries({ queryKey: applicationKeys.all });
        throw error;
      }
    },
    onSuccess: (application) => onCreated(application),
    onError: (error) => {
      if (isApiProblem(error) && error.errors.length > 0) {
        setServerError(error.errors.map((fieldError) => fieldError.message).join(" "));
      } else {
        setServerError(t("error"));
      }
    },
  });

  const ids = {
    title: `${baseId}-title`,
    company: `${baseId}-company`,
    url: `${baseId}-url`,
    notes: `${baseId}-notes`,
    status: `${baseId}-status`,
  };

  return (
    <form
      noValidate
      onSubmit={handleSubmit((values) => {
        if (duplicate) return;
        createMutation.mutate(values);
      })}
      aria-labelledby={`${baseId}-form-title`}
      className="space-y-4 rounded-lg border border-border bg-surface-muted p-4"
    >
      <h2 id={`${baseId}-form-title`} className="text-lg font-semibold text-content">
        {isLinked ? t("titleTracked") : t("title")}
      </h2>

      {duplicate ? (
        // Doublon détecté côté client (Flux 7, Q7) — création bloquée.
        <Alert variant="warning">{t("duplicate")}</Alert>
      ) : null}
      {serverError ? <Alert variant="error">{serverError}</Alert> : null}

      {isLinked ? (
        <p className="text-sm text-content">
          {linkedJobTitle
            ? t("linkedJobNote", {
                title: linkedJobCompany
                  ? `${linkedJobTitle} — ${linkedJobCompany}`
                  : linkedJobTitle,
              })
            : t("linkedJobNoteNoTitle")}
        </p>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2">
          <FormField
            id={ids.title}
            label={t("externalTitleLabel")}
            required
            error={errors.external_title?.message}
          >
            <Input
              id={ids.title}
              autoFocus
              aria-invalid={errors.external_title ? true : undefined}
              aria-describedby={fieldDescribedBy(ids.title, {
                error: Boolean(errors.external_title),
              })}
              {...register("external_title")}
            />
          </FormField>
          <FormField
            id={ids.company}
            label={t("externalCompanyLabel")}
            required
            error={errors.external_company?.message}
          >
            <Input
              id={ids.company}
              aria-invalid={errors.external_company ? true : undefined}
              aria-describedby={fieldDescribedBy(ids.company, {
                error: Boolean(errors.external_company),
              })}
              {...register("external_company")}
            />
          </FormField>
        </div>
      )}

      {!isLinked ? (
        <FormField id={ids.url} label={t("externalUrlLabel")} error={errors.external_url?.message}>
          <Input
            id={ids.url}
            type="url"
            inputMode="url"
            placeholder="https://…"
            aria-invalid={errors.external_url ? true : undefined}
            aria-describedby={fieldDescribedBy(ids.url, { error: Boolean(errors.external_url) })}
            {...register("external_url")}
          />
        </FormField>
      ) : null}

      <FormField id={ids.status} label={t("statusLabel")}>
        <select id={ids.status} className={selectClass} {...register("status")}>
          {INITIAL_STATUSES.map((status) => (
            <option key={status} value={status}>
              {tStatus(`status.${status}`)}
            </option>
          ))}
        </select>
      </FormField>

      <FormField id={ids.notes} label={t("notesLabel")}>
        <textarea
          id={ids.notes}
          rows={3}
          className="w-full rounded-md border border-border bg-surface px-3 py-2 text-sm text-content focus:border-action-primary focus:shadow-input-focus focus:outline-none"
          {...register("notes")}
        />
      </FormField>

      <div className="flex flex-wrap gap-3">
        <Button
          type="submit"
          disabled={createMutation.isPending || duplicate}
          aria-busy={createMutation.isPending}
        >
          {t("submit")}
        </Button>
        <Button variant="secondary" onClick={onCancel}>
          {t("cancel")}
        </Button>
      </div>
    </form>
  );
}

/* ------------------------------------------------------------------ */
/* Page                                                                */
/* ------------------------------------------------------------------ */

function ApplicationsScreen() {
  const t = useTranslations("applications");
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const queryClient = useQueryClient();

  // Pré-remplissage depuis SCR-21 (« Suivre ma candidature ») ou SCR-32.
  const linkedJobId = searchParams.get("suivre");
  const linkedJobTitle = searchParams.get("titre");
  const linkedJobCompany = searchParams.get("entreprise");

  const [creating, setCreating] = useState(linkedJobId !== null);
  const [announcement, setAnnouncement] = useState<string | null>(null);

  const applicationsQuery = useInfiniteQuery({
    queryKey: applicationKeys.list({ limit: PAGE_SIZE }),
    queryFn: ({ pageParam, signal }) => listApplications({ limit: PAGE_SIZE }, pageParam, signal),
    initialPageParam: null as string | null,
    getNextPageParam: (page: Page<Application>) => getNextCursor(page) ?? null,
  });

  const applications = useMemo(
    () => applicationsQuery.data?.pages.flatMap((page) => page.items) ?? [],
    [applicationsQuery.data],
  );

  const existingJobIds = useMemo(
    () =>
      new Set(
        applications
          .map((application) => application.job_posting_id)
          .filter((jobId): jobId is string => Boolean(jobId)),
      ),
    [applications],
  );

  const grouped = useMemo(
    () =>
      APPLICATION_STATUS_ORDER.map((status) => ({
        status,
        items: applications.filter((application) => application.status === status),
      })),
    [applications],
  );

  const handleCreated = (application: Application) => {
    setCreating(false);
    void queryClient.invalidateQueries({ queryKey: applicationKeys.all });
    setAnnouncement(t("form.created"));
    // Nettoie les paramètres de pré-remplissage après création.
    if (linkedJobId) router.replace(pathname, { scroll: false });
    void application;
  };

  const closeForm = () => {
    setCreating(false);
    if (linkedJobId) router.replace(pathname, { scroll: false });
  };

  return (
    <section aria-labelledby="applications-title" className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 id="applications-title" className="text-2xl font-semibold text-content">
          {t("title")}
        </h1>
        <div className="flex flex-wrap gap-2">
          <Link
            href="/candidatures/documents"
            className="inline-flex min-h-11 items-center gap-1.5 rounded-md border border-border bg-surface px-4 text-sm font-medium text-content hover:bg-surface-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
          >
            <FileText aria-hidden="true" className="h-4 w-4" />
            {t("documentsLink")}
          </Link>
          {!creating ? (
            <Button onClick={() => setCreating(true)}>
              <Plus aria-hidden="true" className="h-4 w-4" />
              {t("add")}
            </Button>
          ) : null}
        </div>
      </div>

      {/* Rappel D10 : la saisie est manuelle, rien n'est envoyé par Boussole. */}
      <p className="max-w-prose text-sm text-content-secondary">{t("intro")}</p>

      {/* Annonces (statut mis à jour, notes, suppression…) — aria-live. */}
      <p role="status" aria-live="polite" className="sr-only">
        {announcement}
      </p>

      {creating ? (
        <CreateApplicationForm
          linkedJobId={linkedJobId}
          linkedJobTitle={linkedJobTitle}
          linkedJobCompany={linkedJobCompany}
          existingJobIds={existingJobIds}
          onCreated={handleCreated}
          onCancel={closeForm}
        />
      ) : null}

      {applicationsQuery.isPending ? (
        <div role="status" aria-live="polite" className="space-y-3">
          <span className="sr-only">{t("loading")}</span>
          {Array.from({ length: 3 }, (_, index) => (
            <div
              key={index}
              aria-hidden="true"
              className="h-28 animate-pulse rounded-lg border border-border bg-surface-muted"
            />
          ))}
        </div>
      ) : null}

      {applicationsQuery.isError ? (
        <Alert variant="error" title={t("errorTitle")}>
          <Button variant="secondary" onClick={() => void applicationsQuery.refetch()}>
            {t("retry")}
          </Button>
        </Alert>
      ) : null}

      {applicationsQuery.isSuccess && applications.length === 0 && !creating ? (
        <EmptyState icon={Send} title={t("emptyTitle")} description={t("emptyDescription")}>
          <Button onClick={() => setCreating(true)}>
            <Plus aria-hidden="true" className="h-4 w-4" />
            {t("add")}
          </Button>
        </EmptyState>
      ) : null}

      {applications.length > 0 ? (
        <div className="space-y-6">
          {grouped.map(({ status, items }) =>
            items.length > 0 ? (
              <section
                key={status}
                aria-labelledby={`applications-group-${status}`}
                className="space-y-3"
              >
                <h2
                  id={`applications-group-${status}`}
                  className="flex items-baseline gap-2 text-lg font-semibold text-content"
                >
                  {t(`status.${status}`)}
                  <span className="text-sm font-normal text-content-secondary">
                    {t("sectionCount", { count: items.length })}
                  </span>
                </h2>
                <ul className="space-y-3">
                  {items.map((application) => (
                    <ApplicationCard
                      key={application.id}
                      application={application}
                      onAnnounce={setAnnouncement}
                    />
                  ))}
                </ul>
              </section>
            ) : null,
          )}

          {applicationsQuery.hasNextPage ? (
            <div className="flex justify-center">
              <Button
                variant="secondary"
                onClick={() => void applicationsQuery.fetchNextPage()}
                disabled={applicationsQuery.isFetchingNextPage}
                aria-busy={applicationsQuery.isFetchingNextPage}
              >
                {t("loadMore")}
              </Button>
            </div>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}

export default function ApplicationsPage() {
  return (
    <Suspense fallback={null}>
      <ApplicationsScreen />
    </Suspense>
  );
}
