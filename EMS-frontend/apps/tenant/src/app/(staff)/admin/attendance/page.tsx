"use client";

import { useQuery } from "@tanstack/react-query";
import {
  AttendanceOverview,
  type AttendanceOverviewData,
} from "@/components/attendance/AttendanceOverview";
import { EmptyState, PageHeader } from "@/components/ui";
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
    queryFn: () =>
      attendanceApi.adminOverview({
        term: termId!,
      }) as Promise<AttendanceOverviewData>,
    enabled: Boolean(termId),
  });

  return (
    <div className="space-y-6">
      <PageHeader
        title="Attendance overview"
        description="School-wide attendance summary for the current term"
      />

      {!termId && !terms.isLoading ? (
        <EmptyState
          headline="No terms yet"
          body="Create an academic term before viewing attendance overview."
        />
      ) : (
        <AttendanceOverview
          data={overview.data}
          isLoading={terms.isLoading || overview.isLoading}
          error={overview.error}
        />
      )}
    </div>
  );
}
