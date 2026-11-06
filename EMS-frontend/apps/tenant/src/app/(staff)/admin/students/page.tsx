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

export default function AdminStudentsPage() {
  const qc = useQueryClient();
  const students = useQuery({
    queryKey: ["academics", "students"],
    queryFn: () => academicsApi.students.list(),
  });
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [admission, setAdmission] = useState("");
  const [error, setError] = useState<string | null>(null);

  const create = useMutation({
    mutationFn: () =>
      academicsApi.students.create({
        first_name: firstName,
        last_name: lastName,
        admission_number: admission,
      }),
    onSuccess: () => {
      setFirstName("");
      setLastName("");
      setAdmission("");
      void qc.invalidateQueries({ queryKey: ["academics", "students"] });
    },
    onError: (err) => {
      setError(
        err instanceof ApiRequestError
          ? mapDrfErrors(err.data).form ?? err.message
          : "Create failed",
      );
    },
  });

  return (
    <div className="space-y-6">
      <PageHeader title="Students" description="Student directory" />
      {error ? <p className="text-sm text-danger">{error}</p> : null}
      <Card>
        <CardBody className="grid gap-3 sm:grid-cols-4">
          <div>
            <Label htmlFor="fn">First name</Label>
            <Input id="fn" value={firstName} onChange={(e) => setFirstName(e.target.value)} />
          </div>
          <div>
            <Label htmlFor="ln">Last name</Label>
            <Input id="ln" value={lastName} onChange={(e) => setLastName(e.target.value)} />
          </div>
          <div>
            <Label htmlFor="adm">Admission #</Label>
            <Input id="adm" value={admission} onChange={(e) => setAdmission(e.target.value)} />
          </div>
          <div className="flex items-end">
            <Button
              size="sm"
              disabled={create.isPending || !firstName}
              onClick={() => create.mutate()}
            >
              Add student
            </Button>
          </div>
        </CardBody>
      </Card>
      <Card>
        <CardBody className="p-0">
          {students.isLoading ? (
            <p className="p-4 text-sm text-ink/70">Loading…</p>
          ) : (
            <Table>
              <THead>
                <TR>
                  <TH>Name</TH>
                  <TH>Admission</TH>
                  <TH>Id</TH>
                </TR>
              </THead>
              <TBody>
                {(students.data ?? []).map((s) => (
                  <TR key={s.id}>
                    <TD>
                      {s.full_name ||
                        [s.first_name, s.last_name].filter(Boolean).join(" ") ||
                        "—"}
                    </TD>
                    <TD style={{ fontFamily: "var(--font-mono)" }}>
                      {s.admission_number ?? "—"}
                    </TD>
                    <TD className="text-xs" style={{ fontFamily: "var(--font-mono)" }}>
                      {s.id}
                    </TD>
                  </TR>
                ))}
              </TBody>
            </Table>
          )}
        </CardBody>
      </Card>
    </div>
  );
}
