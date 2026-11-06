"use client";

import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import {
  Button,
  Card,
  CardBody,
  Input,
  Label,
  PageHeader,
} from "@/components/ui";
import { Toast } from "@/components/ui/client";
import { academicsApi } from "@/lib/api/academics";
import { attendanceApi } from "@/lib/api/attendance";
import { ApiRequestError } from "@/lib/api/client";
import { mapDrfErrors } from "@/lib/api/errors";

export default function TeacherAttendancePage() {
  const classes = useQuery({
    queryKey: ["academics", "my-classes"],
    queryFn: () => academicsApi.myClasses(),
  });
  const first = classes.data?.[0];
  const [month, setMonth] = useState(() => {
    const d = new Date();
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
  });
  const [date, setDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [payload, setPayload] = useState("");
  const [toastOpen, setToastOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const register = useQuery({
    queryKey: [
      "attendance",
      "register",
      first?.class_level,
      first?.arm,
      first?.term,
      month,
    ],
    queryFn: () =>
      attendanceApi.register({
        class_level: first!.class_level,
        arm: first!.arm,
        term: first!.term,
        month,
      }),
    enabled: Boolean(first),
  });

  const save = useMutation({
    mutationFn: () => {
      const body = payload
        ? JSON.parse(payload)
        : {
            class_level_id: first?.class_level,
            arm_id: first?.arm,
            term_id: first?.term,
            date,
            entries: [],
          };
      return attendanceApi.bulkUpsert(body);
    },
    onSuccess: () => {
      setToastOpen(true);
      setError(null);
    },
    onError: (err) => {
      setError(
        err instanceof ApiRequestError
          ? mapDrfErrors(err.data).form ?? err.message
          : "Save failed",
      );
    },
  });

  return (
    <div className="space-y-6">
      <PageHeader
        title="Attendance register"
        description="Form-teacher daily register (bulk upsert)"
      />
      <Card>
        <CardBody className="grid gap-3 sm:grid-cols-3">
          <div>
            <Label>Month</Label>
            <Input value={month} onChange={(e) => setMonth(e.target.value)} />
          </div>
          <div>
            <Label>Date</Label>
            <Input value={date} onChange={(e) => setDate(e.target.value)} />
          </div>
          <div className="flex items-end">
            <p className="text-sm text-ink/70">
              Classes: {classes.data?.length ?? 0}
            </p>
          </div>
        </CardBody>
      </Card>
      <Card>
        <CardBody>
          {register.isLoading ? (
            <p className="text-sm text-ink/70">Loading register…</p>
          ) : (
            <pre
              className="max-h-64 overflow-auto text-xs"
              style={{ fontFamily: "var(--font-mono)" }}
            >
              {JSON.stringify(register.data ?? {}, null, 2)}
            </pre>
          )}
        </CardBody>
      </Card>
      <Card>
        <CardBody className="space-y-3">
          <Label>Bulk upsert JSON (optional override)</Label>
          <textarea
            className="min-h-32 w-full rounded-[var(--radius-nb-sm)] border border-ink bg-paper p-3 text-sm"
            style={{ fontFamily: "var(--font-mono)" }}
            value={payload}
            onChange={(e) => setPayload(e.target.value)}
            placeholder='{"class_level_id":"...","arm_id":"...","term_id":"...","date":"YYYY-MM-DD","entries":[{"student_id":"...","status":"present"}]}'
          />
          {error ? <p className="text-sm text-danger">{error}</p> : null}
          <Button disabled={save.isPending} onClick={() => save.mutate()}>
            {save.isPending ? "Saving…" : "Save register"}
          </Button>
        </CardBody>
      </Card>
      <Toast
        open={toastOpen}
        onClose={() => setToastOpen(false)}
        message="Attendance saved."
      />
    </div>
  );
}
