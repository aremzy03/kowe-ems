"use client";

import { useQuery } from "@tanstack/react-query";
import {
  Card,
  CardBody,
  PageHeader,
} from "@/components/ui";
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
    queryFn: () => financeApi.collectionsDashboard(termId!),
    enabled: Boolean(termId),
  });
  const attendance = useQuery({
    queryKey: ["attendance", "admin-overview", termId],
    queryFn: () => attendanceApi.adminOverview({ term: termId! }),
    enabled: Boolean(termId),
  });

  return (
    <div className="space-y-6">
      <PageHeader
        title={`Welcome, ${displayName}`}
        description="School operations overview"
      />
      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardBody>
            <p className="text-sm font-medium text-ink/70">Collections</p>
            {collections.isLoading ? (
              <p className="mt-2 text-sm text-ink/60">Loading…</p>
            ) : collections.error ? (
              <p className="mt-2 text-sm text-danger">Unavailable</p>
            ) : (
              <pre
                className="mt-2 overflow-auto text-xs"
                style={{ fontFamily: "var(--font-mono)" }}
              >
                {JSON.stringify(collections.data ?? {}, null, 2)}
              </pre>
            )}
          </CardBody>
        </Card>
        <Card>
          <CardBody>
            <p className="text-sm font-medium text-ink/70">Attendance</p>
            {attendance.isLoading ? (
              <p className="mt-2 text-sm text-ink/60">Loading…</p>
            ) : attendance.error ? (
              <p className="mt-2 text-sm text-danger">Unavailable</p>
            ) : (
              <pre
                className="mt-2 overflow-auto text-xs"
                style={{ fontFamily: "var(--font-mono)" }}
              >
                {JSON.stringify(attendance.data ?? {}, null, 2)}
              </pre>
            )}
          </CardBody>
        </Card>
      </div>
    </div>
  );
}
