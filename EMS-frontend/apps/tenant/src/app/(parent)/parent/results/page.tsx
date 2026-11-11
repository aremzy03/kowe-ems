"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Button,
  Card,
  CardBody,
  EmptyState,
  PageHeader,
  Table,
  TBody,
  TD,
  TH,
  THead,
  TR,
} from "@/components/ui";
import { Toast } from "@/components/ui/client";
import { academicsApi, currentTerm } from "@/lib/api/academics";
import { assessmentApi } from "@/lib/api/assessment";
import { ApiRequestError } from "@/lib/api/client";
import { useParentChildren } from "@/lib/parent/children";

type SubjectResult = {
  id?: string;
  subject_name?: string;
  subject_code?: string;
  computed_score?: string | number;
};

type ResultsSummary = {
  overall_average?: string | number;
  class_position?: number | null;
  teacher_remark?: string | null;
  admin_remark?: string | null;
  is_published?: boolean;
};

type StudentResultsPayload = {
  student_name?: string;
  term_name?: string;
  summary?: ResultsSummary | null;
  subject_results?: SubjectResult[];
  is_published?: boolean;
  detail?: string;
};

function mono(value: string | number | null | undefined): string {
  if (value == null || value === "") return "—";
  return String(value);
}

export default function ParentResultsPage() {
  const { selected } = useParentChildren();
  const terms = useQuery({
    queryKey: ["academics", "terms"],
    queryFn: () => academicsApi.terms.list(),
  });
  const termId = currentTerm(terms.data)?.id;
  const results = useQuery({
    queryKey: ["assessment", "student-results", selected?.id, termId],
    queryFn: () => assessmentApi.studentResults(selected!.id, termId!),
    enabled: Boolean(selected?.id && termId),
  });
  const [toastOpen, setToastOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function downloadPdf() {
    if (!selected || !termId) return;
    try {
      const blob = await assessmentApi.reportCardPdf(selected.id, termId);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `report-card-${selected.id}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
      setToastOpen(true);
      setError(null);
    } catch (err) {
      if (err instanceof ApiRequestError && (err.status === 404 || err.status === 403)) {
        setError(
          err.detail ||
            "Results are not published for this term yet. The report card is unavailable.",
        );
        return;
      }
      const message =
        err instanceof Error ? err.message : "PDF download failed";
      if (/404|not published|unpublished/i.test(message)) {
        setError(
          "Results are not published for this term yet. The report card is unavailable.",
        );
        return;
      }
      setError(message);
    }
  }

  if (!selected) {
    return (
      <EmptyState
        headline="Select a child"
        body="Link a student to view results."
      />
    );
  }

  if (terms.isSuccess && !termId) {
    const hasTerms = (terms.data?.length ?? 0) > 0;
    return (
      <div className="mx-auto w-full max-w-5xl space-y-4">
        <PageHeader
          title="Results"
          description={`${selected.name} · term results`}
        />
        <EmptyState
          headline={hasTerms ? "No current term" : "No terms yet"}
          body={
            hasTerms
              ? "Results follow the term the school marks as current."
              : "The school has not added a term yet."
          }
        />
      </div>
    );
  }

  const payload = results.data as StudentResultsPayload | undefined;
  const unpublished =
    payload?.is_published === false ||
    (payload != null &&
      !payload.summary &&
      (payload.subject_results?.length ?? 0) === 0);
  const subjects = payload?.subject_results ?? [];
  const summary = payload?.summary;

  return (
    <div className="mx-auto w-full max-w-5xl space-y-4">
      <PageHeader
        title="Results"
        description={`${selected.name} · term results`}
        actions={
          <Button
            size="sm"
            onClick={() => void downloadPdf()}
            disabled={!termId || unpublished}
          >
            Download PDF
          </Button>
        }
      />
      {error ? <p className="text-sm text-danger">{error}</p> : null}

      {results.isLoading || terms.isLoading ? (
        <p className="text-sm text-ink/70">Loading…</p>
      ) : null}

      {results.error ? (
        <p className="text-sm text-danger">
          {results.error instanceof Error
            ? results.error.message
            : "Failed to load results"}
        </p>
      ) : null}

      {!results.isLoading && !results.error && unpublished ? (
        <EmptyState
          headline="Results not published"
          body={
            payload?.detail ||
            "Results are not published for this term yet. Check back after the school publishes report cards."
          }
        />
      ) : null}

      {!results.isLoading && !results.error && !unpublished && payload ? (
        <>
          {summary ? (
            <div className="grid gap-3 sm:grid-cols-3">
              <Card>
                <CardBody className="space-y-1 py-4">
                  <p className="text-sm font-medium text-ink/65">Average</p>
                  <p
                    className="text-2xl font-bold"
                    style={{ fontFamily: "var(--font-mono)" }}
                  >
                    {mono(summary.overall_average)}
                  </p>
                </CardBody>
              </Card>
              <Card>
                <CardBody className="space-y-1 py-4">
                  <p className="text-sm font-medium text-ink/65">Position</p>
                  <p
                    className="text-2xl font-bold"
                    style={{ fontFamily: "var(--font-mono)" }}
                  >
                    {mono(summary.class_position)}
                  </p>
                </CardBody>
              </Card>
              <Card>
                <CardBody className="space-y-1 py-4">
                  <p className="text-sm font-medium text-ink/65">Term</p>
                  <p
                    className="text-lg font-bold"
                    style={{ fontFamily: "var(--font-heading)" }}
                  >
                    {payload.term_name || "—"}
                  </p>
                </CardBody>
              </Card>
            </div>
          ) : null}

          <Card>
            <CardBody className="p-0">
              <Table className="border-0 shadow-none">
                <THead>
                  <TR>
                    <TH>Subject</TH>
                    <TH>Code</TH>
                    <TH>Score</TH>
                  </TR>
                </THead>
                <TBody>
                  {subjects.length === 0 ? (
                    <TR>
                      <TD colSpan={3} className="text-sm text-ink/65">
                        No subject scores for this term.
                      </TD>
                    </TR>
                  ) : (
                    subjects.map((row, i) => (
                      <TR key={row.id ?? row.subject_code ?? i}>
                        <TD className="font-medium">
                          {row.subject_name ?? "—"}
                        </TD>
                        <TD style={{ fontFamily: "var(--font-mono)" }}>
                          {row.subject_code ?? "—"}
                        </TD>
                        <TD style={{ fontFamily: "var(--font-mono)" }}>
                          {mono(row.computed_score)}
                        </TD>
                      </TR>
                    ))
                  )}
                </TBody>
              </Table>
            </CardBody>
          </Card>

          {summary?.teacher_remark || summary?.admin_remark ? (
            <Card>
              <CardBody className="space-y-2">
                {summary.teacher_remark ? (
                  <p className="text-sm">
                    <span className="font-medium">Teacher: </span>
                    {summary.teacher_remark}
                  </p>
                ) : null}
                {summary.admin_remark ? (
                  <p className="text-sm">
                    <span className="font-medium">Admin: </span>
                    {summary.admin_remark}
                  </p>
                ) : null}
              </CardBody>
            </Card>
          ) : null}
        </>
      ) : null}

      <Toast
        open={toastOpen}
        onClose={() => setToastOpen(false)}
        message="Report PDF download started."
      />
    </div>
  );
}
