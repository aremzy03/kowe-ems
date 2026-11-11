"use client";

import { useQuery } from "@tanstack/react-query";
import {
  AttendanceOverview,
  attendancePencilNote,
  type AttendanceOverviewData,
} from "@/components/attendance/AttendanceOverview";
import { EmptyState, PageHeader, PencilAside } from "@/components/ui";
import { attendanceApi } from "@/lib/api/attendance";
import { academicsApi, currentTerm } from "@/lib/api/academics";

export default function AdminAttendancePage() {
  const terms = useQuery({
    queryKey: ["academics", "terms"],
    queryFn: () => academicsApi.terms.list(),
  });
  const termId = currentTerm(terms.data)?.id;
  const hasTerms = (terms.data?.length ?? 0) > 0;
  const overview = useQuery({
    queryKey: ["attendance", "admin-overview", termId],
    queryFn: () =>
      attendanceApi.adminOverview({
        term: termId!,
      }) as Promise<AttendanceOverviewData>,
    enabled: Boolean(termId),
  });

  const note = attendancePencilNote(overview.data);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Attendance overview"
        description="School-wide attendance summary for the current term"
      />

      {!termId && !terms.isLoading ? (
        <EmptyState
          headline={hasTerms ? "No current term" : "No terms yet"}
          body={
            hasTerms
              ? "Set the current term in Academics. This overview uses that term."
              : "Create an academic term before viewing attendance overview."
          }
        />
      ) : (
        <>
          {note ? <PencilAside>{note}</PencilAside> : null}
          <AttendanceOverview
            data={overview.data}
            isLoading={terms.isLoading || overview.isLoading}
            error={overview.error}
          />
        </>
      )}
    </div>
  );
}
