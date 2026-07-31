"use client";

// SCR-01 — M1

import { zodResolver } from "@hookform/resolvers/zod";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { Suspense, useMemo, useRef, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { FormField, fieldDescribedBy } from "@/components/ui/form-field";
import { Input } from "@/components/ui/input";
import { apiFetch, isApiProblem } from "@/lib/api/client";
import type { LoginInput } from "@/lib/api/types";
import { useProblemMessage } from "@/lib/api/problem-message";

/**
 * SCR-01 — Connexion. `POST /auth/login` (204, cookie httpOnly) puis
 * redirection vers l'URL cible conservée (`?next=`) ou le tableau de bord.
 * Erreur identifiants générique (anti-énumération), 429 avec `Retry-After`.
 */
function LoginForm() {
  const t = useTranslations();
  const messageErreur = useProblemMessage();
  const router = useRouter();
  const searchParams = useSearchParams();
  const serverErrorRef = useRef<HTMLDivElement>(null);
  const [serverError, setServerError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const schema = useMemo(
    () =>
      z.object({
        email: z.string().min(1, t("validation.required")).email(t("validation.emailInvalid")),
        password: z.string().min(1, t("validation.required")),
      }),
    [t],
  );

  type FormValues = z.infer<typeof schema>;

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<FormValues>({ resolver: zodResolver(schema), mode: "onTouched" });

  const onSubmit = handleSubmit(async (values) => {
    setServerError(null);
    setSubmitting(true);
    try {
      await apiFetch<undefined>("/auth/login", {
        method: "POST",
        body: values satisfies LoginInput,
      });
      const next = searchParams.get("next");
      router.replace(next && next.startsWith("/") ? next : "/tableau-de-bord");
      router.refresh();
    } catch (error) {
      if (isApiProblem(error)) {
        if (error.status === 401) {
          setServerError(t("auth.login.errors.invalidCredentials"));
        } else if (error.status === 429) {
          setServerError(
            t("auth.login.errors.rateLimited", { seconds: error.retryAfter ?? 60 }),
          );
        } else {
          setServerError(messageErreur(error));
        }
      } else {
        setServerError(t("errors.unexpected"));
      }
      setSubmitting(false);
      requestAnimationFrame(() => serverErrorRef.current?.focus());
    }
  });

  // Message de confirmation après suppression de compte (SCR-72 → SCR-01,
  // M5 « Après succès » — redirection avec `?notice=account-deleted`).
  const accountDeleted = searchParams.get("notice") === "account-deleted";

  return (
    <>
      <h1 className="text-xl font-semibold text-content">{t("auth.login.title")}</h1>

      {accountDeleted ? (
        <Alert variant="success" className="mt-4">
          {t("auth.login.accountDeleted")}
        </Alert>
      ) : null}

      {serverError ? (
        <Alert ref={serverErrorRef} tabIndex={-1} variant="error" className="mt-4">
          {serverError}
        </Alert>
      ) : null}

      <form onSubmit={onSubmit} noValidate className="mt-6 space-y-4">
        <FormField id="email" label={t("auth.login.emailLabel")} error={errors.email?.message}>
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
          label={t("auth.login.passwordLabel")}
          error={errors.password?.message}
        >
          <Input
            id="password"
            type="password"
            autoComplete="current-password"
            aria-invalid={errors.password ? true : undefined}
            aria-describedby={fieldDescribedBy("password", { error: Boolean(errors.password) })}
            {...register("password")}
          />
        </FormField>

        <Button type="submit" className="w-full" disabled={submitting} aria-busy={submitting}>
          {submitting ? t("common.loading") : t("auth.login.submit")}
        </Button>
      </form>

      <p className="mt-6 text-sm text-content-secondary">
        {t("auth.login.noAccount")}{" "}
        <Link
          href="/inscription"
          className="font-medium text-action-primary underline-offset-4 hover:underline"
        >
          {t("auth.login.registerLink")}
        </Link>
      </p>

      <p className="mt-8 border-t border-border pt-4 text-center text-xs text-content-secondary">
        {t("auth.login.valueReminder")}
      </p>
    </>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={null}>
      <LoginForm />
    </Suspense>
  );
}
