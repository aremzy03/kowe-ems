"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { AuthShell } from "@/components/layout/AuthShell";
import { Button, Input, Label } from "@/components/ui";
import { parentSignup } from "@/lib/api/auth";
import { ApiRequestError } from "@/lib/api/client";
import { mapDrfErrors } from "@/lib/api/errors";

const schema = z.object({
  first_name: z.string().min(1, "First name is required"),
  last_name: z.string().min(1, "Last name is required"),
  email: z.string().email("Enter a valid email"),
  password: z.string().min(8, "Password must be at least 8 characters"),
});

type FormValues = z.infer<typeof schema>;

export default function ParentSignupPage() {
  const router = useRouter();
  const [formError, setFormError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      first_name: "",
      last_name: "",
      email: "",
      password: "",
    },
  });

  async function onSubmit(values: FormValues) {
    setFormError(null);
    try {
      await parentSignup(values);
      router.push("/login");
    } catch (err) {
      if (err instanceof ApiRequestError) {
        const mapped = mapDrfErrors(err.data);
        for (const [k, v] of Object.entries(mapped.fields)) {
          if (k in values) setError(k as keyof FormValues, { message: v });
        }
        setFormError(mapped.form ?? err.message);
      } else {
        setFormError(err instanceof Error ? err.message : "Signup failed");
      }
    }
  }

  return (
    <AuthShell>
      <div className="rounded-[var(--radius-nb-lg)] border-[3.5px] border-ink bg-paper-card p-6 shadow-nb-lg sm:p-8">
        <p
          className="mb-1 text-sm text-accent-1"
          style={{ fontFamily: "var(--font-accent)" }}
        >
          Parent account
        </p>
        <h1
          className="text-3xl font-bold"
          style={{ fontFamily: "var(--font-heading)" }}
        >
          Parent signup
        </h1>
        <p className="mt-2 text-ink/75">
          Create an account on this school subdomain, then link your child with a
          linking code.
        </p>

        <form onSubmit={handleSubmit(onSubmit)} className="mt-6 space-y-4">
          <div>
            <Label htmlFor="first_name">First name</Label>
            <Input id="first_name" autoComplete="given-name" {...register("first_name")} />
            {errors.first_name ? (
              <p className="mt-1 text-sm text-danger">{errors.first_name.message}</p>
            ) : null}
          </div>
          <div>
            <Label htmlFor="last_name">Last name</Label>
            <Input id="last_name" autoComplete="family-name" {...register("last_name")} />
            {errors.last_name ? (
              <p className="mt-1 text-sm text-danger">{errors.last_name.message}</p>
            ) : null}
          </div>
          <div>
            <Label htmlFor="email">Email</Label>
            <Input id="email" type="email" autoComplete="email" {...register("email")} />
            {errors.email ? (
              <p className="mt-1 text-sm text-danger">{errors.email.message}</p>
            ) : null}
          </div>
          <div>
            <Label htmlFor="password">Password</Label>
            <Input
              id="password"
              type="password"
              autoComplete="new-password"
              {...register("password")}
            />
            {errors.password ? (
              <p className="mt-1 text-sm text-danger">{errors.password.message}</p>
            ) : null}
          </div>
          {formError ? (
            <p className="text-sm font-medium text-danger">{formError}</p>
          ) : null}
          <Button type="submit" className="w-full" size="lg" disabled={isSubmitting}>
            {isSubmitting ? "Creating…" : "Create account"}
          </Button>
        </form>

        <p className="mt-5 text-center text-sm text-ink/70">
          Already registered?{" "}
          <Link href="/login" className="font-semibold text-accent-1 underline">
            Sign in
          </Link>
        </p>
      </div>
    </AuthShell>
  );
}
