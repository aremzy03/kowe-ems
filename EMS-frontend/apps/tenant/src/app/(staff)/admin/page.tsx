"use client";

import { useQuery } from "@tanstack/react-query";
import {
  AttendanceOverview,
  attendancePencilNote,
  type AttendanceOverviewData,
} from "@/components/attendance/AttendanceOverview";
import {
  CollectionsDashboard,
  collectionsPencilNote,
  type CollectionsDashboardData,
} from "@/components/finance/CollectionsDashboard";
import { EmptyState, PageHeader, PencilAside } from "@/components/ui";
import { academicsApi } from "@/lib/api/academics";
import { financeApi } from "@/lib/api/finance";
import { attendanceApi } from "@/lib/api/attendance";
import { useAppSession } from "@/lib/auth/use-app-session";

export default function AdminHomePage() {
  const { displayName } = useAppSession();
  const terms = useQuery({
    queryKey: ["academics", "terms"],
    queryFn: () => academicsApi.terms.list(),
  });
  const termId = terms.data?.[0]?.id;
  const collections = useQuery({
    queryKey: ["finance", "collections", termId],
    queryFn: () =>
      financeApi.collectionsDashboard(termId!) as Promise<CollectionsDashboardData>,
    enabled: Boolean(termId),
  });
  const attendance = useQuery({
    queryKey: ["attendance", "admin-overview", termId],
    queryFn: () =>
      attendanceApi.adminOverview({
        term: termId!,
      }) as Promise<AttendanceOverviewData>,
    enabled: Boolean(termId),
  });

  const note =
    collectionsPencilNote(collections.data) ?? attendancePencilNote(attendance.data);

  return (
    <div className="space-y-8">
      <PageHeader
        title={`Welcome, ${displayName}`}
        description="School operations overview"
      />

      {!termId && !terms.isLoading ? (
        <EmptyState
          headline="No terms yet"
          body="Create an academic term to see collections and attendance."
        />
      ) : (
        <>
          {note ? <PencilAside>{note}</PencilAside> : null}
          <section className="space-y-3">
            <h2
              className="text-lg font-bold tracking-tight"
              style={{ fontFamily: "var(--font-heading)" }}
            >
              Collections
            </h2>
            <CollectionsDashboard
              data={collections.data}
              isLoading={terms.isLoading || collections.isLoading}
              error={collections.error}
              compact
            />
          </section>

          <section className="space-y-3">
            <h2
              className="text-lg font-bold tracking-tight"
              style={{ fontFamily: "var(--font-heading)" }}
            >
              Attendance
            </h2>
            <AttendanceOverview
              data={attendance.data}
              isLoading={terms.isLoading || attendance.isLoading}
              error={attendance.error}
            />
          </section>
        </>
      )}
    </div>
  );
}
