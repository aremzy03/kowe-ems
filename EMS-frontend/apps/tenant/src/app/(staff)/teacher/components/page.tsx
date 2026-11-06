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
  Table,
  TBody,
  TD,
  TH,
  THead,
  TR,
} from "@/components/ui";
import { academicsApi } from "@/lib/api/academics";
import { assessmentApi } from "@/lib/api/assessment";
import { ApiRequestError } from "@/lib/api/client";
import { mapDrfErrors } from "@/lib/api/errors";

export default function TeacherComponentsPage() {
  const assignments = useQuery({
    queryKey: ["academics", "my-assignments"],
    queryFn: () => academicsApi.myAssignments(),
  });
  const first = assignments.data?.[0];
  const components = useQuery({
    queryKey: [
      "assessment",
      "my-components",
      first?.subject,
      first?.class_level,
      first?.term,
    ],
    queryFn: () =>
      assessmentApi.myComponents({
        subject: first!.subject,
        class_level: first!.class_level,
        term: first!.term,
      }),
    enabled: Boolean(first),
  });

  const [schemeJson, setSchemeJson] = useState("{}");
  const [error, setError] = useState<string | null>(null);

  const setScheme = useMutation({
    mutationFn: () => assessmentApi.setScheme(JSON.parse(schemeJson)),
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
      <PageHeader
        title="Assessment components"
        description="Scheme for your assigned subjects"
      />
      <Card>
        <CardBody className="p-0">
          <Table>
            <THead>
              <TR>
                <TH>Name</TH>
                <TH>Weight</TH>
                <TH>Id</TH>
              </TR>
            </THead>
            <TBody>
              {(components.data ?? []).map((c) => (
                <TR key={c.id}>
                  <TD>{c.name}</TD>
                  <TD style={{ fontFamily: "var(--font-mono)" }}>{String(c.weight)}</TD>
                  <TD className="text-xs" style={{ fontFamily: "var(--font-mono)" }}>
                    {c.id}
                  </TD>
                </TR>
              ))}
            </TBody>
          </Table>
        </CardBody>
      </Card>
      <Card>
        <CardBody className="space-y-3">
          <Label>Set scheme JSON (admin/teacher)</Label>
          <Input
            value={schemeJson}
            onChange={(e) => setSchemeJson(e.target.value)}
            style={{ fontFamily: "var(--font-mono)" }}
          />
          {error ? <p className="text-sm text-danger">{error}</p> : null}
          <Button
            size="sm"
            disabled={setScheme.isPending}
            onClick={() => setScheme.mutate()}
          >
            Apply set-scheme
          </Button>
        </CardBody>
      </Card>
    </div>
  );
}
