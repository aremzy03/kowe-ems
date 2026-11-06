"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Button,
  Card,
  CardBody,
  EmptyState,
  Input,
  Label,
  PageHeader,
  Select,
  Table,
  TBody,
  TD,
  TH,
  THead,
  TR,
} from "@/components/ui";
import { Toast } from "@/components/ui/client";
import {
  academicsApi,
  type ClassSubjectAssignment,
} from "@/lib/api/academics";
import { assessmentApi, type AssessmentComponent } from "@/lib/api/assessment";
import { formatApiError, partialBulkFailureMessage } from "@/lib/api/errors";

type SchemeComponent = AssessmentComponent & {
  weight_percentage?: string | number;
};

type BroadsheetRow = {
  student: string;
  student_name: string;
  admission_number?: string;
  cells?: Record<string, string | number | null>;
};

type BroadsheetPayload = {
  rows?: BroadsheetRow[];
};

const SCORE_PATTERN = /^\d+(\.\d{1,2})?$/;

function assignmentLabel(assignment: ClassSubjectAssignment): string {
  const subject = assignment.subject_name || assignment.subject;
  const level = assignment.class_level_name || assignment.class_level;
  const arm = assignment.arm_name || "";
  const term = assignment.term_name || assignment.term;
  return [subject, [level, arm].filter(Boolean).join(" "), term].join(" · ");
}

function componentMeta(component: SchemeComponent): string {
  const weight = component.weight_percentage ?? component.weight;
  const parts: string[] = [];
  if (weight != null && String(weight) !== "") parts.push(`${weight}%`);
  if (component.max_score != null && String(component.max_score) !== "") {
    parts.push(`max ${component.max_score}`);
  }
  return parts.join(" · ");
}

function cellKey(studentId: string, componentId: string): string {
  return `${studentId}:${componentId}`;
}

function MarksGrid({ assignment }: { assignment: ClassSubjectAssignment }) {
  const qc = useQueryClient();
  const components = useQuery({
    queryKey: [
      "assessment",
      "my-components",
      assignment.subject,
      assignment.class_level,
      assignment.term,
    ],
    queryFn: () =>
      assessmentApi.myComponents({
        subject: assignment.subject,
        class_level: assignment.class_level,
        term: assignment.term,
      }),
  });
  // Enrollment list is admin-only. Broadsheet rows are the enrolled students
  // for this class, arm, term, and subject.
  const sheet = useQuery({
    queryKey: [
      "assessment",
      "broadsheet",
      assignment.class_level,
      assignment.arm,
      assignment.term,
      assignment.subject,
    ],
    queryFn: async () => {
      const data = await assessmentApi.broadsheet({
        class_level: assignment.class_level,
        arm: assignment.arm,
        term: assignment.term,
        subject: assignment.subject,
      });
      return data as BroadsheetPayload;
    },
  });

  const scheme = (components.data ?? []) as SchemeComponent[];
  const rows = sheet.data?.rows ?? [];
  const [scores, setScores] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [toastOpen, setToastOpen] = useState(false);
  const seeded = useRef(false);

  useEffect(() => {
    if (seeded.current || !sheet.isSuccess || !components.isSuccess) return;
    const next: Record<string, string> = {};
    for (const row of sheet.data?.rows ?? []) {
      for (const component of components.data ?? []) {
        const raw = row.cells?.[`comp_${component.id}`];
        if (raw != null && String(raw).trim() !== "") {
          next[cellKey(row.student, component.id)] = String(raw);
        }
      }
    }
    setScores(next);
    seeded.current = true;
  }, [sheet.isSuccess, sheet.data, components.isSuccess, components.data]);

  const filledCount = useMemo(() => {
    let count = 0;
    for (const row of rows) {
      for (const component of scheme) {
        if ((scores[cellKey(row.student, component.id)] ?? "").trim()) count += 1;
      }
    }
    return count;
  }, [rows, scheme, scores]);

  const save = useMutation({
    mutationFn: (entries: {
      student_id: string;
      assessment_component_id: string;
      score: string;
    }[]) => assessmentApi.bulkUpsertScores({ entries }),
    onSuccess: (data) => {
      void qc.invalidateQueries({ queryKey: ["assessment", "broadsheet"] });
      const partial = partialBulkFailureMessage(data);
      if (partial) {
        setError(partial);
        return;
      }
      setError(null);
      setToastOpen(true);
    },
    onError: (err) => {
      setError(formatApiError(err, "Save failed"));
    },
  });

  function submit() {
    const entries: {
      student_id: string;
      assessment_component_id: string;
      score: string;
    }[] = [];
    for (const row of rows) {
      for (const component of scheme) {
        const raw = (scores[cellKey(row.student, component.id)] ?? "").trim();
        if (!raw) continue;
        if (!SCORE_PATTERN.test(raw)) {
          setError(
            `Enter a score with up to 2 decimal places for ${row.student_name}.`,
          );
          return;
        }
        entries.push({
          student_id: row.student,
          assessment_component_id: component.id,
          score: raw,
        });
      }
    }
    if (!entries.length) {
      setError("Enter at least one score.");
      return;
    }
    setError(null);
    save.mutate(entries);
  }

  const loading = components.isLoading || sheet.isLoading;
  const loadError = components.error ?? sheet.error;
  const ready = !loading && !loadError && scheme.length > 0 && rows.length > 0;

  return (
    <>
      <Card>
        <form
          onSubmit={(event) => {
            event.preventDefault();
            if (save.isPending || !ready) return;
            submit();
          }}
        >
          {loading ? (
            <CardBody>
              <p className="text-sm text-ink/70">Loading class list…</p>
            </CardBody>
          ) : loadError ? (
            <CardBody>
              <p className="text-sm text-danger" role="alert">
                {formatApiError(loadError, "Could not load this class.")}
              </p>
            </CardBody>
          ) : scheme.length === 0 ? (
            <CardBody>
              <p className="text-sm text-ink/80">
                This subject has no assessment components yet. Set the scheme
                before entering marks.
              </p>
            </CardBody>
          ) : rows.length === 0 ? (
            <CardBody>
              <p className="text-sm text-ink/80">
                No students are enrolled in this class for the term.
              </p>
            </CardBody>
          ) : (
            <CardBody className="p-0">
              <Table>
                <THead>
                  <TR>
                    <TH>Student</TH>
                    {scheme.map((component) => (
                      <TH key={component.id}>
                        <span className="block">{component.name}</span>
                        {componentMeta(component) ? (
                          <span className="mt-0.5 block text-xs font-normal text-ink/60">
                            {componentMeta(component)}
                          </span>
                        ) : null}
                      </TH>
                    ))}
                  </TR>
                </THead>
                <TBody>
                  {rows.map((row) => (
                    <TR key={row.student}>
                      <TD className="min-w-40">
                        <span className="block">{row.student_name}</span>
                        {row.admission_number ? (
                          <span
                            className="block text-xs text-ink/60"
                            style={{ fontFamily: "var(--font-mono)" }}
                          >
                            {row.admission_number}
                          </span>
                        ) : null}
                      </TD>
                      {scheme.map((component) => {
                        const key = cellKey(row.student, component.id);
                        return (
                          <TD key={component.id} className="min-w-28">
                            <Input
                              aria-label={`${row.student_name} ${component.name}`}
                              inputMode="decimal"
                              value={scores[key] ?? ""}
                              onChange={(event) =>
                                setScores((current) => ({
                                  ...current,
                                  [key]: event.target.value,
                                }))
                              }
                              className="py-1.5 text-sm"
                              style={{ fontFamily: "var(--font-mono)" }}
                            />
                          </TD>
                        );
                      })}
                    </TR>
                  ))}
                </TBody>
              </Table>
            </CardBody>
          )}
          <div className="flex flex-wrap items-center gap-3 border-t border-ink/15 px-5 py-4">
            <Button type="submit" disabled={save.isPending || !ready || filledCount === 0}>
              {save.isPending ? "Saving…" : "Submit scores"}
            </Button>
            <p className="text-sm text-ink/70">
              {filledCount} {filledCount === 1 ? "score" : "scores"} ready.
              Blank cells are left unchanged.
            </p>
          </div>
          {error ? (
            <p className="px-5 pb-4 text-sm text-danger" role="alert">
              {error}
            </p>
          ) : null}
        </form>
      </Card>
      <Toast
        open={toastOpen}
        onClose={() => setToastOpen(false)}
        message="Scores saved."
      />
    </>
  );
}

export default function TeacherMarksPage() {
  const assignments = useQuery({
    queryKey: ["academics", "my-assignments"],
    queryFn: () => academicsApi.myAssignments(),
  });
  const list = assignments.data ?? [];
  const [assignmentId, setAssignmentId] = useState("");
  const selected =
    list.find((assignment) => assignment.id === assignmentId) ?? list[0];

  return (
    <div className="space-y-6">
      <PageHeader
        title="Mark entry"
        description="Enter scores for a class you teach. One save sends the whole grid."
      />
      {assignments.isLoading ? (
        <p className="text-sm text-ink/70">Loading your assignments…</p>
      ) : null}
      {assignments.isError ? (
        <p className="text-sm text-danger" role="alert">
          {formatApiError(assignments.error, "Could not load assignments.")}
        </p>
      ) : null}
      {!assignments.isLoading && !assignments.isError && list.length === 0 ? (
        <EmptyState
          headline="No classes assigned"
          body="When an admin assigns you a subject, class, and term, mark entry shows up here."
        />
      ) : null}
      {selected ? (
        <>
          <Card>
            <CardBody>
              <Label htmlFor="marks-assignment">Assignment</Label>
              <Select
                id="marks-assignment"
                value={selected.id}
                onChange={(event) => setAssignmentId(event.target.value)}
              >
                {list.map((assignment) => (
                  <option key={assignment.id} value={assignment.id}>
                    {assignmentLabel(assignment)}
                  </option>
                ))}
              </Select>
            </CardBody>
          </Card>
          <MarksGrid key={selected.id} assignment={selected} />
        </>
      ) : null}
    </div>
  );
}
