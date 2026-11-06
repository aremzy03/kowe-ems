"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Button,
  Card,
  CardBody,
  EmptyState,
  PageHeader,
} from "@/components/ui";
import { Toast } from "@/components/ui/client";
import { academicsApi } from "@/lib/api/academics";
import { assessmentApi } from "@/lib/api/assessment";
import { useParentChildren } from "@/lib/parent/children";

export default function ParentResultsPage() {
  const { selected } = useParentChildren();
  const terms = useQuery({
    queryKey: ["academics", "terms"],
    queryFn: () => academicsApi.terms.list(),
  });
  const termId = terms.data?.[0]?.id;
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
      setError(err instanceof Error ? err.message : "PDF failed");
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

  return (
    <div className="mx-auto w-full max-w-5xl space-y-4">
      <PageHeader
        title="Results"
        description={`${selected.name} · term results`}
        actions={
          <Button size="sm" onClick={() => void downloadPdf()} disabled={!termId}>
            Download PDF
          </Button>
        }
      />
      {error ? <p className="text-sm text-danger">{error}</p> : null}
      <Card>
        <CardBody>
          {results.isLoading ? (
            <p className="text-sm text-ink/70">Loading…</p>
          ) : results.error ? (
            <p className="text-sm text-danger">
              {results.error instanceof Error
                ? results.error.message
                : "Failed"}
            </p>
          ) : (
            <pre
              className="overflow-auto text-xs"
              style={{ fontFamily: "var(--font-mono)" }}
            >
              {JSON.stringify(results.data ?? {}, null, 2)}
            </pre>
          )}
        </CardBody>
      </Card>
      <Toast
        open={toastOpen}
        onClose={() => setToastOpen(false)}
        message="Report PDF download started."
      />
    </div>
  );
}
