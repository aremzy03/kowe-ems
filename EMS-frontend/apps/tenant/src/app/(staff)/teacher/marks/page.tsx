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
import { assessmentApi } from "@/lib/api/assessment";
import { ApiRequestError } from "@/lib/api/client";
import { mapDrfErrors } from "@/lib/api/errors";

export default function TeacherMarksPage() {
  const assignments = useQuery({
    queryKey: ["academics", "my-assignments"],
    queryFn: () => academicsApi.myAssignments(),
  });
  const [payload, setPayload] = useState("{\n  \"scores\": []\n}");
  const [toastOpen, setToastOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const save = useMutation({
    mutationFn: () => assessmentApi.bulkUpsertScores(JSON.parse(payload)),
    onSuccess: () => {
      setToastOpen(true);
      setError(null);
    },
    onError: (err) => {
      setError(
        err instanceof ApiRequestError
          ? mapDrfErrors(err.data).form ?? err.message
          : err instanceof Error
            ? err.message
            : "Save failed",
      );
    },
  });

  return (
    <div className="space-y-6">
      <PageHeader
        title="Mark entry"
        description="Bulk upsert scores (idempotent). Match Bruno Assessment payload."
      />
      <Card>
        <CardBody className="space-y-2 text-sm text-ink/75">
          <p>Your assignments:</p>
          <ul className="list-disc pl-5">
            {(assignments.data ?? []).map((a) => (
              <li key={a.id} style={{ fontFamily: "var(--font-mono)" }}>
                {a.subject} · {a.class_level} · {a.term}
              </li>
            ))}
          </ul>
        </CardBody>
      </Card>
      <Card>
        <CardBody className="space-y-3">
          <Label htmlFor="scores-json">Bulk upsert JSON</Label>
          <textarea
            id="scores-json"
            className="min-h-48 w-full rounded-[var(--radius-nb-sm)] border border-ink bg-paper p-3 text-sm"
            style={{ fontFamily: "var(--font-mono)" }}
            value={payload}
            onChange={(e) => setPayload(e.target.value)}
          />
          {error ? <p className="text-sm text-danger">{error}</p> : null}
          <Button
            disabled={save.isPending}
            onClick={() => save.mutate()}
          >
            {save.isPending ? "Saving…" : "Submit scores"}
          </Button>
        </CardBody>
      </Card>
      <Toast
        open={toastOpen}
        onClose={() => setToastOpen(false)}
        message="Scores upserted."
      />
    </div>
  );
}
