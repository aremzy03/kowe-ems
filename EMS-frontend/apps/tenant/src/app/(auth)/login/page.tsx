"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { AuthShell } from "@/components/layout/AuthShell";
import { Button, Input, Label } from "@/components/ui";
import { cn } from "@/lib/cn";
import {
  applyAuthSuccess,
  applyPreAuthChallenge,
  login,
  navigateAfterAuth,
} from "@/lib/api/auth";
import { ApiRequestError } from "@/lib/api/client";
import { mapDrfErrors } from "@/lib/api/errors";
import { PLATFORM_ORIGIN } from "@/lib/api/config";
import { useAuth } from "@/lib/auth/auth-provider";
import {
  LOGIN_ROLE_OPTIONS,
  MOCK_USERS,
  type MockRole,
} from "@/lib/mocks/session";
import { beginMockLogin } from "@/lib/mocks/session-client";

const schema = z.object({
  email: z.string().email("Enter a valid email"),
  password: z.string().min(1, "Password is required"),
});

type FormValues = z.infer<typeof schema>;

const roleAccent: Partial<Record<MockRole, string>> = {
  bursar: "border-t-[6px] border-t-accent-2",
  admin: "border-t-[6px] border-t-accent-1",
};

const useMocks = process.env.NEXT_PUBLIC_USE_MOCKS === "true";

function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { setSession } = useAuth();
  const [formError, setFormError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { email: "", password: "" },
  });

  async function onSubmit(values: FormValues) {
    setFormError(null);
    try {
      const data = await login(values.email, values.password);
      if (data.requires_2fa && data.pre_auth_token) {
        applyPreAuthChallenge(data);
        if (data.enrollment_required) {
          router.push("/2fa/setup");
        } else {
          router.push("/2fa/verify");
        }
        return;
      }
      if (data.access && data.role) {
        applyAuthSuccess(data);
        setSession(data.access, data.role);
        navigateAfterAuth(data.role, router, searchParams.get("next"));
        return;
      }
      setFormError("Unexpected login response. Try again.");
    } catch (err) {
      if (err instanceof ApiRequestError) {
        const mapped = mapDrfErrors(err.data);
        if (mapped.fields.email) setError("email", { message: mapped.fields.email });
        if (mapped.fields.password)
          setError("password", { message: mapped.fields.password });
        setFormError(mapped.form ?? err.message);
      } else {
        setFormError(err instanceof Error ? err.message : "Login failed");
      }
    }
  }

  return (
    <AuthShell>
      <div className="mb-8 text-center">
        <p
          className="mb-1 text-lg text-accent-1"
          style={{ fontFamily: "var(--font-accent)" }}
        >
          School sign-in
        </p>
        <h1
          className="text-4xl font-bold tracking-tight"
          style={{ fontFamily: "var(--font-heading)" }}
        >
          EMS
        </h1>
        <p className="mt-2 text-ink/75">
          Sign in on your school subdomain. Admins and bursars complete 2FA next.
        </p>
      </div>

      <div className="rounded-[var(--radius-nb-lg)] border-[3.5px] border-ink bg-paper-card p-6 shadow-nb-lg">
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div>
            <Label htmlFor="email">Email</Label>
            <Input
              id="email"
              type="email"
              autoComplete="username"
              {...register("email")}
            />
            {errors.email ? (
              <p className="mt-1 text-sm text-danger">{errors.email.message}</p>
            ) : null}
          </div>
          <div>
            <Label htmlFor="password">Password</Label>
            <Input
              id="password"
              type="password"
              autoComplete="current-password"
              {...register("password")}
            />
            {errors.password ? (
              <p className="mt-1 text-sm text-danger">{errors.password.message}</p>
            ) : null}
          </div>
          {formError ? (
            <p className="rounded-[var(--radius-nb-sm)] border-[1.5px] border-danger bg-danger/10 px-3 py-2 text-sm font-medium text-ink">
              {formError}
            </p>
          ) : null}
          <Button type="submit" className="w-full" size="lg" disabled={isSubmitting}>
            {isSubmitting ? "Signing in…" : "Sign in"}
          </Button>
        </form>

        {useMocks ? (
          <div className="mt-6 border-t-[2.5px] border-ink pt-5">
            <h2
              className="mb-3 text-lg font-bold"
              style={{ fontFamily: "var(--font-heading)" }}
            >
              Quick pick (dev mocks)
            </h2>
            <div className="flex flex-col gap-2">
              {LOGIN_ROLE_OPTIONS.filter((o) => o.role !== "platform_admin").map(
                (option) => (
                  <button
                    key={option.role}
                    type="button"
                    onClick={() => beginMockLogin(option.role)}
                    className={cn(
                      "nb-interactive rounded-[var(--radius-nb)] border-[2.5px] border-ink bg-paper px-4 py-3 text-left shadow-nb hover:shadow-nb-lg",
                      roleAccent[option.role] ?? "",
                    )}
                  >
                    <span
                      className="block font-bold"
                      style={{ fontFamily: "var(--font-heading)" }}
                    >
                      Continue as {option.label}
                    </span>
                    <span className="text-sm text-ink/70">
                      {option.description} ·{" "}
                      <span style={{ fontFamily: "var(--font-mono)" }}>
                        {MOCK_USERS[option.role].email}
                      </span>
                    </span>
                  </button>
                ),
              )}
            </div>
          </div>
        ) : null}
      </div>

      <p className="mt-6 text-center text-sm">
        New parent?{" "}
        <Link href="/parents/signup" className="font-semibold text-accent-1 underline">
          Create a parent account
        </Link>
      </p>
      <p className="mt-2 text-center text-sm text-ink/70">
        Platform operators:{" "}
        <a href={PLATFORM_ORIGIN} className="font-semibold text-accent-1 underline">
          open platform admin
        </a>
      </p>
      <p className="mt-2 text-center">
        <Link
          href="/"
          className="nb-interactive inline-flex items-center rounded-[var(--radius-nb)] border-[2.5px] border-transparent px-3 py-1.5 text-sm font-semibold text-ink hover:border-ink hover:bg-paper-card hover:shadow-nb-sm"
        >
          ← Portal home
        </Link>
      </p>
    </AuthShell>
  );
}

export default function LoginPage() {
  return (
    <Suspense
      fallback={
        <AuthShell>
          <p className="text-center text-ink/70">Loading…</p>
        </AuthShell>
      }
    >
      <LoginForm />
    </Suspense>
  );
}
