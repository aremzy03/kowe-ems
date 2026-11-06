"use client";

import { useQuery } from "@tanstack/react-query";
import {
  Card,
  CardBody,
  EmptyState,
  PageHeader,
} from "@/components/ui";
import { attendanceApi } from "@/lib/api/attendance";
import { academicsApi } from "@/lib/api/academics";

export default function AdminAttendancePage() {
  const terms = useQuery({
    queryKey: ["academics", "terms"],
    queryFn: () => academicsApi.terms.list(),
  });
  const termId = terms.data?.[0]?.id;
  const overview = useQuery({
    queryKey: ["attendance", "admin-overview", termId],
    queryFn: () => attendanceApi.adminOverview({ term: termId! }),
    enabled: Boolean(termId),
  });

  return (
    <div className="space-y-6">
      <PageHeader
        title="Attendance overview"
        description="School-wide attendance summary for the current term"
      />

      {terms.isLoading || overview.isLoading ? (
        <p className="text-sm text-ink/70">Loading…</p>
      ) : null}
      {overview.error ? (
        <p className="text-sm text-danger">
          {overview.error instanceof Error
            ? overview.error.message
            : "Failed to load"}
        </p>
      ) : null}

      {!termId && !terms.isLoading ? (
        <EmptyState
          headline="No terms yet"
          body="Create an academic term before viewing attendance overview."
        />
      ) : null}

      {overview.data ? (
        <Card>
          <CardBody>
            <pre
              className="overflow-auto text-xs"
              style={{ fontFamily: "var(--font-mono)" }}
            >
              {JSON.stringify(overview.data, null, 2)}
            </pre>
          </CardBody>
        </Card>
      ) : null}
    </div>
  );
}
