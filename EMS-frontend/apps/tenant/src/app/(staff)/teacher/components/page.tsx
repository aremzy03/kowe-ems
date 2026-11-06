"use client";

import { useQuery } from "@tanstack/react-query";
import {
  Card,
  CardBody,
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
import { assessmentApi } from "@/lib/api/assessment";

export default function TeacherComponentsPage() {
  const assignments = useQuery({
    queryKey: ["academics", "my-assignments"],
    queryFn: () => academicsApi.myAssignments(),
  });
  const first = assignments.data?.[0];
  const components = useQuery({
    queryKey: [
      "assessment",
      "my-components",
      first?.subject,
      first?.class_level,
      first?.term,
    ],
    queryFn: () =>
      assessmentApi.myComponents({
        subject: first!.subject,
        class_level: first!.class_level,
        term: first!.term,
      }),
    enabled: Boolean(first),
  });

  const scopeLabel = first
    ? [
        first.subject_name ?? "Subject",
        [first.class_level_name, first.arm_name].filter(Boolean).join(" "),
        first.term_name,
      ]
        .filter(Boolean)
        .join(" · ")
    : null;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Assessment components"
        description="Weights for your assigned subjects"
      />

      <Card>
        <CardBody className="space-y-2">
          <p className="text-sm font-semibold text-ink" style={{ fontFamily: "var(--font-heading)" }}>
            Scheme editing is admin-only
          </p>
          <p className="text-sm text-ink/70">
            Setting or replacing an assessment scheme (
            <span style={{ fontFamily: "var(--font-mono)" }}>set-scheme</span>
            ) requires a school admin. Ask an admin to configure components for
            your subject, class, and term. You can still view the scheme below.
          </p>
        </CardBody>
      </Card>

      <Card>
        <CardBody className="p-0">
          {assignments.isLoading || components.isLoading ? (
            <p className="p-4 text-sm text-ink/70">Loading…</p>
          ) : !first ? (
            <div className="p-4">
              <EmptyState
                headline="No assignments"
                body="Once an admin assigns you a subject, its components appear here."
              />
            </div>
          ) : (components.data?.length ?? 0) === 0 ? (
            <div className="p-4">
              <EmptyState
                headline="No components yet"
                body={
                  scopeLabel
                    ? `No scheme for ${scopeLabel}. An admin must set components first.`
                    : "An admin must set components for this assignment first."
                }
              />
            </div>
          ) : (
            <>
              {scopeLabel ? (
                <p className="border-b border-ink/10 px-4 py-3 text-sm text-ink/70">
                  Showing {scopeLabel}
                </p>
              ) : null}
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
          )}
        </CardBody>
      </Card>
    </div>
  );
}
