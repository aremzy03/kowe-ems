"use client";

import { useQuery } from "@tanstack/react-query";
import { AttendanceStatusBadge } from "@/components/attendance/AttendanceStatusBadge";
import {
  Card,
  CardBody,
  CardHeader,
  CardTitle,
  EmptyState,
  KpiCard,
  PageHeader,
  PencilAside,
  PencilBars,
  Table,
  TBody,
  TD,
  TH,
  THead,
  TR,
  weekdayAttendanceRates,
} from "@/components/ui";
import { academicsApi, currentTerm } from "@/lib/api/academics";
import { attendanceApi } from "@/lib/api/attendance";
import { useParentChildren } from "@/lib/parent/children";

type AttendanceSummary = {
  days_present?: number;
  days_absent?: number;
  days_late?: number;
  days_excused?: number;
  days_marked?: number;
  total_school_days?: number | null;
  attendance_percentage?: string | null;
  available?: boolean;
  message?: string;
};

type DailyRow = {
  id?: string;
  date?: string;
  status?: string;
  remarks?: string;
  class_level_name?: string;
  arm_name?: string;
};

type DailyPayload = {
  count?: number;
  results?: DailyRow[];
};

export default function ParentAttendancePage() {
  const { selected } = useParentChildren();
  const terms = useQuery({
    queryKey: ["academics", "terms"],
    queryFn: () => academicsApi.terms.list(),
  });
  const termId = currentTerm(terms.data)?.id;
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

  if (terms.isSuccess && !termId) {
    const hasTerms = (terms.data?.length ?? 0) > 0;
    return (
      <div className="mx-auto w-full max-w-5xl space-y-4">
        <PageHeader
          title="Attendance"
          description={`${selected.name} · term summary and daily log`}
        />
        <EmptyState
          headline={hasTerms ? "No current term" : "No terms yet"}
          body={
            hasTerms
              ? "Attendance follows the term the school marks as current."
              : "The school has not added a term yet."
          }
        />
      </div>
    );
  }

  const summaryData = summary.data as AttendanceSummary | undefined;
  const dailyData = daily.data as DailyPayload | undefined;
  const days = dailyData?.results ?? [];
  const weekdayRates = weekdayAttendanceRates(days);
  const absentDays = summaryData?.days_absent ?? 0;
  const absentNote =
    summaryData && summaryData.available !== false && absentDays > 0
      ? absentDays === 1
        ? "1 day absent this term."
        : `${absentDays} days absent this term.`
      : null;

  return (
    <div className="mx-auto w-full max-w-5xl space-y-4">
      <PageHeader
        title="Attendance"
        description={`${selected.name} · term summary and daily log`}
      />

      {absentNote ? <PencilAside>{absentNote}</PencilAside> : null}

      {summary.isLoading || terms.isLoading ? (
        <p className="text-sm text-ink/70">Loading summary…</p>
      ) : summary.error ? (
        <p className="text-sm text-danger">
          {summary.error instanceof Error
            ? summary.error.message
            : "Failed to load summary"}
        </p>
      ) : summaryData && summaryData.available === false ? (
        <EmptyState
          headline="No attendance yet"
          body={
            summaryData.message ||
            "No attendance marks recorded for this student this term."
          }
        />
      ) : summaryData ? (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
          <KpiCard
            label="Present"
            value={String(summaryData.days_present ?? 0)}
            tone="green"
          />
          <KpiCard
            label="Absent"
            value={String(summaryData.days_absent ?? 0)}
          />
          <KpiCard label="Late" value={String(summaryData.days_late ?? 0)} />
          <KpiCard
            label="Excused"
            value={String(summaryData.days_excused ?? 0)}
          />
          <KpiCard
            label="Rate"
            value={
              summaryData.attendance_percentage != null
                ? `${summaryData.attendance_percentage}%`
                : "—"
            }
            rate={
              summaryData.attendance_percentage != null
                ? Number(String(summaryData.attendance_percentage).replace("%", ""))
                : undefined
            }
            rateTone="green"
            delta={
              summaryData.total_school_days != null
                ? `${summaryData.days_marked ?? 0} of ${summaryData.total_school_days} school days`
                : undefined
            }
          />
        </div>
      ) : null}

      {weekdayRates ? (
        <Card>
          <CardHeader>
            <CardTitle>Weekday roll</CardTitle>
          </CardHeader>
          <CardBody>
            <PencilBars points={weekdayRates} />
          </CardBody>
        </Card>
      ) : null}

      <section className="space-y-3">
        <h2
          className="text-lg font-bold tracking-tight"
          style={{ fontFamily: "var(--font-heading)" }}
        >
          Daily log
        </h2>
        {daily.isLoading ? (
          <p className="text-sm text-ink/70">Loading daily marks…</p>
        ) : daily.error ? (
          <p className="text-sm text-danger">
            {daily.error instanceof Error
              ? daily.error.message
              : "Failed to load daily attendance"}
          </p>
        ) : (
          <Card ledger>
            <CardBody className="p-0">
              <Table className="border-0 shadow-none">
                <THead>
                  <TR>
                    <TH>Date</TH>
                    <TH>Status</TH>
                    <TH>Class</TH>
                    <TH>Remarks</TH>
                  </TR>
                </THead>
                <TBody>
                  {days.length === 0 ? (
                    <TR>
                      <TD colSpan={4} className="text-sm text-ink/65">
                        No daily attendance rows for this term.
                      </TD>
                    </TR>
                  ) : (
                    days.map((row, i) => (
                      <TR key={row.id ?? `${row.date}-${i}`}>
                        <TD style={{ fontFamily: "var(--font-mono)" }}>
                          {row.date ?? "—"}
                        </TD>
                        <TD>
                          <AttendanceStatusBadge status={row.status} />
                        </TD>
                        <TD>
                          {[row.class_level_name, row.arm_name]
                            .filter(Boolean)
                            .join(" ") || "—"}
                        </TD>
                        <TD className="text-sm text-ink/70">
                          {row.remarks || "—"}
                        </TD>
                      </TR>
                    ))
                  )}
                </TBody>
              </Table>
            </CardBody>
          </Card>
        )}
      </section>
    </div>
  );
}
