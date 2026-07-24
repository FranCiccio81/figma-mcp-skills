"use client";

// SCR-02 — M1

import { zodResolver } from "@hookform/resolvers/zod";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useMemo, useRef, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { FormField, fieldDescribedBy } from "@/components/ui/form-field";
import { Input } from "@/components/ui/input";
import { apiFetch, isApiProblem } from "@/lib/api/client";
import type { RegisterInput } from "@/lib/api/types";
import { CONSENT_PRIVACY_VERSION, CONSENT_TERMS_VERSION } from "@/lib/constants";

/**
 * SCR-02 — Inscription : email + mot de passe (≥ 12 caractères) + consentements
 * explicites obligatoires (CGU/traitement et confidentialité, D09).
 * `POST /auth/register` → 201 (session ouverte) → tableau de bord (l'import CV,
 * SCR-05, arrive plus tard dans M1). 409 → message générique anti-énumération ;
 * 422 → `errors[]` mappées par champ.
 */
export default function RegisterPage() {
  const t = useTranslations();
  const router = useRouter();
  const serverErrorRef = useRef<HTMLDivElement>(null);
  const [serverError, setServerError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const schema = useMemo(
    () =>
      z.object({
        email: z.string().min(1, t("validation.required")).email(t("validation.emailInvalid")),
        password: z.string().min(12, t("validation.passwordTooShort")),
        acceptTerms: z.boolean().refine((value) => value, t("validation.consentRequired")),
        acceptPrivacy: z.boolean().refine((value) => value, t("validation.consentRequired")),
      }),
    [t],
  );

  type FormValues = z.infer<typeof schema>;

  const {
    register,
    handleSubmit,
    setError,
    formState: { errors },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    mode: "onTouched",
    defaultValues: { email: "", password: "", acceptTerms: false, acceptPrivacy: false },
  });

  const onSubmit = handleSubmit(async (values) => {
    setServerError(null);
    setSubmitting(true);

    const payload: RegisterInput = {
      email: values.email,
      password: values.password,
      locale: "fr",
      accepted_terms_version: CONSENT_TERMS_VERSION,
      accepted_privacy_version: CONSENT_PRIVACY_VERSION,
    };

    try {
      await apiFetch<unknown>("/auth/register", { method: "POST", body: payload });
      router.replace("/tableau-de-bord");
      router.refresh();
    } catch (error) {
      if (isApiProblem(error)) {
        if (error.status === 409) {
          setServerError(t("auth.register.errors.emailUnavailable"));
        } else if (error.status === 429) {
          setServerError(
            t("auth.register.errors.rateLimited", { seconds: error.retryAfter ?? 60 }),
          );
        } else if (error.status === 422 && error.errors.length > 0) {
          for (const fieldError of error.errors) {
            if (fieldError.field === "email" || fieldError.field === "password") {
              setError(fieldError.field, { type: "server", message: fieldError.message });
            }
          }
          if (!error.errors.some((e) => e.field === "email" || e.field === "password")) {
            setServerError(error.detail ?? t("errors.unexpected"));
          }
        } else {
          setServerError(error.detail ?? t("errors.unexpected"));
        }
      } else {
        setServerError(t("errors.unexpected"));
      }
      setSubmitting(false);
      requestAnimationFrame(() => serverErrorRef.current?.focus());
    }
  });

  return (
    <>
      <h1 className="text-xl font-semibold text-content">{t("auth.register.title")}</h1>

      {serverError ? (
        <Alert ref={serverErrorRef} tabIndex={-1} variant="error" className="mt-4">
          {serverError}
        </Alert>
      ) : null}

      <form onSubmit={onSubmit} noValidate className="mt-6 space-y-4">
        <FormField id="email" label={t("auth.register.emailLabel")} error={errors.email?.message}>
          <Input
            id="email"
            type="email"
            autoComplete="email"
            aria-invalid={errors.email ? true : undefined}
            aria-describedby={fieldDescribedBy("email", { error: Boolean(errors.email) })}
            {...register("email")}
          />
        </FormField>

        <FormField
          id="password"
          label={t("auth.register.passwordLabel")}
          description={t("auth.register.passwordHint")}
          error={errors.password?.message}
        >
          <Input
            id="password"
            type="password"
            autoComplete="new-password"
            aria-invalid={errors.password ? true : undefined}
            aria-describedby={fieldDescribedBy("password", {
              description: true,
              error: Boolean(errors.password),
            })}
            {...register("password")}
          />
        </FormField>

        <fieldset className="space-y-3">
          <legend className="text-sm font-medium text-content">
            {t("auth.register.consentsLegend")}
          </legend>

          <label htmlFor="acceptTerms" className="flex min-h-11 items-start gap-3 py-1">
            <input
              id="acceptTerms"
              type="checkbox"
              className="mt-0.5 h-5 w-5 shrink-0 accent-action-primary"
              aria-invalid={errors.acceptTerms ? true : undefined}
              aria-describedby={errors.acceptTerms ? "acceptTerms-error" : undefined}
              {...register("acceptTerms")}
            />
            <span className="text-sm text-content">{t("auth.register.termsLabel")}</span>
          </label>
          {errors.acceptTerms ? (
            <p id="acceptTerms-error" role="alert" className="text-sm font-medium text-feedback-error">
              {errors.acceptTerms.message}
            </p>
          ) : null}

          <label htmlFor="acceptPrivacy" className="flex min-h-11 items-start gap-3 py-1">
            <input
              id="acceptPrivacy"
              type="checkbox"
              className="mt-0.5 h-5 w-5 shrink-0 accent-action-primary"
              aria-invalid={errors.acceptPrivacy ? true : undefined}
              aria-describedby={errors.acceptPrivacy ? "acceptPrivacy-error" : undefined}
              {...register("acceptPrivacy")}
            />
            <span className="text-sm text-content">{t("auth.register.privacyLabel")}</span>
          </label>
          {errors.acceptPrivacy ? (
            <p
              id="acceptPrivacy-error"
              role="alert"
              className="text-sm font-medium text-feedback-error"
            >
              {errors.acceptPrivacy.message}
            </p>
          ) : null}
        </fieldset>

        <Button type="submit" className="w-full" disabled={submitting} aria-busy={submitting}>
          {submitting ? t("common.loading") : t("auth.register.submit")}
        </Button>
      </form>

      <p className="mt-6 text-sm text-content-secondary">
        {t("auth.register.haveAccount")}{" "}
        <Link
          href="/connexion"
          className="font-medium text-action-primary underline-offset-4 hover:underline"
        >
          {t("auth.register.loginLink")}
        </Link>
      </p>

      <p className="mt-8 border-t border-border pt-4 text-center text-xs text-content-secondary">
        {t("auth.register.euHostingNotice")}
      </p>
    </>
  );
}
