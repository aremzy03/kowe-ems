"use client";

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import {
  Button,
  Card,
  CardBody,
  Input,
  Label,
  PageHeader,
  Textarea,
} from "@/components/ui";
import { Toast } from "@/components/ui/client";
import { assessmentApi } from "@/lib/api/assessment";
import { ApiRequestError } from "@/lib/api/client";
import { mapDrfErrors } from "@/lib/api/errors";

export default function TeacherRemarksPage() {
  const [student, setStudent] = useState("");
  const [term, setTerm] = useState("");
  const [remark, setRemark] = useState("");
  const [toastOpen, setToastOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const save = useMutation({
    mutationFn: () =>
      assessmentApi.remarks({
        student,
        term,
        teacher_remark: remark,
      }),
    onSuccess: () => {
      setToastOpen(true);
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
    <div className="mx-auto max-w-lg space-y-6">
      <PageHeader title="Remarks" description="Teacher term remarks" />
      <Card>
        <CardBody className="space-y-3">
          <div>
            <Label>Student id</Label>
            <Input
              value={student}
              onChange={(e) => setStudent(e.target.value)}
              style={{ fontFamily: "var(--font-mono)" }}
            />
          </div>
          <div>
            <Label>Term id</Label>
            <Input
              value={term}
              onChange={(e) => setTerm(e.target.value)}
              style={{ fontFamily: "var(--font-mono)" }}
            />
          </div>
          <div>
            <Label>Remark</Label>
            <Textarea
              value={remark}
              onChange={(e) => setRemark(e.target.value)}
              placeholder="Write a short teacher remark…"
            />
          </div>
          {error ? <p className="text-sm text-danger">{error}</p> : null}
          <Button
            disabled={save.isPending || !student || !term}
            onClick={() => save.mutate()}
          >
            {save.isPending ? "Saving…" : "Save remark"}
          </Button>
        </CardBody>
      </Card>
      <Toast
        open={toastOpen}
        onClose={() => setToastOpen(false)}
        message="Remark saved."
      />
    </div>
  );
}
