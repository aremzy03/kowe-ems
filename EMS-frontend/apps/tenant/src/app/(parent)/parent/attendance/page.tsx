"use client";

import { useQuery } from "@tanstack/react-query";
import { Card, CardBody, EmptyState, PageHeader } from "@/components/ui";
import { academicsApi } from "@/lib/api/academics";
import { attendanceApi } from "@/lib/api/attendance";
import { useParentChildren } from "@/lib/parent/children";

export default function ParentAttendancePage() {
  const { selected } = useParentChildren();
  const terms = useQuery({
    queryKey: ["academics", "terms"],
    queryFn: () => academicsApi.terms.list(),
  });
  const termId = terms.data?.[0]?.id;
  const summary = useQuery({
    queryKey: ["attendance", "summary", selected?.id, termId],
    queryFn: () => attendanceApi.studentSummary(selected!.id, termId!),
    enabled: Boolean(selected?.id && termId),
  });
  const daily = useQuery({
    queryKey: ["attendance", "parent-daily", selected?.id, termId],
    queryFn: () => attendanceApi.parentDaily(selected!.id, termId!),
    enabled: Boolean(selected?.id && termId),
  });

  if (!selected) {
    return (
      <EmptyState
        headline="Select a child"
        body="Link a student, then view attendance here."
      />
    );
  }

  return (
    <div className="mx-auto w-full max-w-5xl space-y-4">
      <PageHeader
        title="Attendance"
        description={`${selected.name} · term summary and daily log`}
      />
      <Card>
        <CardBody>
          <p className="mb-2 text-sm font-medium text-ink/70">Summary</p>
          {summary.isLoading ? (
            <p className="text-sm text-ink/60">Loading…</p>
          ) : (
            <pre
              className="overflow-auto text-xs"
              style={{ fontFamily: "var(--font-mono)" }}
            >
              {JSON.stringify(summary.data ?? {}, null, 2)}
            </pre>
          )}
        </CardBody>
      </Card>
      <Card>
        <CardBody>
          <p className="mb-2 text-sm font-medium text-ink/70">Daily</p>
          {daily.isLoading ? (
            <p className="text-sm text-ink/60">Loading…</p>
          ) : (
            <pre
              className="overflow-auto text-xs"
              style={{ fontFamily: "var(--font-mono)" }}
            >
              {JSON.stringify(daily.data ?? {}, null, 2)}
            </pre>
          )}
        </CardBody>
      </Card>
    </div>
  );
}
