"use client";

// SCR-70 — M5 (regroupe SCR-71 Confidentialité & données, SCR-72 Suppression
// du compte et SCR-73 Sources des offres sur une seule page Paramètres).
//
// 1. « Mes données » : export RGPD asynchrone — `POST /privacy/export`
//    (Idempotency-Key UUID, 429 quota 2/j avec Retry-After) puis polling
//    `GET /privacy/exports/{id}` (2 s ×1,5, 12 §1) ; à `ready`, lien signé
//    `download_url` (7 j) utilisé tel quel ; `expired` → nouvel export.
// 2. « Sources et transparence » : `GET /sources` (M6-b) + lien politique de
//    confidentialité (🟡 contenu légal à venir — href="#").
// 3. Zone dangereuse : `DELETE /account` via modale de confirmation
//    accessible (microcopie exacte M5 de 04 §M, Flux 8), puis redirection
//    SCR-01 avec message de confirmation.

import { useMutation, useQuery } from "@tanstack/react-query";
import { useLocale, useTranslations } from "next-intl";
import {
  useEffect,
  useId,
  useRef,
  useState,
  type FormEvent,
  type KeyboardEvent,
} from "react";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { FormField, fieldDescribedBy } from "@/components/ui/form-field";
import { Input } from "@/components/ui/input";
import { isApiProblem } from "@/lib/api/client";
import { getSources, jobsKeys } from "@/lib/api/jobs";
import {
  PRIVACY_EXPORT_DAILY_LIMIT,
  PRIVACY_EXPORT_LINK_TTL_DAYS,
  deleteAccount,
  getPrivacyExport,
  isPrivacyExportSettled,
  privacyKeys,
  requestPrivacyExport,
} from "@/lib/api/privacy";
import { formatDateTime } from "@/lib/format";
import { makePollingInterval } from "@/lib/polling";

/**
 * Délai entre l'annonce de la confirmation de suppression (`role="status"`)
 * et la redirection SCR-01 — « confirmation finale annoncée avant la
 * redirection » (04 Flux 8, a11y).
 */
const DELETE_REDIRECT_DELAY_MS = 1_500;

/**
 * Modale de confirmation de suppression de compte (SCR-72, microcopie M5
 * exacte). A11y (04 Flux 8) : `role="alertdialog"` + `aria-modal`, titre et
 * description liés, piège de focus, focus initial sur le champ mot de passe
 * (🟡 Q9/04 — alternative : bouton « Annuler », à trancher en test), Échap =
 * annuler, bouton destructif distinct par son libellé. À monter
 * conditionnellement : le focus revient au déclencheur au démontage.
 */
function DeleteAccountModal({
  hasPendingExport,
  onClose,
}: {
  /** Avertissement « export en cours perdu » (04 Flux 8, cas limite 🟡). */
  hasPendingExport: boolean;
  onClose: () => void;
}) {
  const t = useTranslations("settings.danger.modal");
  const tRoot = useTranslations();
  const baseId = useId();
  const dialogRef = useRef<HTMLDivElement>(null);
  const passwordRef = useRef<HTMLInputElement>(null);

  const [password, setPassword] = useState("");
  const [fieldError, setFieldError] = useState<string | null>(null);
  const [serverError, setServerError] = useState<string | null>(null);
  const [deleted, setDeleted] = useState(false);

  // Focus initial sur le champ mot de passe + restitution au démontage.
  useEffect(() => {
    const previouslyFocused = document.activeElement as HTMLElement | null;
    passwordRef.current?.focus();
    return () => previouslyFocused?.focus();
  }, []);

  const deleteMutation = useMutation({
    mutationFn: () => deleteAccount(password),
    onSuccess: () => {
      // Session terminée côté API (cookies effacés). Confirmation annoncée
      // puis navigation « dure » vers SCR-01 : l'état client est abandonné.
      setDeleted(true);
      window.setTimeout(() => {
        window.location.assign("/connexion?notice=account-deleted");
      }, DELETE_REDIRECT_DELAY_MS);
    },
    onError: (error) => {
      if (isApiProblem(error) && error.status === 401) {
        // Erreur inline sur le champ, la modale reste ouverte (04 Flux 8).
        setFieldError(t("errors.invalidPassword"));
        requestAnimationFrame(() => passwordRef.current?.focus());
      } else if (isApiProblem(error) && error.status === 429) {
        setServerError(t("errors.rateLimited", { seconds: error.retryAfter ?? 60 }));
      } else {
        setServerError(tRoot("errors.unexpected"));
      }
    },
  });

  const busy = deleteMutation.isPending || deleted;

  /** Piège de focus minimal : Tab boucle dans la modale, Échap annule. */
  const handleKeyDown = (event: KeyboardEvent) => {
    if (event.key === "Escape") {
      event.stopPropagation();
      if (!busy) onClose();
      return;
    }
    if (event.key !== "Tab" || !dialogRef.current) return;
    const focusables = [
      ...dialogRef.current.querySelectorAll<HTMLElement>(
        'a[href], button:not([disabled]), input:not([disabled]), [tabindex]:not([tabindex="-1"])',
      ),
    ];
    if (focusables.length === 0) return;
    const first = focusables[0];
    const last = focusables[focusables.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  };

  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    setServerError(null);
    if (password === "") {
      setFieldError(tRoot("validation.required"));
      passwordRef.current?.focus();
      return;
    }
    setFieldError(null);
    deleteMutation.mutate();
  };

  const titleId = `${baseId}-title`;
  const descriptionId = `${baseId}-description`;
  const passwordId = `${baseId}-password`;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center overflow-y-auto p-4"
      onKeyDown={handleKeyDown}
    >
      {/* Voile d'arrière-plan (les tokens n'exposent pas d'alpha : opacité dédiée). */}
      <div aria-hidden="true" className="absolute inset-0 bg-content opacity-40" />
      <div
        ref={dialogRef}
        role="alertdialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={descriptionId}
        className="relative my-8 w-full max-w-lg space-y-4 rounded-lg border border-border bg-surface p-6"
      >
        <h2 id={titleId} className="text-lg font-semibold text-content">
          {t("title")}
        </h2>

        {/* Corps M5 exact (04 §M) — tout écart repasse par la revue produit. */}
        <div id={descriptionId} className="space-y-3 text-sm text-content">
          <p>{t("body1")}</p>
          <p>{t("body2")}</p>
          <p>{t("body3")}</p>
        </div>

        {hasPendingExport ? (
          <Alert variant="warning">{t("pendingExportWarning")}</Alert>
        ) : null}

        {serverError ? <Alert variant="error">{serverError}</Alert> : null}

        {deleted ? (
          // Confirmation finale annoncée avant la redirection (04 Flux 8 a11y).
          <Alert variant="success">{t("success")}</Alert>
        ) : (
          <form onSubmit={onSubmit} noValidate className="space-y-4">
            <FormField
              id={passwordId}
              label={t("passwordLabel")}
              error={fieldError ?? undefined}
              required
            >
              <Input
                ref={passwordRef}
                id={passwordId}
                type="password"
                autoComplete="current-password"
                required
                value={password}
                onChange={(event) => {
                  setPassword(event.target.value);
                  setFieldError(null);
                }}
                aria-invalid={fieldError ? true : undefined}
                aria-describedby={fieldDescribedBy(passwordId, { error: Boolean(fieldError) })}
              />
            </FormField>

            {/* M5 : « Supprimer mon compte » (destructif) · « Annuler » (défaut). */}
            <div className="flex flex-wrap gap-3">
              <Button
                type="submit"
                variant="destructive"
                disabled={busy}
                aria-busy={deleteMutation.isPending}
              >
                {t("confirm")}
              </Button>
              <Button type="button" variant="secondary" onClick={onClose} disabled={busy}>
                {t("cancel")}
              </Button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}

export default function SettingsPage() {
  const t = useTranslations("settings");
  const tRoot = useTranslations();
  const locale = useLocale();

  /* ----------------------- Mes données (SCR-71) ----------------------- */

  const [exportId, setExportId] = useState<string | null>(null);
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);

  // Idempotency-Key UUID conservée tant que la demande n'a pas abouti : un
  // ré-essai après erreur réseau rejoue la même clé (Idempotent-Replay, 12 §1
  // — le rejeu ne consomme pas le quota). Régénérée pour un NOUVEL export
  // (sinon le rejeu renverrait l'export expiré).
  const idempotencyKeyRef = useRef<string | null>(null);

  const exportMutation = useMutation({
    mutationFn: () => {
      idempotencyKeyRef.current ??= crypto.randomUUID();
      return requestPrivacyExport(idempotencyKeyRef.current);
    },
    onSuccess: (requested) => setExportId(requested.id),
  });

  const startNewExport = () => {
    idempotencyKeyRef.current = crypto.randomUUID();
    exportMutation.mutate();
  };

  const exportQuery = useQuery({
    queryKey: privacyKeys.export(exportId ?? ""),
    queryFn: ({ signal }) => getPrivacyExport(exportId ?? "", signal),
    enabled: exportId !== null,
    // Polling 2 s ×1,5 (12 §1) tant que l'export n'est pas `ready`/`expired`.
    refetchInterval: makePollingInterval(isPrivacyExportSettled),
  });

  const exportData = exportId !== null ? exportQuery.data : undefined;
  const isPreparing =
    exportId !== null &&
    !exportQuery.isError &&
    (exportData === undefined || exportData.status === "pending");
  const isReady = exportData?.status === "ready" && exportData.download_url != null;
  const isExpired = exportData?.status === "expired";

  let exportError: string | null = null;
  if (exportMutation.error) {
    if (isApiProblem(exportMutation.error) && exportMutation.error.status === 429) {
      // Quota 2/j atteint (RM-Q-3) — heure de déblocage depuis Retry-After.
      const unlockAt = new Date(Date.now() + (exportMutation.error.retryAfter ?? 3600) * 1000);
      exportError = t("data.quotaReached", {
        limit: PRIVACY_EXPORT_DAILY_LIMIT,
        time: new Intl.DateTimeFormat(locale, { timeStyle: "short" }).format(unlockAt),
      });
    } else {
      exportError = tRoot("errors.unexpected");
    }
  }

  /* ------------------ Sources et transparence (SCR-73) ------------------ */

  const sourcesQuery = useQuery({
    queryKey: jobsKeys.sources,
    queryFn: ({ signal }) => getSources(signal),
    staleTime: Number.POSITIVE_INFINITY,
  });

  return (
    <section aria-labelledby="settings-title" className="space-y-8">
      <h1 id="settings-title" className="text-2xl font-semibold text-content">
        {t("title")}
      </h1>

      {/* ------------------------- Mes données ------------------------- */}
      <section
        aria-labelledby="settings-data-title"
        className="space-y-4 rounded-lg border border-border bg-surface p-6"
      >
        <h2 id="settings-data-title" className="text-lg font-semibold text-content">
          {t("data.title")}
        </h2>
        {/* Note de transparence : contenu de l'archive (SCR-71). */}
        <p className="text-sm text-content-secondary">{t("data.archiveNote")}</p>

        <Button
          onClick={() => exportMutation.mutate()}
          disabled={exportMutation.isPending || isPreparing}
          aria-busy={exportMutation.isPending}
        >
          {t("data.exportCta")}
        </Button>

        {exportError ? <Alert variant="error">{exportError}</Alert> : null}
        {exportQuery.isError ? (
          <Alert variant="error">{tRoot("errors.unexpected")}</Alert>
        ) : null}

        {isPreparing ? (
          <p role="status" aria-live="polite" className="text-sm text-content-secondary">
            {t("data.preparing")}
          </p>
        ) : null}

        {isReady ? (
          <Alert variant="success" title={t("data.readyTitle")}>
            <p>
              {/* Lien signé relatif fourni par l'API — utilisé tel quel. */}
              <a
                href={exportData?.download_url ?? undefined}
                className="font-medium underline underline-offset-4 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
              >
                {t("data.downloadCta")}
              </a>
            </p>
            <p className="mt-1">{t("data.validity", { days: PRIVACY_EXPORT_LINK_TTL_DAYS })}</p>
          </Alert>
        ) : null}

        {isExpired ? (
          <Alert variant="warning" title={t("data.expiredTitle")}>
            <p>{t("data.expiredBody")}</p>
            <Button
              variant="secondary"
              className="mt-2"
              onClick={startNewExport}
              disabled={exportMutation.isPending}
            >
              {t("data.requestAgainCta")}
            </Button>
          </Alert>
        ) : null}
      </section>

      {/* ------------------ Sources et transparence ------------------- */}
      <section
        aria-labelledby="settings-sources-title"
        className="space-y-4 rounded-lg border border-border bg-surface p-6"
      >
        <h2 id="settings-sources-title" className="text-lg font-semibold text-content">
          {t("sources.title")}
        </h2>

        {sourcesQuery.isPending ? (
          <p role="status" aria-live="polite" className="text-sm text-content-secondary">
            {tRoot("common.loading")}
          </p>
        ) : null}
        {sourcesQuery.isError ? (
          <Alert variant="error">{t("sources.loadError")}</Alert>
        ) : null}

        {sourcesQuery.data ? (
          <>
            {/* Rappel M6-b — « pas “tout le web” ». */}
            <p className="text-sm text-content">
              {t("sources.reminder", { count: sourcesQuery.data.length })}
            </p>
            <ul className="space-y-2">
              {sourcesQuery.data.map((source) => {
                const lastSync = formatDateTime(source.last_sync_at, locale);
                return (
                  <li
                    key={source.slug}
                    className="rounded-md border border-border p-3 text-sm text-content"
                  >
                    <span className="font-medium">{source.name}</span>
                    <span className="text-content-secondary">
                      {" — "}
                      {t(`sources.kind.${source.kind}`)}
                      {" · "}
                      {lastSync
                        ? t("sources.lastSync", { date: lastSync })
                        : t("sources.lastSyncUnknown")}
                    </span>
                  </li>
                );
              })}
            </ul>
          </>
        ) : null}

        <p className="text-sm">
          {/* 🟡 TODO contenu légal : politique de confidentialité à publier. */}
          <a
            href="#"
            className="font-medium text-action-primary underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
          >
            {t("sources.policyLink")}
          </a>
        </p>
      </section>

      {/* ------------------------ Zone dangereuse ---------------------- */}
      <section
        aria-labelledby="settings-danger-title"
        className="space-y-4 rounded-lg border border-feedback-error p-6"
      >
        <h2 id="settings-danger-title" className="text-lg font-semibold text-feedback-error">
          {t("danger.title")}
        </h2>
        {/* Conséquences + proposition d'export préalable (04 Flux 8 §2). */}
        <p className="text-sm text-content">{t("danger.description")}</p>
        <p className="text-sm text-content-secondary">{t("danger.exportFirst")}</p>
        <Button variant="destructive" onClick={() => setDeleteModalOpen(true)}>
          {t("danger.deleteCta")}
        </Button>
      </section>

      {deleteModalOpen ? (
        <DeleteAccountModal
          hasPendingExport={isPreparing}
          onClose={() => setDeleteModalOpen(false)}
        />
      ) : null}
    </section>
  );
}
