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
import { academicsApi } from "@/lib/api/academics";
import { assessmentApi } from "@/lib/api/assessment";
import { ApiRequestError } from "@/lib/api/client";
import { mapDrfErrors } from "@/lib/api/errors";

export default function TeacherBroadsheetPage() {
  const assignments = useQuery({
    queryKey: ["academics", "my-assignments"],
    queryFn: () => academicsApi.myAssignments(),
  });
  const first = assignments.data?.[0];
  const [classLevel, setClassLevel] = useState("");
  const [arm, setArm] = useState("");
  const [term, setTerm] = useState("");
  const [subject, setSubject] = useState("");
  const [error, setError] = useState<string | null>(null);

  const effective = {
    class_level: classLevel || first?.class_level || "",
    arm: arm || first?.arm || "",
    term: term || first?.term || "",
    subject: subject || first?.subject,
  };

  const sheet = useQuery({
    queryKey: ["assessment", "broadsheet", effective],
    queryFn: () =>
      assessmentApi.broadsheet({
        class_level: effective.class_level,
        arm: effective.arm,
        term: effective.term,
        subject: effective.subject,
      }),
    enabled: Boolean(effective.class_level && effective.arm && effective.term),
  });

  const recompute = useMutation({
    mutationFn: () =>
      assessmentApi.recompute({
        class_level: effective.class_level,
        arm: effective.arm,
        term: effective.term,
        subject: effective.subject,
      }),
    onError: (err) => {
      setError(
        err instanceof ApiRequestError
          ? mapDrfErrors(err.data).form ?? err.message
          : "Recompute failed",
      );
    },
  });

  return (
    <div className="space-y-6">
      <PageHeader title="Broadsheet" description="Class results grid" />
      <Card>
        <CardBody className="grid gap-3 sm:grid-cols-4">
          {(
            [
              ["Class level", classLevel, setClassLevel],
              ["Arm", arm, setArm],
              ["Term", term, setTerm],
              ["Subject", subject, setSubject],
            ] as const
          ).map(([label, value, set]) => (
            <div key={label}>
              <Label>{label}</Label>
              <Input
                value={value}
                onChange={(e) => set(e.target.value)}
                placeholder="UUID"
                style={{ fontFamily: "var(--font-mono)" }}
              />
            </div>
          ))}
        </CardBody>
      </Card>
      <div className="flex gap-2">
        <Button
          size="sm"
          disabled={recompute.isPending}
          onClick={() => recompute.mutate()}
        >
          Recompute
        </Button>
      </div>
      {error ? <p className="text-sm text-danger">{error}</p> : null}
      <Card>
        <CardBody>
          {sheet.isLoading ? (
            <p className="text-sm text-ink/70">Loading…</p>
          ) : (
            <pre
              className="max-h-96 overflow-auto text-xs"
              style={{ fontFamily: "var(--font-mono)" }}
            >
              {JSON.stringify(sheet.data ?? {}, null, 2)}
            </pre>
          )}
        </CardBody>
      </Card>
    </div>
  );
}
