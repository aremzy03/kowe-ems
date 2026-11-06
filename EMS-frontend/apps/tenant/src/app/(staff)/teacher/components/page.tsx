"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Card,
  CardBody,
  EmptyState,
  Label,
  PageHeader,
  Select,
  Table,
  TBody,
  TD,
  TH,
  THead,
  TR,
} from "@/components/ui";
import {
  academicsApi,
  type ClassSubjectAssignment,
} from "@/lib/api/academics";
import { assessmentApi } from "@/lib/api/assessment";
import { formatApiError } from "@/lib/api/errors";

function assignmentLabel(assignment: ClassSubjectAssignment): string {
  const subject = assignment.subject_name || assignment.subject;
  const level = assignment.class_level_name || assignment.class_level;
  const arm = assignment.arm_name || "";
  const term = assignment.term_name || assignment.term;
  return [subject, [level, arm].filter(Boolean).join(" "), term].join(" · ");
}

function ComponentsTable({ assignment }: { assignment: ClassSubjectAssignment }) {
  const components = useQuery({
    queryKey: [
      "assessment",
      "my-components",
      assignment.subject,
      assignment.class_level,
      assignment.term,
    ],
    queryFn: () =>
      assessmentApi.myComponents({
        subject: assignment.subject,
        class_level: assignment.class_level,
        term: assignment.term,
      }),
  });

  const scopeLabel = [
    assignment.subject_name ?? "Subject",
    [assignment.class_level_name, assignment.arm_name].filter(Boolean).join(" "),
    assignment.term_name,
  ]
    .filter(Boolean)
    .join(" · ");

  if (components.isLoading) {
    return <p className="p-4 text-sm text-ink/70">Loading…</p>;
  }
  if (components.isError) {
    return (
      <p className="p-4 text-sm text-danger" role="alert">
        {formatApiError(components.error, "Could not load components.")}
      </p>
    );
  }
  if ((components.data?.length ?? 0) === 0) {
    return (
      <div className="p-4">
        <EmptyState
          headline="No components yet"
          body={`No scheme for ${scopeLabel}. An admin must set components on Assessment scheme first.`}
        />
      </div>
    );
  }

  return (
    <>
      <p className="border-b border-ink/10 px-4 py-3 text-sm text-ink/70">
        Showing {scopeLabel}
      </p>
      <Table>
        <THead>
          <TR>
            <TH>Name</TH>
            <TH>Weight %</TH>
            <TH>Max score</TH>
          </TR>
        </THead>
        <TBody>
          {(components.data ?? []).map((c) => (
            <TR key={c.id}>
              <TD>{c.name}</TD>
              <TD style={{ fontFamily: "var(--font-mono)" }}>
                {String(c.weight_percentage)}
              </TD>
              <TD style={{ fontFamily: "var(--font-mono)" }}>
                {c.max_score != null ? String(c.max_score) : "—"}
              </TD>
            </TR>
          ))}
        </TBody>
      </Table>
    </>
  );
}

export default function TeacherComponentsPage() {
  const assignments = useQuery({
    queryKey: ["academics", "my-assignments"],
    queryFn: () => academicsApi.myAssignments(),
  });
  const list = assignments.data ?? [];
  const [assignmentId, setAssignmentId] = useState("");
  const selected =
    list.find((assignment) => assignment.id === assignmentId) ?? list[0];

  return (
    <div className="space-y-6">
      <PageHeader
        title="Assessment components"
        description="Weights for your assigned subjects"
      />

      <Card>
        <CardBody className="space-y-2">
          <p
            className="text-sm font-semibold text-ink"
            style={{ fontFamily: "var(--font-heading)" }}
          >
            Scheme editing is admin-only
          </p>
          <p className="text-sm text-ink/70">
            Setting or replacing an assessment scheme requires a school admin.
            Ask an admin to open Assessment scheme and configure components for
            your subject, class, and term. You can still view the scheme below.
          </p>
        </CardBody>
      </Card>

      {assignments.isLoading ? (
        <p className="text-sm text-ink/70">Loading your assignments…</p>
      ) : null}
      {assignments.isError ? (
        <p className="text-sm text-danger" role="alert">
          {formatApiError(assignments.error, "Could not load assignments.")}
        </p>
      ) : null}

      {!assignments.isLoading && !assignments.isError && list.length === 0 ? (
        <EmptyState
          headline="No assignments"
          body="Once an admin assigns you a subject, its components appear here."
        />
      ) : null}

      {selected ? (
        <>
          <Card>
            <CardBody>
              <Label htmlFor="components-assignment">Assignment</Label>
              <Select
                id="components-assignment"
                value={selected.id}
                onChange={(event) => setAssignmentId(event.target.value)}
              >
                {list.map((assignment) => (
                  <option key={assignment.id} value={assignment.id}>
                    {assignmentLabel(assignment)}
                  </option>
                ))}
              </Select>
            </CardBody>
          </Card>
          <Card>
            <CardBody className="p-0">
              <ComponentsTable key={selected.id} assignment={selected} />
            </CardBody>
          </Card>
        </>
      ) : null}
    </div>
  );
}
