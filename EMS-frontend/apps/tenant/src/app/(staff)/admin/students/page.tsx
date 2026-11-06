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
  Select,
  Table,
  TBody,
  TD,
  TH,
  THead,
  TR,
} from "@/components/ui";
import { academicsApi, type Student } from "@/lib/api/academics";
import { ApiRequestError } from "@/lib/api/client";
import { mapDrfErrors } from "@/lib/api/errors";

function studentName(s: Pick<Student, "full_name" | "first_name" | "last_name">) {
  return s.full_name || [s.first_name, s.last_name].filter(Boolean).join(" ");
}

export default function AdminStudentsPage() {
  const qc = useQueryClient();
  const students = useQuery({
    queryKey: ["academics", "students"],
    queryFn: () => academicsApi.students.list(),
  });
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [dob, setDob] = useState("2015-04-12");
  const [gender, setGender] = useState("female");
  const [admission, setAdmission] = useState("");
  const [admissionDate, setAdmissionDate] = useState("2026-09-08");
  const [error, setError] = useState<string | null>(null);
  const [created, setCreated] = useState<Student | null>(null);
  const [copiedKey, setCopiedKey] = useState<string | null>(null);

  async function copyCode(code: string, key: string) {
    try {
      await navigator.clipboard.writeText(code);
      setError(null);
      setCopiedKey(key);
    } catch {
      setError("Could not copy the linking code.");
    }
  }

  const create = useMutation({
    mutationFn: () =>
      academicsApi.students.create({
        first_name: firstName,
        last_name: lastName,
        date_of_birth: dob,
        gender,
        admission_number: admission,
        admission_date: admissionDate,
      }),
    onSuccess: (student) => {
      setFirstName("");
      setLastName("");
      setAdmission("");
      setError(null);
      setCreated(student);
      setCopiedKey(null);
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
      <PageHeader
        title="Students"
        description="Admission numbers and class placement"
      />
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
            <Label htmlFor="dob">Date of birth</Label>
            <Input id="dob" type="date" value={dob} onChange={(e) => setDob(e.target.value)} />
          </div>
          <div>
            <Label htmlFor="gender">Gender</Label>
            <Select id="gender" value={gender} onChange={(e) => setGender(e.target.value)}>
              <option value="female">Female</option>
              <option value="male">Male</option>
              <option value="other">Other</option>
            </Select>
          </div>
          <div>
            <Label htmlFor="adm">Admission #</Label>
            <Input id="adm" value={admission} onChange={(e) => setAdmission(e.target.value)} />
          </div>
          <div>
            <Label htmlFor="adm-date">Admission date</Label>
            <Input
              id="adm-date"
              type="date"
              value={admissionDate}
              onChange={(e) => setAdmissionDate(e.target.value)}
            />
          </div>
          <div className="flex items-end">
            <Button
              size="sm"
              disabled={create.isPending || !firstName || !lastName || !admission}
              onClick={() => create.mutate()}
            >
              Add student
            </Button>
          </div>
          {created?.linking_code ? (
            <div className="flex flex-wrap items-center gap-3 border-t border-ink/15 pt-3 sm:col-span-4">
              <p className="text-sm text-ink/80">
                Linking code for {studentName(created) || "this student"}. The parent enters it at{" "}
                <span style={{ fontFamily: "var(--font-mono)" }}>/link-student</span>.
              </p>
              <span className="text-lg tracking-wide" style={{ fontFamily: "var(--font-mono)" }}>
                {created.linking_code}
              </span>
              <Button
                variant="secondary"
                size="sm"
                onClick={() => void copyCode(created.linking_code!, "created")}
              >
                {copiedKey === "created" ? "Copied" : "Copy"}
              </Button>
            </div>
          ) : null}
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
                  <TH>Linking code</TH>
                  <TH>Id</TH>
                </TR>
              </THead>
              <TBody>
                {(students.data ?? []).map((s) => (
                  <TR key={s.id}>
                    <TD>{studentName(s) || "—"}</TD>
                    <TD style={{ fontFamily: "var(--font-mono)" }}>
                      {s.admission_number ?? "—"}
                    </TD>
                    <TD>
                      {s.linking_code ? (
                        <span className="inline-flex items-center gap-2">
                          <span style={{ fontFamily: "var(--font-mono)" }}>{s.linking_code}</span>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => void copyCode(s.linking_code!, s.id)}
                          >
                            {copiedKey === s.id ? "Copied" : "Copy"}
                          </Button>
                        </span>
                      ) : (
                        <span className="text-ink/60">Used</span>
                      )}
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
