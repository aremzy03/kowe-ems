"use client";

import Link from "next/link";
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
import { Button, EmptyState, PageHeader, PencilAside } from "@/components/ui";
import { academicsApi, currentTerm } from "@/lib/api/academics";
import { financeApi } from "@/lib/api/finance";
import { attendanceApi } from "@/lib/api/attendance";
import { useAppSession } from "@/lib/auth/use-app-session";

export default function AdminHomePage() {
  const { displayName } = useAppSession();
  const terms = useQuery({
    queryKey: ["academics", "terms"],
    queryFn: () => academicsApi.terms.list(),
  });
  const termId = currentTerm(terms.data)?.id;
  const hasTerms = (terms.data?.length ?? 0) > 0;
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
        actions={
          <Link href="/admin/payment-account">
            <Button variant="secondary" size="sm">
              Payment account
            </Button>
          </Link>
        }
      />

      {!termId && !terms.isLoading ? (
        <EmptyState
          headline={hasTerms ? "No current term" : "No terms yet"}
          body={
            hasTerms
              ? "Set the current term in Academics. Collections and attendance here use that term."
              : "Create an academic term to see collections and attendance."
          }
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
