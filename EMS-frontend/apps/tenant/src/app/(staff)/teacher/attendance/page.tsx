"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Button,
  Card,
  CardBody,
  EmptyState,
  Input,
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
import { Toast } from "@/components/ui/client";
import {
  academicsApi,
  type ClassTeacherAssignment,
} from "@/lib/api/academics";
import {
  attendanceApi,
  type AttendanceStatus,
  type BulkAttendanceUpsertBody,
  type ClassRegister,
  type RegisterStudent,
} from "@/lib/api/attendance";
import { formatApiError, partialBulkFailureMessage } from "@/lib/api/errors";

const STATUS_OPTIONS: { value: AttendanceStatus; label: string }[] = [
  { value: "present", label: "Present" },
  { value: "absent", label: "Absent" },
  { value: "late", label: "Late" },
  { value: "excused", label: "Excused" },
];

type RowMark = { status: AttendanceStatus | ""; remarks: string };

function todayIso(): string {
  const now = new Date();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");
  return `${now.getFullYear()}-${month}-${day}`;
}

function classLabel(assignment: ClassTeacherAssignment): string {
  const level = assignment.class_level_name || assignment.class_level;
  const arm = assignment.arm_name || "";
  const term = assignment.term_name || assignment.term;
  return [[level, arm].filter(Boolean).join(" "), term].join(" · ");
}

function isStatus(value: string | null | undefined): value is AttendanceStatus {
  return STATUS_OPTIONS.some((option) => option.value === value);
}

function isWeekend(isoDate: string): boolean {
  const day = new Date(`${isoDate}T00:00:00`).getDay();
  return day === 0 || day === 6;
}

function studentsFromRegister(register: ClassRegister | undefined): RegisterStudent[] {
  if (!register) return [];
  if (register.students && register.students.length > 0) return register.students;
  return (register.grid ?? []).map((row) => row.student);
}

function existingMark(
  register: ClassRegister | undefined,
  studentId: string,
  date: string,
): RowMark {
  const row = register?.grid?.find((item) => item.student.id === studentId);
  const cell = row?.cells.find((item) => item.date === date);
  return {
    status: isStatus(cell?.status) ? cell.status : "",
    remarks: cell?.remarks ?? "",
  };
}

function RegisterGrid({
  assignment,
  date,
}: {
  assignment: ClassTeacherAssignment;
  date: string;
}) {
  const qc = useQueryClient();
  const register = useQuery({
    queryKey: [
      "attendance",
      "register",
      assignment.class_level,
      assignment.arm,
      assignment.term,
      date,
    ],
    queryFn: () =>
      attendanceApi.register({
        class_level: assignment.class_level,
        arm: assignment.arm,
        term: assignment.term,
        date_from: date,
        date_to: date,
      }),
    enabled: Boolean(date),
  });

  const students = studentsFromRegister(register.data);
  const [marks, setMarks] = useState<Record<string, RowMark>>({});
  const [error, setError] = useState<string | null>(null);
  const [toastOpen, setToastOpen] = useState(false);
  const seeded = useRef(false);

  useEffect(() => {
    if (seeded.current || !register.isSuccess) return;
    const next: Record<string, RowMark> = {};
    for (const student of studentsFromRegister(register.data)) {
      next[student.id] = existingMark(register.data, student.id, date);
    }
    setMarks(next);
    seeded.current = true;
  }, [register.isSuccess, register.data, date]);

  const markedCount = useMemo(
    () => students.filter((student) => marks[student.id]?.status).length,
    [students, marks],
  );

  const save = useMutation({
    mutationFn: (body: BulkAttendanceUpsertBody) => attendanceApi.bulkUpsert(body),
    onSuccess: (data) => {
      void qc.invalidateQueries({ queryKey: ["attendance", "register"] });
      const partial = partialBulkFailureMessage(data);
      if (partial) {
        setError(partial);
        return;
      }
      setError(null);
      setToastOpen(true);
    },
    onError: (err) => {
      setError(formatApiError(err, "Save failed"));
    },
  });

  function markUnmarkedPresent() {
    setMarks((current) => {
      const next = { ...current };
      for (const student of students) {
        if (next[student.id]?.status) continue;
        next[student.id] = {
          status: "present",
          remarks: next[student.id]?.remarks ?? "",
        };
      }
      return next;
    });
  }

  function submit() {
    const entries = students.flatMap((student) => {
      const mark = marks[student.id];
      if (!mark?.status) return [];
      return [
        {
          student_id: student.id,
          status: mark.status,
          remarks: mark.remarks.trim(),
        },
      ];
    });
    if (!entries.length) {
      setError("Choose a status for at least one student.");
      return;
    }
    setError(null);
    save.mutate({
      class_level_id: assignment.class_level,
      arm_id: assignment.arm,
      term_id: assignment.term,
      date,
      entries,
    });
  }

  const ready = register.isSuccess && students.length > 0;

  return (
    <>
      <Card>
        <form
          onSubmit={(event) => {
            event.preventDefault();
            if (save.isPending || !ready) return;
            submit();
          }}
        >
          {register.isLoading ? (
            <CardBody>
              <p className="text-sm text-ink/70">Loading register…</p>
            </CardBody>
          ) : register.isError ? (
            <CardBody>
              <p className="text-sm text-danger" role="alert">
                {formatApiError(register.error, "Could not load the register.")}
              </p>
            </CardBody>
          ) : students.length === 0 ? (
            <CardBody>
              <p className="text-sm text-ink/80">
                No students are enrolled in this class for the term.
              </p>
            </CardBody>
          ) : (
            <CardBody className="space-y-3 p-0">
              {isWeekend(date) ? (
                <p className="px-5 pt-4 text-sm text-ink/70">
                  Weekend dates are not on the weekday grid. Marks you save
                  here are still stored.
                </p>
              ) : null}
              <Table>
                <THead>
                  <TR>
                    <TH>Student</TH>
                    <TH>Status</TH>
                    <TH>Remarks</TH>
                  </TR>
                </THead>
                <TBody>
                  {students.map((student) => {
                    const mark = marks[student.id] ?? { status: "", remarks: "" };
                    return (
                      <TR key={student.id}>
                        <TD className="min-w-40">
                          <span className="block">{student.name}</span>
                          {student.admission_number ? (
                            <span
                              className="block text-xs text-ink/60"
                              style={{ fontFamily: "var(--font-mono)" }}
                            >
                              {student.admission_number}
                            </span>
                          ) : null}
                        </TD>
                        <TD className="min-w-36">
                          <Select
                            aria-label={`${student.name} status`}
                            value={mark.status}
                            onChange={(event) => {
                              const status = event.target.value as
                                | AttendanceStatus
                                | "";
                              setMarks((current) => ({
                                ...current,
                                [student.id]: {
                                  status,
                                  remarks: current[student.id]?.remarks ?? "",
                                },
                              }));
                            }}
                            className="py-1.5 text-sm"
                          >
                            <option value="">—</option>
                            {STATUS_OPTIONS.map((option) => (
                              <option key={option.value} value={option.value}>
                                {option.label}
                              </option>
                            ))}
                          </Select>
                        </TD>
                        <TD className="min-w-40">
                          <Input
                            aria-label={`${student.name} remarks`}
                            value={mark.remarks}
                            placeholder="Optional"
                            onChange={(event) =>
                              setMarks((current) => ({
                                ...current,
                                [student.id]: {
                                  status: current[student.id]?.status ?? "",
                                  remarks: event.target.value,
                                },
                              }))
                            }
                            className="py-1.5 text-sm"
                          />
                        </TD>
                      </TR>
                    );
                  })}
                </TBody>
              </Table>
            </CardBody>
          )}
          <div className="flex flex-wrap items-center gap-3 border-t border-ink/15 px-5 py-4">
            <Button type="submit" disabled={save.isPending || !ready || markedCount === 0}>
              {save.isPending ? "Saving…" : "Save register"}
            </Button>
            <Button
              type="button"
              variant="secondary"
              size="sm"
              disabled={save.isPending || !ready}
              onClick={markUnmarkedPresent}
            >
              Mark unmarked present
            </Button>
            <p className="text-sm text-ink/70">
              {markedCount} of {students.length} marked. Students left as — are
              not changed.
            </p>
          </div>
          {error ? (
            <p className="px-5 pb-4 text-sm text-danger" role="alert">
              {error}
            </p>
          ) : null}
        </form>
      </Card>
      <Toast
        open={toastOpen}
        onClose={() => setToastOpen(false)}
        message="Attendance saved."
      />
    </>
  );
}

export default function TeacherAttendancePage() {
  const classes = useQuery({
    queryKey: ["academics", "my-classes"],
    queryFn: () => academicsApi.myClasses(),
  });
  const list = classes.data ?? [];
  const [classId, setClassId] = useState("");
  const [date, setDate] = useState(todayIso);
  const selected = list.find((item) => item.id === classId) ?? list[0];

  return (
    <div className="space-y-6">
      <PageHeader
        title="Attendance register"
        description="Daily register for a class you are form teacher of."
      />
      {classes.isLoading ? (
        <p className="text-sm text-ink/70">Loading your classes…</p>
      ) : null}
      {classes.isError ? (
        <p className="text-sm text-danger" role="alert">
          {formatApiError(classes.error, "Could not load classes.")}
        </p>
      ) : null}
      {!classes.isLoading && !classes.isError && list.length === 0 ? (
        <EmptyState
          headline="No form class assigned"
          body="When an admin assigns you as form teacher, the daily register shows up here."
        />
      ) : null}
      {selected ? (
        <>
          <Card>
            <CardBody className="grid gap-3 sm:grid-cols-2">
              <div>
                <Label htmlFor="attendance-class">Class</Label>
                <Select
                  id="attendance-class"
                  value={selected.id}
                  onChange={(event) => setClassId(event.target.value)}
                >
                  {list.map((item) => (
                    <option key={item.id} value={item.id}>
                      {classLabel(item)}
                    </option>
                  ))}
                </Select>
              </div>
              <div>
                <Label htmlFor="attendance-date">Date</Label>
                <Input
                  id="attendance-date"
                  type="date"
                  value={date}
                  onChange={(event) => setDate(event.target.value)}
                />
              </div>
            </CardBody>
          </Card>
          {date ? (
            <RegisterGrid
              key={`${selected.id}:${date}`}
              assignment={selected}
              date={date}
            />
          ) : (
            <p className="text-sm text-ink/70">Choose a date.</p>
          )}
        </>
      ) : null}
    </div>
  );
}
