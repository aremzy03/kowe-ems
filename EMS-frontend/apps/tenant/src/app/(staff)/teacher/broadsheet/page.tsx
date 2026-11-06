"use client";

import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import {
  Button,
  Card,
  CardBody,
  EmptyState,
  Label,
  PageHeader,
  Table,
  TBody,
  TD,
  TH,
  THead,
  TR,
} from "@/components/ui";
import {
  EntitySearchField,
  type EntitySearchOption,
} from "@/components/ui/client";
import { academicsApi, type Session, type Term } from "@/lib/api/academics";
import { assessmentApi } from "@/lib/api/assessment";
import { ApiRequestError } from "@/lib/api/client";
import { mapDrfErrors } from "@/lib/api/errors";

type BroadsheetColumn = {
  key: string;
  kind?: string;
  label?: string;
  subject_name?: string;
};

type BroadsheetRow = {
  student?: string;
  student_name?: string;
  admission_number?: string;
  class_position?: number | null;
  rank?: number | null;
  cells?: Record<string, string | number | null | undefined>;
};

type BroadsheetPayload = {
  class_level_name?: string;
  arm_name?: string;
  term_name?: string;
  columns?: BroadsheetColumn[];
  rows?: BroadsheetRow[];
  student_count?: number;
};

function cellValue(value: string | number | null | undefined): string {
  if (value == null || value === "") return "—";
  return String(value);
}

function termOptionLabel(term: Term, sessions: Session[]) {
  const session =
    term.session_name ||
    sessions.find((s) => s.id === term.session)?.name;
  return session ? `${session} · ${term.name}` : term.name;
}

export default function TeacherBroadsheetPage() {
  const assignments = useQuery({
    queryKey: ["academics", "my-assignments"],
    queryFn: () => academicsApi.myAssignments(),
  });
  const classes = useQuery({
    queryKey: ["academics", "my-classes"],
    queryFn: () => academicsApi.myClasses(),
  });
  const sessions = useQuery({
    queryKey: ["academics", "sessions"],
    queryFn: () => academicsApi.sessions.list(),
  });
  const terms = useQuery({
    queryKey: ["academics", "terms"],
    queryFn: () => academicsApi.terms.list(),
  });
  const classLevels = useQuery({
    queryKey: ["academics", "class-levels"],
    queryFn: () => academicsApi.classLevels.list(),
  });
  const arms = useQuery({
    queryKey: ["academics", "arms"],
    queryFn: () => academicsApi.arms.list(),
  });
  const subjects = useQuery({
    queryKey: ["academics", "subjects"],
    queryFn: () => academicsApi.subjects.list(),
  });

  const first = assignments.data?.[0] ?? classes.data?.[0];
  const [classLevel, setClassLevel] = useState("");
  const [arm, setArm] = useState("");
  const [term, setTerm] = useState("");
  const [subject, setSubject] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [seeded, setSeeded] = useState(false);

  useEffect(() => {
    if (seeded || !first) return;
    setClassLevel(first.class_level);
    setArm(first.arm);
    setTerm(first.term);
    if ("subject" in first && first.subject) setSubject(first.subject);
    setSeeded(true);
  }, [first, seeded]);

  const classOptions: EntitySearchOption[] = useMemo(() => {
    const fromCatalog = (classLevels.data ?? []).map((level) => ({
      id: level.id,
      label: level.name,
    }));
    if (fromCatalog.length) return fromCatalog;
    const seen = new Map<string, string>();
    for (const row of [...(assignments.data ?? []), ...(classes.data ?? [])]) {
      if (!seen.has(row.class_level)) {
        seen.set(
          row.class_level,
          row.class_level_name ?? row.class_level,
        );
      }
    }
    return [...seen.entries()].map(([id, label]) => ({ id, label }));
  }, [classLevels.data, assignments.data, classes.data]);

  const armOptions: EntitySearchOption[] = useMemo(() => {
    const catalog = (arms.data ?? []).filter(
      (a) => !classLevel || a.class_level === classLevel,
    );
    if (catalog.length) {
      return catalog.map((a) => ({ id: a.id, label: a.name }));
    }
    const seen = new Map<string, string>();
    for (const row of [...(assignments.data ?? []), ...(classes.data ?? [])]) {
      if (classLevel && row.class_level !== classLevel) continue;
      if (!seen.has(row.arm)) {
        seen.set(row.arm, row.arm_name ?? row.arm);
      }
    }
    return [...seen.entries()].map(([id, label]) => ({ id, label }));
  }, [arms.data, classLevel, assignments.data, classes.data]);

  const termOptions: EntitySearchOption[] = useMemo(() => {
    if (terms.data?.length) {
      return terms.data.map((t) => ({
        id: t.id,
        label: termOptionLabel(t, sessions.data ?? []),
        keywords: t.name,
      }));
    }
    const seen = new Map<string, string>();
    for (const row of [...(assignments.data ?? []), ...(classes.data ?? [])]) {
      if (!seen.has(row.term)) {
        seen.set(row.term, row.term_name ?? row.term);
      }
    }
    return [...seen.entries()].map(([id, label]) => ({ id, label }));
  }, [terms.data, sessions.data, assignments.data, classes.data]);

  const subjectOptions: EntitySearchOption[] = useMemo(() => {
    if (subjects.data?.length) {
      return subjects.data.map((s) => ({
        id: s.id,
        label: s.code ? `${s.name} (${s.code})` : s.name,
        keywords: s.code,
      }));
    }
    const seen = new Map<string, string>();
    for (const row of assignments.data ?? []) {
      if (!seen.has(row.subject)) {
        seen.set(
          row.subject,
          row.subject_name ?? row.subject_code ?? row.subject,
        );
      }
    }
    return [...seen.entries()].map(([id, label]) => ({ id, label }));
  }, [subjects.data, assignments.data]);

  const effective = {
    class_level: classLevel,
    arm,
    term,
    subject: subject || undefined,
  };

  const sheet = useQuery({
    queryKey: ["assessment", "broadsheet", effective],
    queryFn: () =>
      assessmentApi.broadsheet({
        class_level: effective.class_level,
        arm: effective.arm,
        term: effective.term,
        subject: effective.subject,
      }),
    enabled: Boolean(effective.class_level && effective.arm && effective.term),
  });

  const recompute = useMutation({
    mutationFn: () =>
      assessmentApi.recompute({
        class_level: effective.class_level,
        arm: effective.arm,
        term: effective.term,
        subject: effective.subject,
      }),
    onSuccess: () => {
      setError(null);
      void sheet.refetch();
    },
    onError: (err) => {
      setError(
        err instanceof ApiRequestError
          ? mapDrfErrors(err.data).form ?? err.message
          : "Recompute failed",
      );
    },
  });

  const payload = sheet.data as BroadsheetPayload | undefined;
  const columns = payload?.columns ?? [];
  const rows = payload?.rows ?? [];
  const hasRank = rows.some(
    (row) => row.class_position != null || row.rank != null,
  );

  return (
    <div className="space-y-6">
      <PageHeader title="Broadsheet" description="Class results grid" />
      <Card>
        <CardBody className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <div>
            <Label htmlFor="bs-class">Class level</Label>
            <EntitySearchField
              id="bs-class"
              value={classLevel}
              onChange={(id) => {
                setClassLevel(id);
                setArm("");
              }}
              options={classOptions}
              loading={classLevels.isLoading || assignments.isLoading}
              placeholder="Search class…"
            />
          </div>
          <div>
            <Label htmlFor="bs-arm">Arm</Label>
            <EntitySearchField
              id="bs-arm"
              value={arm}
              onChange={setArm}
              options={armOptions}
              loading={arms.isLoading}
              disabled={!classLevel}
              placeholder={classLevel ? "Search arm…" : "Choose class first"}
            />
          </div>
          <div>
            <Label htmlFor="bs-term">Term</Label>
            <EntitySearchField
              id="bs-term"
              value={term}
              onChange={setTerm}
              options={termOptions}
              loading={terms.isLoading || sessions.isLoading}
              placeholder="Search term…"
            />
          </div>
          <div>
            <Label htmlFor="bs-subject">Subject (optional)</Label>
            <EntitySearchField
              id="bs-subject"
              value={subject}
              onChange={setSubject}
              options={subjectOptions}
              loading={subjects.isLoading || assignments.isLoading}
              placeholder="Search subject…"
            />
          </div>
        </CardBody>
      </Card>
      <div className="flex gap-2">
        <Button
          size="sm"
          disabled={
            recompute.isPending || !classLevel || !arm || !term
          }
          onClick={() => recompute.mutate()}
        >
          {recompute.isPending ? "Recomputing…" : "Recompute"}
        </Button>
      </div>
      {error ? <p className="text-sm text-danger">{error}</p> : null}

      {sheet.isLoading ? (
        <p className="text-sm text-ink/70">Loading broadsheet…</p>
      ) : sheet.error ? (
        <p className="text-sm text-danger">
          {sheet.error instanceof Error
            ? sheet.error.message
            : "Failed to load broadsheet"}
        </p>
      ) : !payload ? (
        <EmptyState
          headline="No broadsheet data"
          body="Select a class, arm, and term to load the grid."
        />
      ) : rows.length === 0 ? (
        <EmptyState
          headline="No students"
          body="No active enrollments for this class/arm/term."
        />
      ) : (
        <Card>
          <CardBody className="space-y-3 p-0 pt-3">
            {payload.class_level_name || payload.term_name ? (
              <p className="px-4 text-sm text-ink/65">
                {[
                  [payload.class_level_name, payload.arm_name]
                    .filter(Boolean)
                    .join(" "),
                  payload.term_name,
                  payload.student_count != null
                    ? `${payload.student_count} students`
                    : null,
                ]
                  .filter(Boolean)
                  .join(" · ")}
              </p>
            ) : null}
            <div className="overflow-x-auto">
              <Table className="border-0 shadow-none">
                <THead>
                  <TR>
                    <TH>Student</TH>
                    <TH>Admission</TH>
                    {hasRank ? <TH>Rank</TH> : null}
                    {columns.map((col) => (
                      <TH key={col.key} title={col.subject_name}>
                        {col.label ?? col.key}
                      </TH>
                    ))}
                  </TR>
                </THead>
                <TBody>
                  {rows.map((row) => (
                    <TR key={row.student ?? row.admission_number}>
                      <TD className="whitespace-nowrap font-medium">
                        {row.student_name ?? "—"}
                      </TD>
                      <TD
                        className="whitespace-nowrap"
                        style={{ fontFamily: "var(--font-mono)" }}
                      >
                        {row.admission_number ?? "—"}
                      </TD>
                      {hasRank ? (
                        <TD style={{ fontFamily: "var(--font-mono)" }}>
                          {cellValue(row.class_position ?? row.rank)}
                        </TD>
                      ) : null}
                      {columns.map((col) => (
                        <TD
                          key={col.key}
                          className="whitespace-nowrap text-right"
                          style={{ fontFamily: "var(--font-mono)" }}
                        >
                          {cellValue(row.cells?.[col.key])}
                        </TD>
                      ))}
                    </TR>
                  ))}
                </TBody>
              </Table>
            </div>
          </CardBody>
        </Card>
      )}
    </div>
  );
}
