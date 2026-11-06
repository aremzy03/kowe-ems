"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  Badge,
  Card,
  CardBody,
  CardHeader,
  CardTitle,
  PageHeader,
} from "@/components/ui";
import { academicsApi } from "@/lib/api/academics";
import { useAppSession } from "@/lib/auth/use-app-session";

export default function TeacherHomePage() {
  const { displayName } = useAppSession();
  const assignments = useQuery({
    queryKey: ["academics", "my-assignments"],
    queryFn: () => academicsApi.myAssignments(),
  });
  const classes = useQuery({
    queryKey: ["academics", "my-classes"],
    queryFn: () => academicsApi.myClasses(),
  });

  return (
    <div>
      <PageHeader
        title={`Welcome, ${displayName}`}
        description="Your class-subject and form-teacher assignments"
      />

      <section className="mb-8" aria-label="Subject assignments">
        <h2
          className="mb-3 text-xl font-bold"
          style={{ fontFamily: "var(--font-heading)" }}
        >
          Assignments
        </h2>
        {assignments.isLoading ? (
          <p className="text-sm text-ink/70">Loading…</p>
        ) : null}
        {assignments.error ? (
          <p className="text-sm text-danger">
            {assignments.error instanceof Error
              ? assignments.error.message
              : "Failed to load"}
          </p>
        ) : null}
        {!assignments.isLoading && (assignments.data?.length ?? 0) === 0 ? (
          <p className="text-sm text-ink/70">No subject assignments yet.</p>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {(assignments.data ?? []).map((assignment) => (
              <Card key={assignment.id}>
                <CardHeader className="flex items-start justify-between gap-2">
                  <div>
                    <CardTitle>{assignment.subject}</CardTitle>
                    <p className="mt-1 text-sm text-ink/70">
                      Level {assignment.class_level}
                      {assignment.arm ? ` · Arm ${assignment.arm}` : ""}
                    </p>
                  </div>
                  <Badge variant="info">Assigned</Badge>
                </CardHeader>
                <CardBody className="flex items-center justify-between gap-3">
                  <Link
                    href="/teacher/marks"
                    className="text-sm font-semibold text-accent-1 underline-offset-2 hover:underline"
                    style={{ fontFamily: "var(--font-heading)" }}
                  >
                    Enter marks
                  </Link>
                </CardBody>
              </Card>
            ))}
          </div>
        )}
      </section>

      <section aria-label="Form teacher classes">
        <h2
          className="mb-3 text-xl font-bold"
          style={{ fontFamily: "var(--font-heading)" }}
        >
          Form teacher
        </h2>
        {classes.isLoading ? (
          <p className="text-sm text-ink/70">Loading…</p>
        ) : null}
        {!classes.isLoading && (classes.data?.length ?? 0) === 0 ? (
          <p className="text-sm text-ink/70">No form classes assigned.</p>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2">
            {(classes.data ?? []).map((ft) => (
              <Card key={ft.id}>
                <CardHeader>
                  <CardTitle>
                    Level {ft.class_level} · Arm {ft.arm}
                  </CardTitle>
                  <p className="mt-1 text-sm text-ink/70">Form class</p>
                </CardHeader>
                <CardBody className="flex flex-wrap gap-3 text-sm font-semibold">
                  <Link
                    href="/teacher/attendance"
                    className="text-accent-1 underline-offset-2 hover:underline"
                  >
                    Register
                  </Link>
                  <Link
                    href="/teacher/remarks"
                    className="text-accent-1 underline-offset-2 hover:underline"
                  >
                    Remarks
                  </Link>
                </CardBody>
              </Card>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
