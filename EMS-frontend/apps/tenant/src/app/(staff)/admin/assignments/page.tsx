"use client";

import { useQuery } from "@tanstack/react-query";
import {
  Card,
  CardBody,
  CardHeader,
  CardTitle,
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
        <CardHeader>
          <CardTitle>Class–subject</CardTitle>
        </CardHeader>
        <CardBody className="p-0">
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
                  <TD style={{ fontFamily: "var(--font-mono)" }}>{a.teacher}</TD>
                  <TD style={{ fontFamily: "var(--font-mono)" }}>{a.subject}</TD>
                  <TD style={{ fontFamily: "var(--font-mono)" }}>
                    {a.class_level}
                    {a.arm ? `/${a.arm}` : ""}
                  </TD>
                  <TD style={{ fontFamily: "var(--font-mono)" }}>{a.term}</TD>
                </TR>
              ))}
            </TBody>
          </Table>
        </CardBody>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Class teachers</CardTitle>
        </CardHeader>
        <CardBody className="p-0">
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
                  <TD style={{ fontFamily: "var(--font-mono)" }}>{a.teacher}</TD>
                  <TD style={{ fontFamily: "var(--font-mono)" }}>{a.class_level}</TD>
                  <TD style={{ fontFamily: "var(--font-mono)" }}>{a.arm}</TD>
                  <TD style={{ fontFamily: "var(--font-mono)" }}>{a.term}</TD>
                </TR>
              ))}
            </TBody>
          </Table>
        </CardBody>
      </Card>
    </div>
  );
}
