"use client";

import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Button,
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
import { ConfirmDeleteModal } from "@/components/ui/client";
import {
  academicsApi,
  type Enrollment,
  type EnrollmentStatus,
  type Session,
  type Student,
  type Term,
} from "@/lib/api/academics";
import { formatApiError } from "@/lib/api/errors";

const ENROLLMENT_STATUSES: { value: EnrollmentStatus; label: string }[] = [
  { value: "active", label: "Active" },
  { value: "withdrawn", label: "Withdrawn" },
  { value: "graduated", label: "Graduated" },
];

function enrollmentLabel(row: Enrollment) {
  const who = row.student_name || "this enrollment";
  const when = [row.session_name, row.term_name].filter(Boolean).join(" · ");
  return when ? `${who} (${when})` : who;
}

function studentLabel(s: Student) {
  const name =
    s.full_name || [s.first_name, s.last_name].filter(Boolean).join(" ");
  return s.admission_number
    ? `${name || "Student"} · ${s.admission_number}`
    : name || s.id;
}

function termOptionLabel(term: Term, sessions: Session[]) {
  const session = sessions.find((s) => s.id === term.session);
  return session ? `${session.name} · ${term.name}` : term.name;
}

export default function AdminEnrollmentPage() {
  const qc = useQueryClient();
  const enrollments = useQuery({
    queryKey: ["academics", "enrollments"],
    queryFn: () => academicsApi.enrollments.list(),
  });
  const students = useQuery({
    queryKey: ["academics", "students"],
    queryFn: () => academicsApi.students.list(),
  });
  const sessions = useQuery({
    queryKey: ["academics", "sessions"],
    queryFn: () => academicsApi.sessions.list(),
  });
  const terms = useQuery({
    queryKey: ["academics", "terms"],
    queryFn: () => academicsApi.terms.list(),
  });
  const classLevels = useQuery({
    queryKey: ["academics", "class-levels"],
    queryFn: () => academicsApi.classLevels.list(),
  });
  const arms = useQuery({
    queryKey: ["academics", "arms"],
    queryFn: () => academicsApi.arms.list(),
  });

  const [student, setStudent] = useState("");
  const [session, setSession] = useState("");
  const [term, setTerm] = useState("");
  const [classLevel, setClassLevel] = useState("");
  const [arm, setArm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pendingDelete, setPendingDelete] = useState<Enrollment | null>(null);

  const termsForSession = useMemo(
    () =>
      (terms.data ?? []).filter((t) => !session || t.session === session),
    [terms.data, session],
  );

  const armsForClass = useMemo(
    () =>
      (arms.data ?? []).filter(
        (a) => !classLevel || a.class_level === classLevel,
      ),
    [arms.data, classLevel],
  );

  const create = useMutation({
    mutationFn: () =>
      academicsApi.enrollments.create({
        student,
        session,
        term,
        class_level: classLevel,
        arm,
      }),
    onSuccess: () => {
      setStudent("");
      setSession("");
      setTerm("");
      setClassLevel("");
      setArm("");
      setError(null);
      void qc.invalidateQueries({ queryKey: ["academics", "enrollments"] });
    },
    onError: (err) => {
      setError(formatApiError(err, "Could not enroll student"));
    },
  });

  const updateStatus = useMutation({
    mutationFn: ({ id, status }: { id: string; status: EnrollmentStatus }) =>
      academicsApi.enrollments.update(id, { status }),
    onSuccess: () => {
      setError(null);
      void qc.invalidateQueries({ queryKey: ["academics", "enrollments"] });
    },
    onError: (err) => {
      setError(formatApiError(err, "Could not update enrollment"));
    },
  });

  const removeEnrollment = useMutation({
    mutationFn: (id: string) => academicsApi.enrollments.remove(id),
    onSuccess: () => {
      setPendingDelete(null);
      setError(null);
      void qc.invalidateQueries({ queryKey: ["academics", "enrollments"] });
    },
    onError: (err) => {
      setPendingDelete(null);
      setError(formatApiError(err, "Could not delete enrollment"));
    },
  });

  const catalogsLoading =
    students.isLoading ||
    sessions.isLoading ||
    terms.isLoading ||
    classLevels.isLoading ||
    arms.isLoading;

  const canEnroll =
    Boolean(student) &&
    Boolean(session) &&
    Boolean(term) &&
    Boolean(classLevel) &&
    Boolean(arm) &&
    !create.isPending;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Enrollment"
        description="Place students into classes for a term"
      />
      {error ? <p className="text-sm text-danger">{error}</p> : null}
      <Card>
        <CardBody className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <div>
            <Label htmlFor="enroll-student">Student</Label>
            <Select
              id="enroll-student"
              value={student}
              disabled={catalogsLoading}
              onChange={(e) => setStudent(e.target.value)}
            >
              <option value="">
                {students.isLoading ? "Loading…" : "Choose student"}
              </option>
              {(students.data ?? []).map((s) => (
                <option key={s.id} value={s.id}>
                  {studentLabel(s)}
                </option>
              ))}
            </Select>
          </div>
          <div>
            <Label htmlFor="enroll-session">Session</Label>
            <Select
              id="enroll-session"
              value={session}
              disabled={catalogsLoading}
              onChange={(e) => {
                setSession(e.target.value);
                setTerm("");
              }}
            >
              <option value="">
                {sessions.isLoading ? "Loading…" : "Choose session"}
              </option>
              {(sessions.data ?? []).map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </Select>
          </div>
          <div>
            <Label htmlFor="enroll-term">Term</Label>
            <Select
              id="enroll-term"
              value={term}
              disabled={catalogsLoading || !session}
              onChange={(e) => setTerm(e.target.value)}
            >
              <option value="">
                {!session
                  ? "Choose session first"
                  : terms.isLoading
                    ? "Loading…"
                    : "Choose term"}
              </option>
              {termsForSession.map((t) => (
                <option key={t.id} value={t.id}>
                  {termOptionLabel(t, sessions.data ?? [])}
                </option>
              ))}
            </Select>
          </div>
          <div>
            <Label htmlFor="enroll-class">Class level</Label>
            <Select
              id="enroll-class"
              value={classLevel}
              disabled={catalogsLoading}
              onChange={(e) => {
                setClassLevel(e.target.value);
                setArm("");
              }}
            >
              <option value="">
                {classLevels.isLoading ? "Loading…" : "Choose class"}
              </option>
              {(classLevels.data ?? []).map((level) => (
                <option key={level.id} value={level.id}>
                  {level.name}
                </option>
              ))}
            </Select>
          </div>
          <div>
            <Label htmlFor="enroll-arm">Arm</Label>
            <Select
              id="enroll-arm"
              value={arm}
              disabled={catalogsLoading || !classLevel}
              onChange={(e) => setArm(e.target.value)}
            >
              <option value="">
                {!classLevel
                  ? "Choose class first"
                  : arms.isLoading
                    ? "Loading…"
                    : "Choose arm"}
              </option>
              {armsForClass.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.name}
                </option>
              ))}
            </Select>
          </div>
          <div className="flex items-end">
            <Button
              size="sm"
              disabled={!canEnroll}
              onClick={() => create.mutate()}
            >
              Enroll
            </Button>
          </div>
        </CardBody>
      </Card>
      <Card>
        <CardBody className="p-0">
          {enrollments.isLoading ? (
            <p className="p-4 text-sm text-ink/70">Loading…</p>
          ) : enrollments.isError ? (
            <p className="p-4 text-sm text-danger">
              {enrollments.error instanceof Error
                ? enrollments.error.message
                : "Failed to load"}
            </p>
          ) : (enrollments.data?.length ?? 0) === 0 ? (
            <div className="p-4">
              <EmptyState
                headline="No enrollments yet"
                body="Place a student into a class and term to begin."
              />
            </div>
          ) : (
            <Table>
              <THead>
                <TR>
                  <TH>Student</TH>
                  <TH>Session / term</TH>
                  <TH>Class</TH>
                  <TH>Arm</TH>
                  <TH>Status</TH>
                  <TH>Actions</TH>
                </TR>
              </THead>
              <TBody>
                {(enrollments.data ?? []).map((e) => {
                  const status = (e.status || "active") as EnrollmentStatus;
                  const known = ENROLLMENT_STATUSES.some((s) => s.value === status);
                  return (
                    <TR key={e.id}>
                      <TD>
                        <span className="font-medium">
                          {e.student_name ?? "—"}
                        </span>
                        {e.student_admission_number ? (
                          <span
                            className="mt-0.5 block text-xs text-ink/65"
                            style={{ fontFamily: "var(--font-mono)" }}
                          >
                            {e.student_admission_number}
                          </span>
                        ) : null}
                      </TD>
                      <TD>
                        {[e.session_name, e.term_name]
                          .filter(Boolean)
                          .join(" · ") || "—"}
                      </TD>
                      <TD>{e.class_level_name ?? "—"}</TD>
                      <TD>{e.arm_name ?? "—"}</TD>
                      <TD>
                        <Select
                          aria-label={`Status for ${e.student_name ?? "enrollment"}`}
                          value={known ? status : "active"}
                          disabled={updateStatus.isPending || removeEnrollment.isPending}
                          onChange={(ev) =>
                            updateStatus.mutate({
                              id: e.id,
                              status: ev.target.value as EnrollmentStatus,
                            })
                          }
                        >
                          {ENROLLMENT_STATUSES.map((option) => (
                            <option key={option.value} value={option.value}>
                              {option.label}
                            </option>
                          ))}
                        </Select>
                      </TD>
                      <TD>
                        <Button
                          variant="ghost"
                          size="sm"
                          disabled={removeEnrollment.isPending}
                          onClick={() => setPendingDelete(e)}
                        >
                          Delete
                        </Button>
                      </TD>
                    </TR>
                  );
                })}
              </TBody>
            </Table>
          )}
        </CardBody>
      </Card>

      <ConfirmDeleteModal
        open={Boolean(pendingDelete)}
        onClose={() => setPendingDelete(null)}
        onConfirm={() => {
          if (pendingDelete) removeEnrollment.mutate(pendingDelete.id);
        }}
        title={
          pendingDelete
            ? `Delete enrollment for ${enrollmentLabel(pendingDelete)}?`
            : "Delete enrollment?"
        }
        description="This removes the placement. Prefer withdraw or graduate if the student left the class but the record should stay."
        pending={removeEnrollment.isPending}
      />
    </div>
  );
}
