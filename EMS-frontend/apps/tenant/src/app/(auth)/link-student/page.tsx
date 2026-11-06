"use client";

import Link from "next/link";
import { useState, type FormEvent } from "react";
import { AuthShell } from "@/components/layout/AuthShell";
import { Button, Input, Label } from "@/components/ui";
import { apiFetch, ApiRequestError } from "@/lib/api/client";
import { mapDrfErrors } from "@/lib/api/errors";

type RedeemResponse = {
  detail?: string;
  student_id?: string;
  code?: string;
};

export default function LinkStudentPage() {
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [linkedId, setLinkedId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    const normalized = code.trim();
    if (normalized.length < 4) {
      setError("Enter the linking code from your school.");
      return;
    }
    setBusy(true);
    try {
      const data = await apiFetch<RedeemResponse>(
        "/api/academics/linking-codes/redeem/",
        {
          method: "POST",
          body: {
            code: normalized,
            relationship_to_student: "guardian",
          },
          auth: true,
          scope: "tenant",
        },
      );
      setLinkedId(data.student_id ?? "linked");
    } catch (err) {
      if (err instanceof ApiRequestError) {
        setError(mapDrfErrors(err.data).form ?? err.message);
      } else {
        setError(err instanceof Error ? err.message : "Link failed");
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthShell>
      <div className="rounded-[var(--radius-nb-lg)] border-[3.5px] border-ink bg-paper-card p-6 shadow-nb-lg sm:p-8">
        <p
          className="mb-1 text-sm text-accent-1"
          style={{ fontFamily: "var(--font-accent)" }}
        >
          Parent
        </p>
        <h1
          className="text-3xl font-bold"
          style={{ fontFamily: "var(--font-heading)" }}
        >
          Link student
        </h1>
        <p className="mt-2 text-ink/75">
          Enter the school-issued linking code to connect your child to this
          parent account.
        </p>

        {linkedId ? (
          <div className="mt-6 space-y-4">
            <div className="rounded-[var(--radius-nb)] border-[2.5px] border-ink bg-success/15 px-4 py-3 shadow-nb-sm">
              <p className="font-semibold text-ink">Linked successfully</p>
              <p className="mt-1 text-sm text-ink/70">
                Student id:{" "}
                <span style={{ fontFamily: "var(--font-mono)" }}>{linkedId}</span>
              </p>
            </div>
            <Link href="/parent">
              <Button className="w-full" size="lg">
                Go to parent home
              </Button>
            </Link>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="mt-6 space-y-4">
            <div>
              <Label htmlFor="linking-code">Linking code</Label>
              <Input
                id="linking-code"
                value={code}
                onChange={(e) => setCode(e.target.value)}
                autoComplete="off"
                style={{ fontFamily: "var(--font-mono)" }}
              />
            </div>
            {error ? (
              <p className="text-sm font-medium text-danger">{error}</p>
            ) : null}
            <Button type="submit" className="w-full" size="lg" disabled={busy}>
              {busy ? "Linking…" : "Link student"}
            </Button>
          </form>
        )}

        <p className="mt-4">
          <Link href="/parent" className="text-sm font-semibold text-ink underline">
            Back to parent portal
          </Link>
        </p>
      </div>
    </AuthShell>
  );
}
