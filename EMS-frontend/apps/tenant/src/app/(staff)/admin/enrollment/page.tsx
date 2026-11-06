"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Button,
  Card,
  CardBody,
  Input,
  Label,
  PageHeader,
  Table,
  TBody,
  TD,
  TH,
  THead,
  TR,
} from "@/components/ui";
import { academicsApi } from "@/lib/api/academics";
import { ApiRequestError } from "@/lib/api/client";
import { mapDrfErrors } from "@/lib/api/errors";

export default function AdminEnrollmentPage() {
  const qc = useQueryClient();
  const enrollments = useQuery({
    queryKey: ["academics", "enrollments"],
    queryFn: () => academicsApi.enrollments.list(),
  });
  const [student, setStudent] = useState("");
  const [term, setTerm] = useState("");
  const [classLevel, setClassLevel] = useState("");
  const [arm, setArm] = useState("");
  const [error, setError] = useState<string | null>(null);

  const create = useMutation({
    mutationFn: () =>
      academicsApi.enrollments.create({
        student,
        term,
        class_level: classLevel,
        arm,
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["academics", "enrollments"] });
      setError(null);
    },
    onError: (err) => {
      setError(
        err instanceof ApiRequestError
          ? mapDrfErrors(err.data).form ?? err.message
          : "Failed",
      );
    },
  });

  return (
    <div className="space-y-6">
      <PageHeader title="Enrollment" description="Term enrollments" />
      {error ? <p className="text-sm text-danger">{error}</p> : null}
      <Card>
        <CardBody className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
          {(
            [
              ["Student id", student, setStudent],
              ["Term id", term, setTerm],
              ["Class level id", classLevel, setClassLevel],
              ["Arm id", arm, setArm],
            ] as const
          ).map(([label, value, set]) => (
            <div key={label}>
              <Label>{label}</Label>
              <Input
                value={value}
                onChange={(e) => set(e.target.value)}
                style={{ fontFamily: "var(--font-mono)" }}
              />
            </div>
          ))}
          <div className="flex items-end">
            <Button
              size="sm"
              disabled={create.isPending || !student || !term}
              onClick={() => create.mutate()}
            >
              Enroll
            </Button>
          </div>
        </CardBody>
      </Card>
      <Card>
        <CardBody className="p-0">
          <Table>
            <THead>
              <TR>
                <TH>Student</TH>
                <TH>Term</TH>
                <TH>Class</TH>
                <TH>Arm</TH>
              </TR>
            </THead>
            <TBody>
              {(enrollments.data ?? []).map((e) => (
                <TR key={e.id}>
                  <TD style={{ fontFamily: "var(--font-mono)" }}>{e.student}</TD>
                  <TD style={{ fontFamily: "var(--font-mono)" }}>{e.term}</TD>
                  <TD style={{ fontFamily: "var(--font-mono)" }}>{e.class_level}</TD>
                  <TD style={{ fontFamily: "var(--font-mono)" }}>{e.arm}</TD>
                </TR>
              ))}
            </TBody>
          </Table>
        </CardBody>
      </Card>
    </div>
  );
}
