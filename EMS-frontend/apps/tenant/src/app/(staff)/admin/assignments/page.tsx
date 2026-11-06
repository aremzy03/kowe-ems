"use client";

import { useQuery } from "@tanstack/react-query";
import {
  Card,
  CardBody,
  CardHeader,
  CardTitle,
  EmptyState,
  PageHeader,
  Table,
  TBody,
  TD,
  TH,
  THead,
  TR,
} from "@/components/ui";
import { academicsApi } from "@/lib/api/academics";

export default function AdminAssignmentsPage() {
  const subject = useQuery({
    queryKey: ["academics", "class-subject-assignments"],
    queryFn: () => academicsApi.classSubjectAssignments.list(),
  });
  const teacher = useQuery({
    queryKey: ["academics", "class-teacher-assignments"],
    queryFn: () => academicsApi.classTeacherAssignments.list(),
  });

  return (
    <div className="space-y-6">
      <PageHeader
        title="Assignments"
        description="Class-subject and form-teacher assignments"
      />

      <Card>
        <CardBody className="space-y-1">
          <p
            className="text-sm font-semibold text-ink"
            style={{ fontFamily: "var(--font-heading)" }}
          >
            Create UI deferred
          </p>
          <p className="text-sm text-ink/70">
            Assignment create APIs exist, but there is no staff directory
            endpoint to pick a teacher (invite-only). Use Django admin or the
            API until a membership list ships.
          </p>
        </CardBody>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Class–subject</CardTitle>
        </CardHeader>
        <CardBody className="p-0">
          {subject.isLoading ? (
            <p className="p-4 text-sm text-ink/70">Loading…</p>
          ) : subject.isError ? (
            <p className="p-4 text-sm text-danger">
              {subject.error instanceof Error
                ? subject.error.message
                : "Failed to load"}
            </p>
          ) : (subject.data?.length ?? 0) === 0 ? (
            <div className="p-4">
              <EmptyState
                headline="No subject assignments"
                body="Assign teachers to subjects via the API until create UI lands."
              />
            </div>
          ) : (
            <Table>
              <THead>
                <TR>
                  <TH>Teacher</TH>
                  <TH>Subject</TH>
                  <TH>Class</TH>
                  <TH>Term</TH>
                </TR>
              </THead>
              <TBody>
                {(subject.data ?? []).map((a) => (
                  <TR key={a.id}>
                    <TD>{a.teacher_email ?? "—"}</TD>
                    <TD>
                      {a.subject_name ?? a.subject_code ?? "—"}
                    </TD>
                    <TD>
                      {[a.class_level_name, a.arm_name]
                        .filter(Boolean)
                        .join(" ") || "—"}
                    </TD>
                    <TD>{a.term_name ?? "—"}</TD>
                  </TR>
                ))}
              </TBody>
            </Table>
          )}
        </CardBody>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Class teachers</CardTitle>
        </CardHeader>
        <CardBody className="p-0">
          {teacher.isLoading ? (
            <p className="p-4 text-sm text-ink/70">Loading…</p>
          ) : teacher.isError ? (
            <p className="p-4 text-sm text-danger">
              {teacher.error instanceof Error
                ? teacher.error.message
                : "Failed to load"}
            </p>
          ) : (teacher.data?.length ?? 0) === 0 ? (
            <div className="p-4">
              <EmptyState
                headline="No form-teacher assignments"
                body="Assign form teachers via the API until create UI lands."
              />
            </div>
          ) : (
            <Table>
              <THead>
                <TR>
                  <TH>Teacher</TH>
                  <TH>Class</TH>
                  <TH>Arm</TH>
                  <TH>Term</TH>
                </TR>
              </THead>
              <TBody>
                {(teacher.data ?? []).map((a) => (
                  <TR key={a.id}>
                    <TD>{a.teacher_email ?? "—"}</TD>
                    <TD>{a.class_level_name ?? "—"}</TD>
                    <TD>{a.arm_name ?? "—"}</TD>
                    <TD>{a.term_name ?? "—"}</TD>
                  </TR>
                ))}
              </TBody>
            </Table>
          )}
        </CardBody>
      </Card>
    </div>
  );
}
