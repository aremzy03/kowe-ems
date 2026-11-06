"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { AuthShell } from "@/components/layout/AuthShell";
import { Button, Input, Label } from "@/components/ui";
import { applyLogin, login } from "@/lib/api/auth";
import { ApiRequestError } from "@/lib/api/client";
import { useAuth } from "@/lib/auth/auth-provider";

const schema = z.object({
  email: z.string().email(),
  password: z.string().min(1),
});

type FormValues = z.infer<typeof schema>;

export default function PlatformLoginPage() {
  const router = useRouter();
  const { setSession } = useAuth();
  const [formError, setFormError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    formState: { isSubmitting },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { email: "", password: "" },
  });

  async function onSubmit(values: FormValues) {
    setFormError(null);
    try {
      const data = await login(values.email, values.password);
      if (!data.access || data.role !== "platform_admin") {
        setFormError(
          data.role && data.role !== "platform_admin"
            ? "This account is not a platform admin. Use the school subdomain UI."
            : "Unexpected login response.",
        );
        return;
      }
      applyLogin(data);
      setSession(data.access, data.role);
      router.push("/");
    } catch (err) {
      if (err instanceof ApiRequestError) {
        setFormError(err.detail ?? err.message);
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
          Platform
        </p>
        <h1
          className="text-4xl font-bold tracking-tight"
          style={{ fontFamily: "var(--font-heading)" }}
        >
          EMS
        </h1>
        <p className="mt-2 text-ink/75">
          Operator sign-in. No school tenant header is sent.
        </p>
      </div>
      <div className="rounded-[var(--radius-nb-lg)] border-[3.5px] border-ink bg-paper-card p-6 shadow-nb-lg">
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div>
            <Label htmlFor="email">Email</Label>
            <Input id="email" type="email" autoComplete="username" {...register("email")} />
          </div>
          <div>
            <Label htmlFor="password">Password</Label>
            <Input
              id="password"
              type="password"
              autoComplete="current-password"
              {...register("password")}
            />
          </div>
          {formError ? (
            <p className="rounded-[var(--radius-nb-sm)] border-[1.5px] border-danger bg-danger/10 px-3 py-2 text-sm">
              {formError}
            </p>
          ) : null}
          <Button type="submit" className="w-full" size="lg" disabled={isSubmitting}>
            {isSubmitting ? "Signing in…" : "Sign in"}
          </Button>
        </form>
      </div>
    </AuthShell>
  );
}
