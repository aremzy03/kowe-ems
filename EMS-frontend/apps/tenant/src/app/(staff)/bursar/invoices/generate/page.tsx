"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Button, Card, CardBody, Label, PageHeader } from "@/components/ui";
import {
  EntitySearchField,
  type EntitySearchOption,
} from "@/components/ui/client";
import { academicsApi, type Session, type Term } from "@/lib/api/academics";
import { financeApi } from "@/lib/api/finance";
import { ApiRequestError } from "@/lib/api/client";
import { mapDrfErrors } from "@/lib/api/errors";

type GenerateResult = {
  created_count?: number;
  skipped_count?: number;
  skipped_student_ids?: string[];
  invoices?: { term_name?: string; session_name?: string; term?: string }[];
};

const ALL_CLASSES = "all";

function termOptionLabel(term: Term, sessions: Session[]) {
  const session =
    term.session_name ||
    sessions.find((s) => s.id === term.session)?.name;
  return session ? `${session} · ${term.name}` : term.name;
}

export default function GenerateInvoicesPage() {
  const [classLevel, setClassLevel] = useState("");
  const [term, setTerm] = useState("");
  const [arm, setArm] = useState("");
  const [result, setResult] = useState<GenerateResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const classLevels = useQuery({
    queryKey: ["academics", "class-levels"],
    queryFn: () => academicsApi.classLevels.list(),
  });
  const sessions = useQuery({
    queryKey: ["academics", "sessions"],
    queryFn: () => academicsApi.sessions.list(),
  });
  const terms = useQuery({
    queryKey: ["academics", "terms"],
    queryFn: () => academicsApi.terms.list(),
  });
  const arms = useQuery({
    queryKey: ["academics", "arms"],
    queryFn: () => academicsApi.arms.list(),
  });

  const classOptions: EntitySearchOption[] = useMemo(
    () => [
      { id: ALL_CLASSES, label: "All classes" },
      ...(classLevels.data ?? []).map((level) => ({
        id: level.id,
        label: level.name,
      })),
    ],
    [classLevels.data],
  );

  const termOptions: EntitySearchOption[] = useMemo(
    () =>
      (terms.data ?? []).map((t) => ({
        id: t.id,
        label: termOptionLabel(t, sessions.data ?? []),
        keywords: t.name,
      })),
    [terms.data, sessions.data],
  );

  const armOptions: EntitySearchOption[] = useMemo(
    () =>
      (arms.data ?? [])
        .filter((a) => !classLevel || a.class_level === classLevel)
        .map((a) => ({
          id: a.id,
          label: a.name,
          keywords: a.class_level,
        })),
    [arms.data, classLevel],
  );

  const allClasses = classLevel === ALL_CLASSES;

  const generate = useMutation({
    mutationFn: () =>
      financeApi.generateInvoices({
        term,
        ...(allClasses ? {} : { class_level: classLevel }),
        ...(arm && !allClasses ? { arm } : {}),
      }) as Promise<GenerateResult>,
    onSuccess: (data) => {
      setResult(data ?? {});
      setError(null);
    },
    onError: (err) => {
      setError(
        err instanceof ApiRequestError
          ? mapDrfErrors(err.data).form ?? err.message
          : "Generate failed",
      );
    },
  });

  const created = result?.created_count ?? 0;
  const skipped = result?.skipped_count ?? 0;
  const sample = result?.invoices?.[0];
  const selectedTerm = termOptions.find((o) => o.id === term);
  const termLabel =
    [sample?.session_name, sample?.term_name].filter(Boolean).join(" · ") ||
    selectedTerm?.label ||
    "selected term";

  return (
    <div className="mx-auto max-w-lg space-y-6">
      <PageHeader
        title="Generate invoices"
        description="Create invoices for one class, or every class, in a term"
      />
      <Card>
        <CardBody className="space-y-3">
          <div>
            <Label htmlFor="gen-class">Class level</Label>
            <EntitySearchField
              id="gen-class"
              value={classLevel}
              onChange={(id) => {
                setClassLevel(id);
                setArm("");
              }}
              options={classOptions}
              loading={classLevels.isLoading}
              placeholder="Search class level, or all classes…"
              emptyMessage="No class levels found"
            />
          </div>
          <div>
            <Label htmlFor="gen-term">Term</Label>
            <EntitySearchField
              id="gen-term"
              value={term}
              onChange={setTerm}
              options={termOptions}
              loading={terms.isLoading || sessions.isLoading}
              placeholder="Search session · term…"
              emptyMessage="No terms found"
            />
          </div>
          <div>
            <Label htmlFor="gen-arm">Arm (optional)</Label>
            <EntitySearchField
              id="gen-arm"
              value={arm}
              onChange={setArm}
              options={armOptions}
              loading={arms.isLoading}
              disabled={!classLevel || allClasses}
              placeholder={
                allClasses
                  ? "Not used when generating every class"
                  : classLevel
                    ? "Search arm…"
                    : "Choose a class level first"
              }
              emptyMessage="No arms for this class"
            />
          </div>
          {error ? <p className="text-sm text-danger">{error}</p> : null}
          <Button
            disabled={generate.isPending || !classLevel || !term}
            onClick={() => generate.mutate()}
          >
            {generate.isPending ? "Generating…" : "Generate"}
          </Button>
          {result ? (
            <div className="space-y-3 rounded-[var(--radius-nb-sm)] border border-ink/20 bg-paper p-4">
              <p
                className="font-medium"
                style={{ fontFamily: "var(--font-heading)" }}
              >
                {created === 0
                  ? "No new invoices created"
                  : `Created ${created} invoice${created === 1 ? "" : "s"}`}
              </p>
              <p className="text-sm text-ink/75">
                {allClasses ? "Every class" : "Selected class"} · term {termLabel}
                {skipped > 0
                  ? ` · ${skipped} student${skipped === 1 ? "" : "s"} already had an invoice and were skipped`
                  : null}
                .
              </p>
              <Link
                href="/bursar/invoices"
                className="nb-interactive inline-flex items-center justify-center gap-2 rounded-[var(--radius-nb)] border-2 border-ink bg-paper-card px-3 py-1.5 text-sm font-semibold text-ink shadow-nb hover:shadow-nb-lg"
                style={{ fontFamily: "var(--font-heading)" }}
              >
                View invoices
              </Link>
            </div>
          ) : null}
        </CardBody>
      </Card>
    </div>
  );
}
