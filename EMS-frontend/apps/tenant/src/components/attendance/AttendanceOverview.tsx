"use client";

import {
  Card,
  CardBody,
  EmptyState,
  KpiCard,
  Table,
  TBody,
  TD,
  TH,
  THead,
  TR,
} from "@/components/ui";
import { MarkEntryStatusBadge } from "./AttendanceStatusBadge";

export type AttendanceOverviewClass = {
  class_level_id?: string;
  class_level_name?: string;
  arm_id?: string;
  arm_name?: string;
  term_id?: string;
  term_name?: string;
  session_name?: string;
  enrolled_count?: number;
  marked_count?: number;
  status?: string;
  days_with_marks?: number;
  marks_total?: number;
  last_marked_date?: string | null;
  never_marked?: boolean;
  class_teacher?: { id?: string; email?: string } | null;
};

export type AttendanceOverviewData = {
  mode?: "date" | "term" | string;
  date?: string;
  term_id?: string;
  term_name?: string;
  session_name?: string;
  total_school_days?: number | null;
  classes?: AttendanceOverviewClass[];
  summary?: {
    total_classes?: number;
    complete?: number;
    partial?: number;
    pending?: number;
    empty?: number;
    never_marked?: number;
    with_any_marks?: number;
  };
  note?: string;
};

export type AttendanceOverviewProps = {
  data?: AttendanceOverviewData | null;
  isLoading?: boolean;
  error?: Error | unknown | null;
};

function classLabel(row: AttendanceOverviewClass): string {
  return [row.class_level_name, row.arm_name].filter(Boolean).join(" ") || "—";
}

export function AttendanceOverview({
  data,
  isLoading,
  error,
}: AttendanceOverviewProps) {
  if (isLoading) {
    return <p className="text-sm text-ink/70">Loading attendance…</p>;
  }

  if (error) {
    return (
      <p className="text-sm text-danger">
        {error instanceof Error ? error.message : "Failed to load attendance"}
      </p>
    );
  }

  if (!data) {
    return (
      <EmptyState
        headline="No attendance overview"
        body="Create a term and enroll students to see mark-entry status."
      />
    );
  }

  const classes = data.classes ?? [];
  const summary = data.summary ?? {};
  const isDateMode = data.mode === "date";

  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <KpiCard
          label="Classes"
          value={String(summary.total_classes ?? classes.length)}
        />
        {isDateMode ? (
          <>
            <KpiCard
              label="Complete"
              value={String(summary.complete ?? 0)}
            />
            <KpiCard
              label="Partial"
              value={String(summary.partial ?? 0)}
            />
            <KpiCard
              label="Pending"
              value={String(summary.pending ?? 0)}
            />
          </>
        ) : (
          <>
            <KpiCard
              label="With marks"
              value={String(summary.with_any_marks ?? 0)}
            />
            <KpiCard
              label="Never marked"
              value={String(summary.never_marked ?? 0)}
            />
            <KpiCard
              label="School days"
              value={
                data.total_school_days != null
                  ? String(data.total_school_days)
                  : "—"
              }
            />
          </>
        )}
      </div>

      <Card>
        <CardBody className="p-0">
          <Table className="border-0 shadow-none">
            <THead>
              <TR>
                <TH>Class</TH>
                <TH>Enrolled</TH>
                {isDateMode ? (
                  <>
                    <TH>Marked</TH>
                    <TH>Status</TH>
                  </>
                ) : (
                  <>
                    <TH>Days marked</TH>
                    <TH>Marks</TH>
                    <TH>Last marked</TH>
                    <TH>Status</TH>
                  </>
                )}
                <TH>Form teacher</TH>
              </TR>
            </THead>
            <TBody>
              {classes.length === 0 ? (
                <TR>
                  <TD
                    colSpan={isDateMode ? 5 : 7}
                    className="text-sm text-ink/65"
                  >
                    No classes in this overview.
                  </TD>
                </TR>
              ) : (
                classes.map((row) => (
                  <TR
                    key={`${row.class_level_id}-${row.arm_id}-${row.term_id}`}
                  >
                    <TD className="font-medium">{classLabel(row)}</TD>
                    <TD style={{ fontFamily: "var(--font-mono)" }}>
                      {row.enrolled_count ?? 0}
                    </TD>
                    {isDateMode ? (
                      <>
                        <TD style={{ fontFamily: "var(--font-mono)" }}>
                          {row.marked_count ?? 0}
                        </TD>
                        <TD>
                          <MarkEntryStatusBadge status={row.status} />
                        </TD>
                      </>
                    ) : (
                      <>
                        <TD style={{ fontFamily: "var(--font-mono)" }}>
                          {row.days_with_marks ?? 0}
                        </TD>
                        <TD style={{ fontFamily: "var(--font-mono)" }}>
                          {row.marks_total ?? 0}
                        </TD>
                        <TD style={{ fontFamily: "var(--font-mono)" }}>
                          {row.last_marked_date ?? "—"}
                        </TD>
                        <TD>
                          {row.never_marked ? (
                            <MarkEntryStatusBadge status="pending" />
                          ) : (row.days_with_marks ?? 0) > 0 ? (
                            <MarkEntryStatusBadge status="complete" />
                          ) : (
                            <MarkEntryStatusBadge status="empty" />
                          )}
                        </TD>
                      </>
                    )}
                    <TD className="text-sm text-ink/70">
                      {row.class_teacher?.email ?? "—"}
                    </TD>
                  </TR>
                ))
              )}
            </TBody>
          </Table>
        </CardBody>
      </Card>
    </div>
  );
}
