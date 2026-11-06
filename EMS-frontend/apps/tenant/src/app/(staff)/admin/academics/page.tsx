"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Button,
  Card,
  CardBody,
  CardHeader,
  CardTitle,
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

export default function AdminAcademicsPage() {
  const qc = useQueryClient();
  const sessions = useQuery({
    queryKey: ["academics", "sessions"],
    queryFn: () => academicsApi.sessions.list(),
  });
  const terms = useQuery({
    queryKey: ["academics", "terms"],
    queryFn: () => academicsApi.terms.list(),
  });
  const levels = useQuery({
    queryKey: ["academics", "class-levels"],
    queryFn: () => academicsApi.classLevels.list(),
  });
  const arms = useQuery({
    queryKey: ["academics", "arms"],
    queryFn: () => academicsApi.arms.list(),
  });
  const subjects = useQuery({
    queryKey: ["academics", "subjects"],
    queryFn: () => academicsApi.subjects.list(),
  });

  const [sessionName, setSessionName] = useState("");
  const [subjectName, setSubjectName] = useState("");
  const [subjectCode, setSubjectCode] = useState("");
  const [error, setError] = useState<string | null>(null);

  const createSession = useMutation({
    mutationFn: () => academicsApi.sessions.create({ name: sessionName }),
    onSuccess: () => {
      setSessionName("");
      void qc.invalidateQueries({ queryKey: ["academics", "sessions"] });
    },
    onError: (err) => {
      setError(
        err instanceof ApiRequestError
          ? mapDrfErrors(err.data).form ?? err.message
          : "Failed",
      );
    },
  });

  const createSubject = useMutation({
    mutationFn: () =>
      academicsApi.subjects.create({ name: subjectName, code: subjectCode }),
    onSuccess: () => {
      setSubjectName("");
      setSubjectCode("");
      void qc.invalidateQueries({ queryKey: ["academics", "subjects"] });
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
      <PageHeader
        title="Academics"
        description="Sessions, terms, classes, and subjects"
      />
      {error ? <p className="text-sm text-danger">{error}</p> : null}

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Sessions</CardTitle>
          </CardHeader>
          <CardBody className="space-y-3">
            <div className="flex gap-2">
              <Input
                value={sessionName}
                onChange={(e) => setSessionName(e.target.value)}
                placeholder="2025/2026"
              />
              <Button
                size="sm"
                disabled={!sessionName || createSession.isPending}
                onClick={() => createSession.mutate()}
              >
                Add
              </Button>
            </div>
            <Table>
              <THead>
                <TR>
                  <TH>Name</TH>
                  <TH>Id</TH>
                </TR>
              </THead>
              <TBody>
                {(sessions.data ?? []).map((s) => (
                  <TR key={s.id}>
                    <TD>{s.name}</TD>
                    <TD className="text-xs" style={{ fontFamily: "var(--font-mono)" }}>
                      {s.id}
                    </TD>
                  </TR>
                ))}
              </TBody>
            </Table>
          </CardBody>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Terms ({terms.data?.length ?? 0})</CardTitle>
          </CardHeader>
          <CardBody>
            <Table>
              <THead>
                <TR>
                  <TH>Name</TH>
                  <TH>Session</TH>
                </TR>
              </THead>
              <TBody>
                {(terms.data ?? []).map((t) => (
                  <TR key={t.id}>
                    <TD>{t.name}</TD>
                    <TD className="text-xs" style={{ fontFamily: "var(--font-mono)" }}>
                      {t.session}
                    </TD>
                  </TR>
                ))}
              </TBody>
            </Table>
          </CardBody>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>
              Levels / Arms ({levels.data?.length ?? 0} / {arms.data?.length ?? 0})
            </CardTitle>
          </CardHeader>
          <CardBody className="space-y-2 text-sm">
            <p>Class levels: {(levels.data ?? []).map((l) => l.name).join(", ") || "—"}</p>
            <p>Arms: {(arms.data ?? []).map((a) => a.name).join(", ") || "—"}</p>
          </CardBody>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Subjects</CardTitle>
          </CardHeader>
          <CardBody className="space-y-3">
            <div className="grid gap-2 sm:grid-cols-3">
              <div>
                <Label htmlFor="sub-code">Code</Label>
                <Input
                  id="sub-code"
                  value={subjectCode}
                  onChange={(e) => setSubjectCode(e.target.value)}
                />
              </div>
              <div className="sm:col-span-2">
                <Label htmlFor="sub-name">Name</Label>
                <Input
                  id="sub-name"
                  value={subjectName}
                  onChange={(e) => setSubjectName(e.target.value)}
                />
              </div>
            </div>
            <Button
              size="sm"
              disabled={!subjectName || createSubject.isPending}
              onClick={() => createSubject.mutate()}
            >
              Add subject
            </Button>
            <Table>
              <THead>
                <TR>
                  <TH>Code</TH>
                  <TH>Name</TH>
                </TR>
              </THead>
              <TBody>
                {(subjects.data ?? []).map((s) => (
                  <TR key={s.id}>
                    <TD style={{ fontFamily: "var(--font-mono)" }}>{s.code}</TD>
                    <TD>{s.name}</TD>
                  </TR>
                ))}
              </TBody>
            </Table>
          </CardBody>
        </Card>
      </div>
    </div>
  );
}
