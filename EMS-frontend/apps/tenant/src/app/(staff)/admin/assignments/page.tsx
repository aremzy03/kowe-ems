"use client";

import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Button,
  Card,
  CardBody,
  CardHeader,
  CardTitle,
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
  type ClassSubjectAssignment,
  type ClassTeacherAssignment,
  type Session,
  type Term,
} from "@/lib/api/academics";
import { formatApiError } from "@/lib/api/errors";
import {
  membershipsApi,
  type SchoolMembership,
} from "@/lib/api/memberships";

function teacherLabel(m: SchoolMembership) {
  const name = [m.first_name, m.last_name].filter(Boolean).join(" ").trim();
  return name ? `${name} · ${m.email}` : m.email;
}

function termOptionLabel(term: Term, sessions: Session[]) {
  const session = sessions.find((s) => s.id === term.session);
  return session ? `${session.name} · ${term.name}` : term.name;
}

function subjectAssignmentLabel(row: ClassSubjectAssignment) {
  const who = row.teacher_email || "assignment";
  const what = [
    row.subject_name || row.subject_code,
    [row.class_level_name, row.arm_name].filter(Boolean).join(" "),
    row.term_name,
  ]
    .filter(Boolean)
    .join(" · ");
  return what ? `${who} — ${what}` : who;
}

function formTeacherLabel(row: ClassTeacherAssignment) {
  const who = row.teacher_email || "assignment";
  const what = [
    [row.class_level_name, row.arm_name].filter(Boolean).join(" "),
    row.term_name,
  ]
    .filter(Boolean)
    .join(" · ");
  return what ? `${who} — ${what}` : who;
}

export default function AdminAssignmentsPage() {
  const qc = useQueryClient();

  const subjectAssignments = useQuery({
    queryKey: ["academics", "class-subject-assignments"],
    queryFn: () => academicsApi.classSubjectAssignments.list(),
  });
  const formTeacherAssignments = useQuery({
    queryKey: ["academics", "class-teacher-assignments"],
    queryFn: () => academicsApi.classTeacherAssignments.list(),
  });
  const teachers = useQuery({
    queryKey: ["memberships", "members", "teacher", "active"],
    queryFn: () =>
      membershipsApi.members.list({ role: "teacher", is_active: true }),
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
  const subjects = useQuery({
    queryKey: ["academics", "subjects"],
    queryFn: () => academicsApi.subjects.list(),
  });

  const [subjectError, setSubjectError] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

  const [subjectTeacher, setSubjectTeacher] = useState("");
  const [subjectId, setSubjectId] = useState("");
  const [subjectClassLevel, setSubjectClassLevel] = useState("");
  const [subjectArm, setSubjectArm] = useState("");
  const [subjectTerm, setSubjectTerm] = useState("");

  const [formTeacher, setFormTeacher] = useState("");
  const [formClassLevel, setFormClassLevel] = useState("");
  const [formArm, setFormArm] = useState("");
  const [formTerm, setFormTerm] = useState("");

  const [pendingSubjectDelete, setPendingSubjectDelete] =
    useState<ClassSubjectAssignment | null>(null);
  const [pendingFormDelete, setPendingFormDelete] =
    useState<ClassTeacherAssignment | null>(null);

  const subjectArms = useMemo(
    () =>
      (arms.data ?? []).filter(
        (a) => !subjectClassLevel || a.class_level === subjectClassLevel,
      ),
    [arms.data, subjectClassLevel],
  );

  const formArms = useMemo(
    () =>
      (arms.data ?? []).filter(
        (a) => !formClassLevel || a.class_level === formClassLevel,
      ),
    [arms.data, formClassLevel],
  );

  const catalogsLoading =
    teachers.isLoading ||
    sessions.isLoading ||
    terms.isLoading ||
    classLevels.isLoading ||
    arms.isLoading ||
    subjects.isLoading;

  const createSubject = useMutation({
    mutationFn: () =>
      academicsApi.classSubjectAssignments.create({
        teacher: subjectTeacher,
        subject: subjectId,
        class_level: subjectClassLevel,
        arm: subjectArm,
        term: subjectTerm,
      }),
    onSuccess: () => {
      setSubjectTeacher("");
      setSubjectId("");
      setSubjectClassLevel("");
      setSubjectArm("");
      setSubjectTerm("");
      setSubjectError(null);
      void qc.invalidateQueries({
        queryKey: ["academics", "class-subject-assignments"],
      });
    },
    onError: (err) => {
      setSubjectError(
        formatApiError(err, "Could not create subject assignment"),
      );
    },
  });

  const removeSubject = useMutation({
    mutationFn: (id: string) => academicsApi.classSubjectAssignments.remove(id),
    onSuccess: () => {
      setPendingSubjectDelete(null);
      setSubjectError(null);
      void qc.invalidateQueries({
        queryKey: ["academics", "class-subject-assignments"],
      });
    },
    onError: (err) => {
      setPendingSubjectDelete(null);
      setSubjectError(
        formatApiError(err, "Could not delete subject assignment"),
      );
    },
  });

  const createFormTeacher = useMutation({
    mutationFn: () =>
      academicsApi.classTeacherAssignments.create({
        teacher: formTeacher,
        class_level: formClassLevel,
        arm: formArm,
        term: formTerm,
      }),
    onSuccess: () => {
      setFormTeacher("");
      setFormClassLevel("");
      setFormArm("");
      setFormTerm("");
      setFormError(null);
      void qc.invalidateQueries({
        queryKey: ["academics", "class-teacher-assignments"],
      });
    },
    onError: (err) => {
      setFormError(
        formatApiError(err, "Could not create form-teacher assignment"),
      );
    },
  });

  const removeFormTeacher = useMutation({
    mutationFn: (id: string) => academicsApi.classTeacherAssignments.remove(id),
    onSuccess: () => {
      setPendingFormDelete(null);
      setFormError(null);
      void qc.invalidateQueries({
        queryKey: ["academics", "class-teacher-assignments"],
      });
    },
    onError: (err) => {
      setPendingFormDelete(null);
      setFormError(
        formatApiError(err, "Could not delete form-teacher assignment"),
      );
    },
  });

  const canCreateSubject =
    Boolean(subjectTeacher) &&
    Boolean(subjectId) &&
    Boolean(subjectClassLevel) &&
    Boolean(subjectArm) &&
    Boolean(subjectTerm) &&
    !createSubject.isPending;

  const canCreateFormTeacher =
    Boolean(formTeacher) &&
    Boolean(formClassLevel) &&
    Boolean(formArm) &&
    Boolean(formTerm) &&
    !createFormTeacher.isPending;

  const teacherOptions = teachers.data ?? [];
  const termOptions = terms.data ?? [];
  const sessionRows = sessions.data ?? [];

  return (
    <div className="space-y-6">
      <PageHeader
        title="Assignments"
        description="Assign teachers to subjects and form classes"
      />

      <Card>
        <CardHeader>
          <CardTitle>Class–subject</CardTitle>
        </CardHeader>
        <CardBody className="space-y-4">
          {subjectError ? (
            <p className="text-sm text-danger">{subjectError}</p>
          ) : null}
          {teachers.isError ? (
            <p className="text-sm text-danger">
              {formatApiError(teachers.error, "Could not load teachers")}
            </p>
          ) : null}
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            <div>
              <Label htmlFor="subject-teacher">Teacher</Label>
              <Select
                id="subject-teacher"
                value={subjectTeacher}
                disabled={catalogsLoading}
                onChange={(e) => setSubjectTeacher(e.target.value)}
              >
                <option value="">
                  {teachers.isLoading
                    ? "Loading…"
                    : teacherOptions.length === 0
                      ? "No active teachers"
                      : "Choose teacher"}
                </option>
                {teacherOptions.map((m) => (
                  <option key={m.id} value={m.user}>
                    {teacherLabel(m)}
                  </option>
                ))}
              </Select>
            </div>
            <div>
              <Label htmlFor="subject-subject">Subject</Label>
              <Select
                id="subject-subject"
                value={subjectId}
                disabled={catalogsLoading}
                onChange={(e) => setSubjectId(e.target.value)}
              >
                <option value="">
                  {subjects.isLoading ? "Loading…" : "Choose subject"}
                </option>
                {(subjects.data ?? []).map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.code ? `${s.name} (${s.code})` : s.name}
                  </option>
                ))}
              </Select>
            </div>
            <div>
              <Label htmlFor="subject-term">Term</Label>
              <Select
                id="subject-term"
                value={subjectTerm}
                disabled={catalogsLoading}
                onChange={(e) => setSubjectTerm(e.target.value)}
              >
                <option value="">
                  {terms.isLoading ? "Loading…" : "Choose term"}
                </option>
                {termOptions.map((t) => (
                  <option key={t.id} value={t.id}>
                    {termOptionLabel(t, sessionRows)}
                  </option>
                ))}
              </Select>
            </div>
            <div>
              <Label htmlFor="subject-class">Class level</Label>
              <Select
                id="subject-class"
                value={subjectClassLevel}
                disabled={catalogsLoading}
                onChange={(e) => {
                  setSubjectClassLevel(e.target.value);
                  setSubjectArm("");
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
              <Label htmlFor="subject-arm">Arm</Label>
              <Select
                id="subject-arm"
                value={subjectArm}
                disabled={catalogsLoading || !subjectClassLevel}
                onChange={(e) => setSubjectArm(e.target.value)}
              >
                <option value="">
                  {!subjectClassLevel
                    ? "Choose class first"
                    : arms.isLoading
                      ? "Loading…"
                      : "Choose arm"}
                </option>
                {subjectArms.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.name}
                  </option>
                ))}
              </Select>
            </div>
            <div className="flex items-end">
              <Button
                size="sm"
                disabled={!canCreateSubject}
                onClick={() => createSubject.mutate()}
              >
                {createSubject.isPending ? "Assigning…" : "Assign subject"}
              </Button>
            </div>
          </div>
        </CardBody>
        <CardBody className="border-t border-ink/10 p-0">
          {subjectAssignments.isLoading ? (
            <p className="p-4 text-sm text-ink/70">Loading…</p>
          ) : subjectAssignments.isError ? (
            <p className="p-4 text-sm text-danger">
              {formatApiError(
                subjectAssignments.error,
                "Failed to load subject assignments",
              )}
            </p>
          ) : (subjectAssignments.data?.length ?? 0) === 0 ? (
            <div className="p-4">
              <EmptyState
                headline="No subject assignments"
                body="Pick a teacher, subject, class, arm, and term above."
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
                  <TH>Actions</TH>
                </TR>
              </THead>
              <TBody>
                {(subjectAssignments.data ?? []).map((a) => (
                  <TR key={a.id}>
                    <TD>{a.teacher_email ?? "—"}</TD>
                    <TD>{a.subject_name ?? a.subject_code ?? "—"}</TD>
                    <TD>
                      {[a.class_level_name, a.arm_name]
                        .filter(Boolean)
                        .join(" ") || "—"}
                    </TD>
                    <TD>{a.term_name ?? "—"}</TD>
                    <TD>
                      <Button
                        size="sm"
                        variant="destructive"
                        onClick={() => setPendingSubjectDelete(a)}
                      >
                        Remove
                      </Button>
                    </TD>
                  </TR>
                ))}
              </TBody>
            </Table>
          )}
        </CardBody>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Form teachers</CardTitle>
        </CardHeader>
        <CardBody className="space-y-4">
          {formError ? <p className="text-sm text-danger">{formError}</p> : null}
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            <div>
              <Label htmlFor="form-teacher">Teacher</Label>
              <Select
                id="form-teacher"
                value={formTeacher}
                disabled={catalogsLoading}
                onChange={(e) => setFormTeacher(e.target.value)}
              >
                <option value="">
                  {teachers.isLoading
                    ? "Loading…"
                    : teacherOptions.length === 0
                      ? "No active teachers"
                      : "Choose teacher"}
                </option>
                {teacherOptions.map((m) => (
                  <option key={m.id} value={m.user}>
                    {teacherLabel(m)}
                  </option>
                ))}
              </Select>
            </div>
            <div>
              <Label htmlFor="form-term">Term</Label>
              <Select
                id="form-term"
                value={formTerm}
                disabled={catalogsLoading}
                onChange={(e) => setFormTerm(e.target.value)}
              >
                <option value="">
                  {terms.isLoading ? "Loading…" : "Choose term"}
                </option>
                {termOptions.map((t) => (
                  <option key={t.id} value={t.id}>
                    {termOptionLabel(t, sessionRows)}
                  </option>
                ))}
              </Select>
            </div>
            <div>
              <Label htmlFor="form-class">Class level</Label>
              <Select
                id="form-class"
                value={formClassLevel}
                disabled={catalogsLoading}
                onChange={(e) => {
                  setFormClassLevel(e.target.value);
                  setFormArm("");
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
              <Label htmlFor="form-arm">Arm</Label>
              <Select
                id="form-arm"
                value={formArm}
                disabled={catalogsLoading || !formClassLevel}
                onChange={(e) => setFormArm(e.target.value)}
              >
                <option value="">
                  {!formClassLevel
                    ? "Choose class first"
                    : arms.isLoading
                      ? "Loading…"
                      : "Choose arm"}
                </option>
                {formArms.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.name}
                  </option>
                ))}
              </Select>
            </div>
            <div className="flex items-end">
              <Button
                size="sm"
                disabled={!canCreateFormTeacher}
                onClick={() => createFormTeacher.mutate()}
              >
                {createFormTeacher.isPending
                  ? "Assigning…"
                  : "Assign form teacher"}
              </Button>
            </div>
          </div>
        </CardBody>
        <CardBody className="border-t border-ink/10 p-0">
          {formTeacherAssignments.isLoading ? (
            <p className="p-4 text-sm text-ink/70">Loading…</p>
          ) : formTeacherAssignments.isError ? (
            <p className="p-4 text-sm text-danger">
              {formatApiError(
                formTeacherAssignments.error,
                "Failed to load form-teacher assignments",
              )}
            </p>
          ) : (formTeacherAssignments.data?.length ?? 0) === 0 ? (
            <div className="p-4">
              <EmptyState
                headline="No form-teacher assignments"
                body="Pick a teacher, class, arm, and term above."
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
                  <TH>Actions</TH>
                </TR>
              </THead>
              <TBody>
                {(formTeacherAssignments.data ?? []).map((a) => (
                  <TR key={a.id}>
                    <TD>{a.teacher_email ?? "—"}</TD>
                    <TD>{a.class_level_name ?? "—"}</TD>
                    <TD>{a.arm_name ?? "—"}</TD>
                    <TD>{a.term_name ?? "—"}</TD>
                    <TD>
                      <Button
                        size="sm"
                        variant="destructive"
                        onClick={() => setPendingFormDelete(a)}
                      >
                        Remove
                      </Button>
                    </TD>
                  </TR>
                ))}
              </TBody>
            </Table>
          )}
        </CardBody>
      </Card>

      <ConfirmDeleteModal
        open={pendingSubjectDelete !== null}
        onClose={() => setPendingSubjectDelete(null)}
        onConfirm={() => {
          if (pendingSubjectDelete) {
            removeSubject.mutate(pendingSubjectDelete.id);
          }
        }}
        title="Remove subject assignment"
        description={
          pendingSubjectDelete
            ? `Remove ${subjectAssignmentLabel(pendingSubjectDelete)}? Teachers will lose mark-entry access for this subject.`
            : ""
        }
        pending={removeSubject.isPending}
        confirmLabel="Remove"
      />

      <ConfirmDeleteModal
        open={pendingFormDelete !== null}
        onClose={() => setPendingFormDelete(null)}
        onConfirm={() => {
          if (pendingFormDelete) {
            removeFormTeacher.mutate(pendingFormDelete.id);
          }
        }}
        title="Remove form-teacher assignment"
        description={
          pendingFormDelete
            ? `Remove ${formTeacherLabel(pendingFormDelete)}? That teacher will lose attendance marking for this class.`
            : ""
        }
        pending={removeFormTeacher.isPending}
        confirmLabel="Remove"
      />
    </div>
  );
}
