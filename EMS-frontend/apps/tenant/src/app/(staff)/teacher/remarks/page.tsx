"use client";

import { useMemo, useState } from "react";
import { useMutation, useQueries, useQuery } from "@tanstack/react-query";
import {
  Button,
  Card,
  CardBody,
  Label,
  PageHeader,
  Textarea,
} from "@/components/ui";
import {
  EntitySearchField,
  Toast,
  type EntitySearchOption,
} from "@/components/ui/client";
import { academicsApi, type Session, type Term } from "@/lib/api/academics";
import { assessmentApi } from "@/lib/api/assessment";
import { ApiRequestError } from "@/lib/api/client";
import { mapDrfErrors } from "@/lib/api/errors";

type BroadsheetRow = {
  student?: string;
  student_name?: string;
  admission_number?: string;
};

type BroadsheetPayload = {
  rows?: BroadsheetRow[];
};

function termOptionLabel(term: Term, sessions: Session[]) {
  const session =
    term.session_name ||
    sessions.find((s) => s.id === term.session)?.name;
  return session ? `${session} · ${term.name}` : term.name;
}

export default function TeacherRemarksPage() {
  const [student, setStudent] = useState("");
  const [term, setTerm] = useState("");
  const [remark, setRemark] = useState("");
  const [toastOpen, setToastOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const sessions = useQuery({
    queryKey: ["academics", "sessions"],
    queryFn: () => academicsApi.sessions.list(),
  });
  const terms = useQuery({
    queryKey: ["academics", "terms"],
    queryFn: () => academicsApi.terms.list(),
  });
  const myClasses = useQuery({
    queryKey: ["academics", "my-classes"],
    queryFn: () => academicsApi.myClasses(),
  });
  const myAssignments = useQuery({
    queryKey: ["academics", "my-assignments"],
    queryFn: () => academicsApi.myAssignments(),
  });

  const scopes = useMemo(() => {
    const map = new Map<
      string,
      { class_level: string; arm: string; term: string }
    >();
    for (const row of [...(myClasses.data ?? []), ...(myAssignments.data ?? [])]) {
      const key = `${row.class_level}:${row.arm}:${row.term}`;
      if (!map.has(key)) {
        map.set(key, {
          class_level: row.class_level,
          arm: row.arm,
          term: row.term,
        });
      }
    }
    return [...map.values()].filter((s) => !term || s.term === term);
  }, [myClasses.data, myAssignments.data, term]);

  const broadsheetQueries = useQueries({
    queries: scopes.map((scope) => ({
      queryKey: [
        "assessment",
        "broadsheet-students",
        scope.class_level,
        scope.arm,
        scope.term,
      ],
      queryFn: () =>
        assessmentApi.broadsheet({
          class_level: scope.class_level,
          arm: scope.arm,
          term: scope.term,
        }) as Promise<BroadsheetPayload>,
      enabled: Boolean(term) && scopes.length > 0,
    })),
  });

  const termOptions: EntitySearchOption[] = useMemo(
    () =>
      (terms.data ?? []).map((t) => ({
        id: t.id,
        label: termOptionLabel(t, sessions.data ?? []),
        keywords: t.name,
      })),
    [terms.data, sessions.data],
  );

  const studentOptions: EntitySearchOption[] = useMemo(() => {
    const seen = new Map<string, EntitySearchOption>();
    for (const q of broadsheetQueries) {
      const rows = (q.data as BroadsheetPayload | undefined)?.rows ?? [];
      for (const row of rows) {
        if (!row.student || seen.has(row.student)) continue;
        const name = row.student_name ?? "Student";
        seen.set(row.student, {
          id: row.student,
          label: row.admission_number
            ? `${name} · ${row.admission_number}`
            : name,
          keywords: row.admission_number,
        });
      }
    }
    return [...seen.values()].sort((a, b) => a.label.localeCompare(b.label));
  }, [broadsheetQueries]);

  const studentsLoading =
    Boolean(term) &&
    (myClasses.isLoading ||
      myAssignments.isLoading ||
      broadsheetQueries.some((q) => q.isLoading));

  const save = useMutation({
    mutationFn: () =>
      assessmentApi.remarks({
        student,
        term,
        teacher_remark: remark,
      }),
    onSuccess: () => {
      setToastOpen(true);
      setError(null);
    },
    onError: (err) => {
      setError(
        err instanceof ApiRequestError
          ? mapDrfErrors(err.data).form ?? err.message
          : "Failed",
      );
    },
  });

  return (
    <div className="mx-auto max-w-lg space-y-6">
      <PageHeader
        title="Remarks"
        description="Short term remarks for report cards"
      />
      <Card>
        <CardBody className="space-y-3">
          <div>
            <Label htmlFor="remark-term">Term</Label>
            <EntitySearchField
              id="remark-term"
              value={term}
              onChange={(id) => {
                setTerm(id);
                setStudent("");
              }}
              options={termOptions}
              loading={terms.isLoading || sessions.isLoading}
              placeholder="Search session · term…"
            />
          </div>
          <div>
            <Label htmlFor="remark-student">Student</Label>
            <EntitySearchField
              id="remark-student"
              value={student}
              onChange={setStudent}
              options={studentOptions}
              loading={studentsLoading}
              disabled={!term}
              placeholder={
                term
                  ? "Search student name or admission no…"
                  : "Choose a term first"
              }
              emptyMessage={
                term
                  ? "No students in your assigned classes for this term"
                  : "Choose a term first"
              }
            />
          </div>
          <div>
            <Label htmlFor="remark-text">Remark</Label>
            <Textarea
              id="remark-text"
              value={remark}
              onChange={(e) => setRemark(e.target.value)}
              placeholder="Write a short teacher remark…"
            />
          </div>
          {error ? <p className="text-sm text-danger">{error}</p> : null}
          <Button
            disabled={save.isPending || !student || !term || !remark.trim()}
            onClick={() => save.mutate()}
          >
            {save.isPending ? "Saving…" : "Save remark"}
          </Button>
        </CardBody>
      </Card>
      <Toast
        open={toastOpen}
        onClose={() => setToastOpen(false)}
        message="Remark saved."
      />
    </div>
  );
}
