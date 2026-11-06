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
} from "@/components/ui";
import { financeApi } from "@/lib/api/finance";
import { ApiRequestError } from "@/lib/api/client";
import { mapDrfErrors } from "@/lib/api/errors";

export default function GenerateInvoicesPage() {
  const [classLevel, setClassLevel] = useState("");
  const [term, setTerm] = useState("");
  const [arm, setArm] = useState("");
  const [result, setResult] = useState<string>("");
  const [error, setError] = useState<string | null>(null);

  const generate = useMutation({
    mutationFn: () =>
      financeApi.generateInvoices({
        class_level: classLevel,
        term,
        ...(arm ? { arm } : {}),
      }),
    onSuccess: (data) => {
      setResult(JSON.stringify(data, null, 2));
      setError(null);
    },
    onError: (err) => {
      setError(
        err instanceof ApiRequestError
          ? mapDrfErrors(err.data).form ?? err.message
          : "Generate failed",
      );
    },
  });

  return (
    <div className="mx-auto max-w-lg space-y-6">
      <PageHeader
        title="Generate invoices"
        description="Create invoices for a class/term (idempotent)"
      />
      <Card>
        <CardBody className="space-y-3">
          <div>
            <Label>Class level id</Label>
            <Input
              value={classLevel}
              onChange={(e) => setClassLevel(e.target.value)}
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
            <Label>Arm id (optional)</Label>
            <Input
              value={arm}
              onChange={(e) => setArm(e.target.value)}
              style={{ fontFamily: "var(--font-mono)" }}
            />
          </div>
          {error ? <p className="text-sm text-danger">{error}</p> : null}
          <Button
            disabled={generate.isPending || !classLevel || !term}
            onClick={() => generate.mutate()}
          >
            {generate.isPending ? "Generating…" : "Generate"}
          </Button>
          {result ? (
            <pre
              className="overflow-auto rounded border border-ink/20 bg-paper p-3 text-xs"
              style={{ fontFamily: "var(--font-mono)" }}
            >
              {result}
            </pre>
          ) : null}
        </CardBody>
      </Card>
    </div>
  );
}
