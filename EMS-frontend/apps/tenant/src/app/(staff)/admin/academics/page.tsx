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
  Select,
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
  const [sessionStart, setSessionStart] = useState("2026-09-08");
  const [sessionEnd, setSessionEnd] = useState("2027-07-16");
  const [subjectName, setSubjectName] = useState("");
  const [subjectCode, setSubjectCode] = useState("");
  const [termSession, setTermSession] = useState("");
  const [termName, setTermName] = useState("1st");
  const [termStart, setTermStart] = useState("2026-09-08");
  const [termEnd, setTermEnd] = useState("2026-12-11");
  const [schoolDays, setSchoolDays] = useState("65");
  const [levelName, setLevelName] = useState("");
  const [armLevel, setArmLevel] = useState("");
  const [armName, setArmName] = useState("");
  const [error, setError] = useState<string | null>(null);

  const createSession = useMutation({
    mutationFn: () =>
      academicsApi.sessions.create({
        name: sessionName,
        start_date: sessionStart,
        end_date: sessionEnd,
      }),
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

  const createTerm = useMutation({
    mutationFn: () =>
      academicsApi.terms.create({
        session: termSession,
        name: termName,
        start_date: termStart,
        end_date: termEnd,
        total_school_days: Number(schoolDays),
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["academics", "terms"] });
    },
    onError: (err) => {
      setError(
        err instanceof ApiRequestError
          ? mapDrfErrors(err.data).form ?? err.message
          : "Failed",
      );
    },
  });

  const createLevel = useMutation({
    mutationFn: () => academicsApi.classLevels.create({ name: levelName }),
    onSuccess: () => {
      setLevelName("");
      void qc.invalidateQueries({ queryKey: ["academics", "class-levels"] });
    },
    onError: (err) => {
      setError(
        err instanceof ApiRequestError
          ? mapDrfErrors(err.data).form ?? err.message
          : "Failed",
      );
    },
  });

  const createArm = useMutation({
    mutationFn: () => academicsApi.arms.create({ class_level: armLevel, name: armName }),
    onSuccess: () => {
      setArmName("");
      void qc.invalidateQueries({ queryKey: ["academics", "arms"] });
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
            <div className="grid gap-2 sm:grid-cols-2">
              <Input
                value={sessionName}
                onChange={(e) => setSessionName(e.target.value)}
                placeholder="2026/2027"
                aria-label="Session name"
              />
              <Button
                size="sm"
                disabled={!sessionName || !sessionStart || !sessionEnd || createSession.isPending}
                onClick={() => createSession.mutate()}
              >
                Add
              </Button>
              <Input
                type="date"
                value={sessionStart}
                onChange={(e) => setSessionStart(e.target.value)}
                aria-label="Session start date"
              />
              <Input
                type="date"
                value={sessionEnd}
                onChange={(e) => setSessionEnd(e.target.value)}
                aria-label="Session end date"
              />
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
          <CardBody className="space-y-3">
            <div className="grid gap-2 sm:grid-cols-2">
              <Select
                aria-label="Term session"
                value={termSession}
                onChange={(e) => setTermSession(e.target.value)}
              >
                <option value="">Session</option>
                {(sessions.data ?? []).map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name}
                  </option>
                ))}
              </Select>
              <Select
                aria-label="Term name"
                value={termName}
                onChange={(e) => setTermName(e.target.value)}
              >
                <option value="1st">1st</option>
                <option value="2nd">2nd</option>
                <option value="3rd">3rd</option>
              </Select>
              <Input
                type="date"
                aria-label="Term start date"
                value={termStart}
                onChange={(e) => setTermStart(e.target.value)}
              />
              <Input
                type="date"
                aria-label="Term end date"
                value={termEnd}
                onChange={(e) => setTermEnd(e.target.value)}
              />
              <Input
                aria-label="School days"
                value={schoolDays}
                onChange={(e) => setSchoolDays(e.target.value)}
              />
              <Button
                size="sm"
                disabled={!termSession || createTerm.isPending}
                onClick={() => createTerm.mutate()}
              >
                Add term
              </Button>
            </div>
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
          <CardBody className="space-y-3 text-sm">
            <div className="flex gap-2">
              <Input
                aria-label="Class level name"
                value={levelName}
                onChange={(e) => setLevelName(e.target.value)}
                placeholder="JSS1"
              />
              <Button
                size="sm"
                disabled={!levelName || createLevel.isPending}
                onClick={() => createLevel.mutate()}
              >
                Add level
              </Button>
            </div>
            <div className="flex gap-2">
              <Select
                aria-label="Arm class level"
                value={armLevel}
                onChange={(e) => setArmLevel(e.target.value)}
              >
                <option value="">Class level</option>
                {(levels.data ?? []).map((level) => (
                  <option key={level.id} value={level.id}>
                    {level.name}
                  </option>
                ))}
              </Select>
              <Input
                aria-label="Arm name"
                value={armName}
                onChange={(e) => setArmName(e.target.value)}
                placeholder="A"
              />
              <Button
                size="sm"
                disabled={!armLevel || !armName || createArm.isPending}
                onClick={() => createArm.mutate()}
              >
                Add arm
              </Button>
            </div>
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
