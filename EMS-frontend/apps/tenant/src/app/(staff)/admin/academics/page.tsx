"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Badge,
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
import { ConfirmDeleteModal } from "@/components/ui/client";
import {
  academicsApi,
  type Arm,
  type ClassLevel,
  type Session,
  type Subject,
  type Term,
} from "@/lib/api/academics";
import { formatApiError } from "@/lib/api/errors";

type DeleteKind = "session" | "term" | "level" | "arm" | "subject";

type PendingDelete = {
  kind: DeleteKind;
  id: string;
  label: string;
};

const TERM_NAMES = ["1st", "2nd", "3rd"] as const;

function sessionLabel(session: Session) {
  return session.name || "Session";
}

function termLabel(term: Term) {
  return [term.session_name, term.name].filter(Boolean).join(" · ") || term.name;
}

function levelLabel(level: ClassLevel) {
  return level.name || "Class level";
}

function armLabel(arm: Arm, levels: ClassLevel[]) {
  const level = levels.find((l) => l.id === arm.class_level);
  return level ? `${level.name}${arm.name}` : arm.name;
}

function subjectLabel(subject: Subject) {
  return subject.code ? `${subject.code} — ${subject.name}` : subject.name;
}

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

  const [editingSessionId, setEditingSessionId] = useState<string | null>(null);
  const [editSessionName, setEditSessionName] = useState("");
  const [editSessionStart, setEditSessionStart] = useState("");
  const [editSessionEnd, setEditSessionEnd] = useState("");

  const [editingTermId, setEditingTermId] = useState<string | null>(null);
  const [editTermSession, setEditTermSession] = useState("");
  const [editTermName, setEditTermName] = useState("1st");
  const [editTermStart, setEditTermStart] = useState("");
  const [editTermEnd, setEditTermEnd] = useState("");
  const [editSchoolDays, setEditSchoolDays] = useState("");

  const [editingLevelId, setEditingLevelId] = useState<string | null>(null);
  const [editLevelName, setEditLevelName] = useState("");

  const [editingArmId, setEditingArmId] = useState<string | null>(null);
  const [editArmLevel, setEditArmLevel] = useState("");
  const [editArmName, setEditArmName] = useState("");

  const [editingSubjectId, setEditingSubjectId] = useState<string | null>(null);
  const [editSubjectCode, setEditSubjectCode] = useState("");
  const [editSubjectName, setEditSubjectName] = useState("");

  const [pendingDelete, setPendingDelete] = useState<PendingDelete | null>(null);

  function invalidateAcademics() {
    void qc.invalidateQueries({ queryKey: ["academics"] });
  }

  function startEditSession(s: Session) {
    setEditingSessionId(s.id);
    setEditSessionName(s.name);
    setEditSessionStart(s.start_date ?? "");
    setEditSessionEnd(s.end_date ?? "");
  }

  function startEditTerm(t: Term) {
    setEditingTermId(t.id);
    setEditTermSession(t.session);
    setEditTermName(t.name);
    setEditTermStart(t.start_date ?? "");
    setEditTermEnd(t.end_date ?? "");
    setEditSchoolDays(
      t.total_school_days != null ? String(t.total_school_days) : "",
    );
  }

  function startEditLevel(level: ClassLevel) {
    setEditingLevelId(level.id);
    setEditLevelName(level.name);
  }

  function startEditArm(arm: Arm) {
    setEditingArmId(arm.id);
    setEditArmLevel(arm.class_level);
    setEditArmName(arm.name);
  }

  function startEditSubject(subject: Subject) {
    setEditingSubjectId(subject.id);
    setEditSubjectCode(subject.code ?? "");
    setEditSubjectName(subject.name);
  }

  const createSession = useMutation({
    mutationFn: () =>
      academicsApi.sessions.create({
        name: sessionName,
        start_date: sessionStart,
        end_date: sessionEnd,
      }),
    onSuccess: () => {
      setSessionName("");
      setError(null);
      invalidateAcademics();
    },
    onError: (err) => setError(formatApiError(err, "Could not create session")),
  });

  const updateSession = useMutation({
    mutationFn: ({ id, body }: { id: string; body: Partial<Session> }) =>
      academicsApi.sessions.update(id, body),
    onSuccess: () => {
      setEditingSessionId(null);
      setError(null);
      invalidateAcademics();
    },
    onError: (err) => setError(formatApiError(err, "Could not update session")),
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
      setError(null);
      invalidateAcademics();
    },
    onError: (err) => setError(formatApiError(err, "Could not create term")),
  });

  const updateTerm = useMutation({
    mutationFn: ({ id, body }: { id: string; body: Partial<Term> }) =>
      academicsApi.terms.update(id, body),
    onSuccess: () => {
      setEditingTermId(null);
      setError(null);
      invalidateAcademics();
    },
    onError: (err) => setError(formatApiError(err, "Could not update term")),
  });

  const createLevel = useMutation({
    mutationFn: () => academicsApi.classLevels.create({ name: levelName }),
    onSuccess: () => {
      setLevelName("");
      setError(null);
      invalidateAcademics();
    },
    onError: (err) => setError(formatApiError(err, "Could not create class level")),
  });

  const updateLevel = useMutation({
    mutationFn: ({ id, body }: { id: string; body: Partial<ClassLevel> }) =>
      academicsApi.classLevels.update(id, body),
    onSuccess: () => {
      setEditingLevelId(null);
      setError(null);
      invalidateAcademics();
    },
    onError: (err) => setError(formatApiError(err, "Could not update class level")),
  });

  const createArm = useMutation({
    mutationFn: () => academicsApi.arms.create({ class_level: armLevel, name: armName }),
    onSuccess: () => {
      setArmName("");
      setError(null);
      invalidateAcademics();
    },
    onError: (err) => setError(formatApiError(err, "Could not create arm")),
  });

  const updateArm = useMutation({
    mutationFn: ({ id, body }: { id: string; body: Partial<Arm> }) =>
      academicsApi.arms.update(id, body),
    onSuccess: () => {
      setEditingArmId(null);
      setError(null);
      invalidateAcademics();
    },
    onError: (err) => setError(formatApiError(err, "Could not update arm")),
  });

  const createSubject = useMutation({
    mutationFn: () =>
      academicsApi.subjects.create({ name: subjectName, code: subjectCode }),
    onSuccess: () => {
      setSubjectName("");
      setSubjectCode("");
      setError(null);
      invalidateAcademics();
    },
    onError: (err) => setError(formatApiError(err, "Could not create subject")),
  });

  const updateSubject = useMutation({
    mutationFn: ({ id, body }: { id: string; body: Partial<Subject> }) =>
      academicsApi.subjects.update(id, body),
    onSuccess: () => {
      setEditingSubjectId(null);
      setError(null);
      invalidateAcademics();
    },
    onError: (err) => setError(formatApiError(err, "Could not update subject")),
  });

  const removeMutation = useMutation({
    mutationFn: async (target: PendingDelete) => {
      if (target.kind === "session") return academicsApi.sessions.remove(target.id);
      if (target.kind === "term") return academicsApi.terms.remove(target.id);
      if (target.kind === "level") return academicsApi.classLevels.remove(target.id);
      if (target.kind === "arm") return academicsApi.arms.remove(target.id);
      return academicsApi.subjects.remove(target.id);
    },
    onSuccess: (_data, target) => {
      setPendingDelete(null);
      setError(null);
      if (target.kind === "session") {
        setEditingSessionId((current) => (current === target.id ? null : current));
      } else if (target.kind === "term") {
        setEditingTermId((current) => (current === target.id ? null : current));
      } else if (target.kind === "level") {
        setEditingLevelId((current) => (current === target.id ? null : current));
      } else if (target.kind === "arm") {
        setEditingArmId((current) => (current === target.id ? null : current));
      } else {
        setEditingSubjectId((current) => (current === target.id ? null : current));
      }
      invalidateAcademics();
    },
    onError: (err) => {
      setPendingDelete(null);
      setError(formatApiError(err, "Could not delete"));
    },
  });

  const rowBusy =
    updateSession.isPending ||
    updateTerm.isPending ||
    updateLevel.isPending ||
    updateArm.isPending ||
    updateSubject.isPending ||
    removeMutation.isPending;

  const sessionList = sessions.data ?? [];
  const termList = terms.data ?? [];
  const levelList = levels.data ?? [];
  const armList = arms.data ?? [];
  const subjectList = subjects.data ?? [];

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
                  <TH>Dates</TH>
                  <TH>Status</TH>
                  <TH>Actions</TH>
                </TR>
              </THead>
              <TBody>
                {sessionList.map((s) => {
                  const editing = editingSessionId === s.id;
                  return (
                    <TR key={s.id}>
                      <TD>
                        {editing ? (
                          <Input
                            value={editSessionName}
                            onChange={(e) => setEditSessionName(e.target.value)}
                            aria-label="Edit session name"
                          />
                        ) : (
                          s.name
                        )}
                      </TD>
                      <TD>
                        {editing ? (
                          <div className="grid gap-2">
                            <Input
                              type="date"
                              value={editSessionStart}
                              onChange={(e) => setEditSessionStart(e.target.value)}
                              aria-label="Edit session start"
                            />
                            <Input
                              type="date"
                              value={editSessionEnd}
                              onChange={(e) => setEditSessionEnd(e.target.value)}
                              aria-label="Edit session end"
                            />
                          </div>
                        ) : (
                          <span className="text-sm" style={{ fontFamily: "var(--font-mono)" }}>
                            {[s.start_date, s.end_date].filter(Boolean).join(" → ") || "—"}
                          </span>
                        )}
                      </TD>
                      <TD>
                        <Badge variant={s.is_active ? "success" : "default"}>
                          {s.is_active ? "active" : "inactive"}
                        </Badge>
                      </TD>
                      <TD>
                        {editing ? (
                          <span className="inline-flex flex-wrap gap-2">
                            <Button
                              size="sm"
                              disabled={
                                updateSession.isPending ||
                                !editSessionName.trim() ||
                                !editSessionStart ||
                                !editSessionEnd
                              }
                              onClick={() =>
                                updateSession.mutate({
                                  id: s.id,
                                  body: {
                                    name: editSessionName.trim(),
                                    start_date: editSessionStart,
                                    end_date: editSessionEnd,
                                  },
                                })
                              }
                            >
                              Save
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => setEditingSessionId(null)}
                            >
                              Cancel
                            </Button>
                          </span>
                        ) : (
                          <span className="inline-flex flex-wrap gap-2">
                            <Button
                              variant="ghost"
                              size="sm"
                              disabled={rowBusy}
                              onClick={() =>
                                updateSession.mutate({
                                  id: s.id,
                                  body: { is_active: !s.is_active },
                                })
                              }
                            >
                              {s.is_active ? "Deactivate" : "Activate"}
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              disabled={rowBusy}
                              onClick={() => startEditSession(s)}
                            >
                              Edit
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              disabled={rowBusy}
                              onClick={() =>
                                setPendingDelete({
                                  kind: "session",
                                  id: s.id,
                                  label: sessionLabel(s),
                                })
                              }
                            >
                              Delete
                            </Button>
                          </span>
                        )}
                      </TD>
                    </TR>
                  );
                })}
              </TBody>
            </Table>
          </CardBody>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Terms ({termList.length})</CardTitle>
          </CardHeader>
          <CardBody className="space-y-3">
            <div className="grid gap-2 sm:grid-cols-2">
              <Select
                aria-label="Term session"
                value={termSession}
                onChange={(e) => setTermSession(e.target.value)}
              >
                <option value="">Session</option>
                {sessionList.map((s) => (
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
                {TERM_NAMES.map((name) => (
                  <option key={name} value={name}>
                    {name}
                  </option>
                ))}
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
                  <TH>Status</TH>
                  <TH>Actions</TH>
                </TR>
              </THead>
              <TBody>
                {termList.map((t) => {
                  const editing = editingTermId === t.id;
                  return (
                    <TR key={t.id}>
                      <TD>
                        {editing ? (
                          <div className="grid gap-2">
                            <Select
                              aria-label="Edit term name"
                              value={editTermName}
                              onChange={(e) => setEditTermName(e.target.value)}
                            >
                              {TERM_NAMES.map((name) => (
                                <option key={name} value={name}>
                                  {name}
                                </option>
                              ))}
                            </Select>
                            <Input
                              type="date"
                              aria-label="Edit term start"
                              value={editTermStart}
                              onChange={(e) => setEditTermStart(e.target.value)}
                            />
                            <Input
                              type="date"
                              aria-label="Edit term end"
                              value={editTermEnd}
                              onChange={(e) => setEditTermEnd(e.target.value)}
                            />
                            <Input
                              aria-label="Edit school days"
                              value={editSchoolDays}
                              onChange={(e) => setEditSchoolDays(e.target.value)}
                              placeholder="School days"
                            />
                          </div>
                        ) : (
                          <div>
                            <div>{t.name}</div>
                            <div
                              className="text-xs text-ink/65"
                              style={{ fontFamily: "var(--font-mono)" }}
                            >
                              {[t.start_date, t.end_date].filter(Boolean).join(" → ") || "—"}
                              {t.total_school_days != null
                                ? ` · ${t.total_school_days} days`
                                : ""}
                            </div>
                          </div>
                        )}
                      </TD>
                      <TD>
                        {editing ? (
                          <Select
                            aria-label="Edit term session"
                            value={editTermSession}
                            onChange={(e) => setEditTermSession(e.target.value)}
                          >
                            {sessionList.map((s) => (
                              <option key={s.id} value={s.id}>
                                {s.name}
                              </option>
                            ))}
                          </Select>
                        ) : (
                          t.session_name || "—"
                        )}
                      </TD>
                      <TD>
                        <Badge variant={t.is_active ? "success" : "default"}>
                          {t.is_active ? "active" : "inactive"}
                        </Badge>
                      </TD>
                      <TD>
                        {editing ? (
                          <span className="inline-flex flex-wrap gap-2">
                            <Button
                              size="sm"
                              disabled={
                                updateTerm.isPending ||
                                !editTermSession ||
                                !editTermName ||
                                !editTermStart ||
                                !editTermEnd
                              }
                              onClick={() =>
                                updateTerm.mutate({
                                  id: t.id,
                                  body: {
                                    session: editTermSession,
                                    name: editTermName,
                                    start_date: editTermStart,
                                    end_date: editTermEnd,
                                    total_school_days: editSchoolDays
                                      ? Number(editSchoolDays)
                                      : undefined,
                                  },
                                })
                              }
                            >
                              Save
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => setEditingTermId(null)}
                            >
                              Cancel
                            </Button>
                          </span>
                        ) : (
                          <span className="inline-flex flex-wrap gap-2">
                            <Button
                              variant="ghost"
                              size="sm"
                              disabled={rowBusy}
                              onClick={() =>
                                updateTerm.mutate({
                                  id: t.id,
                                  body: { is_active: !t.is_active },
                                })
                              }
                            >
                              {t.is_active ? "Deactivate" : "Activate"}
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              disabled={rowBusy}
                              onClick={() => startEditTerm(t)}
                            >
                              Edit
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              disabled={rowBusy}
                              onClick={() =>
                                setPendingDelete({
                                  kind: "term",
                                  id: t.id,
                                  label: termLabel(t),
                                })
                              }
                            >
                              Delete
                            </Button>
                          </span>
                        )}
                      </TD>
                    </TR>
                  );
                })}
              </TBody>
            </Table>
          </CardBody>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>
              Levels / Arms ({levelList.length} / {armList.length})
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
                {levelList.map((level) => (
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
            <Table>
              <THead>
                <TR>
                  <TH>Level</TH>
                  <TH>Actions</TH>
                </TR>
              </THead>
              <TBody>
                {levelList.map((level) => {
                  const editing = editingLevelId === level.id;
                  return (
                    <TR key={level.id}>
                      <TD>
                        {editing ? (
                          <Input
                            value={editLevelName}
                            onChange={(e) => setEditLevelName(e.target.value)}
                            aria-label="Edit class level name"
                          />
                        ) : (
                          level.name
                        )}
                      </TD>
                      <TD>
                        {editing ? (
                          <span className="inline-flex flex-wrap gap-2">
                            <Button
                              size="sm"
                              disabled={updateLevel.isPending || !editLevelName.trim()}
                              onClick={() =>
                                updateLevel.mutate({
                                  id: level.id,
                                  body: { name: editLevelName.trim() },
                                })
                              }
                            >
                              Save
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => setEditingLevelId(null)}
                            >
                              Cancel
                            </Button>
                          </span>
                        ) : (
                          <span className="inline-flex flex-wrap gap-2">
                            <Button
                              variant="ghost"
                              size="sm"
                              disabled={rowBusy}
                              onClick={() => startEditLevel(level)}
                            >
                              Edit
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              disabled={rowBusy}
                              onClick={() =>
                                setPendingDelete({
                                  kind: "level",
                                  id: level.id,
                                  label: levelLabel(level),
                                })
                              }
                            >
                              Delete
                            </Button>
                          </span>
                        )}
                      </TD>
                    </TR>
                  );
                })}
              </TBody>
            </Table>
            <Table>
              <THead>
                <TR>
                  <TH>Level</TH>
                  <TH>Arm</TH>
                  <TH>Actions</TH>
                </TR>
              </THead>
              <TBody>
                {armList.map((arm) => {
                  const editing = editingArmId === arm.id;
                  const levelNameForArm =
                    levelList.find((l) => l.id === arm.class_level)?.name ?? "—";
                  return (
                    <TR key={arm.id}>
                      <TD>
                        {editing ? (
                          <Select
                            aria-label="Edit arm class level"
                            value={editArmLevel}
                            onChange={(e) => setEditArmLevel(e.target.value)}
                          >
                            {levelList.map((level) => (
                              <option key={level.id} value={level.id}>
                                {level.name}
                              </option>
                            ))}
                          </Select>
                        ) : (
                          levelNameForArm
                        )}
                      </TD>
                      <TD>
                        {editing ? (
                          <Input
                            value={editArmName}
                            onChange={(e) => setEditArmName(e.target.value)}
                            aria-label="Edit arm name"
                          />
                        ) : (
                          arm.name
                        )}
                      </TD>
                      <TD>
                        {editing ? (
                          <span className="inline-flex flex-wrap gap-2">
                            <Button
                              size="sm"
                              disabled={
                                updateArm.isPending || !editArmLevel || !editArmName.trim()
                              }
                              onClick={() =>
                                updateArm.mutate({
                                  id: arm.id,
                                  body: {
                                    class_level: editArmLevel,
                                    name: editArmName.trim(),
                                  },
                                })
                              }
                            >
                              Save
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => setEditingArmId(null)}
                            >
                              Cancel
                            </Button>
                          </span>
                        ) : (
                          <span className="inline-flex flex-wrap gap-2">
                            <Button
                              variant="ghost"
                              size="sm"
                              disabled={rowBusy}
                              onClick={() => startEditArm(arm)}
                            >
                              Edit
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              disabled={rowBusy}
                              onClick={() =>
                                setPendingDelete({
                                  kind: "arm",
                                  id: arm.id,
                                  label: armLabel(arm, levelList),
                                })
                              }
                            >
                              Delete
                            </Button>
                          </span>
                        )}
                      </TD>
                    </TR>
                  );
                })}
              </TBody>
            </Table>
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
                  <TH>Actions</TH>
                </TR>
              </THead>
              <TBody>
                {subjectList.map((s) => {
                  const editing = editingSubjectId === s.id;
                  return (
                    <TR key={s.id}>
                      <TD>
                        {editing ? (
                          <Input
                            value={editSubjectCode}
                            onChange={(e) => setEditSubjectCode(e.target.value)}
                            aria-label="Edit subject code"
                            style={{ fontFamily: "var(--font-mono)" }}
                          />
                        ) : (
                          <span style={{ fontFamily: "var(--font-mono)" }}>{s.code}</span>
                        )}
                      </TD>
                      <TD>
                        {editing ? (
                          <Input
                            value={editSubjectName}
                            onChange={(e) => setEditSubjectName(e.target.value)}
                            aria-label="Edit subject name"
                          />
                        ) : (
                          s.name
                        )}
                      </TD>
                      <TD>
                        {editing ? (
                          <span className="inline-flex flex-wrap gap-2">
                            <Button
                              size="sm"
                              disabled={
                                updateSubject.isPending ||
                                !editSubjectName.trim() ||
                                !editSubjectCode.trim()
                              }
                              onClick={() =>
                                updateSubject.mutate({
                                  id: s.id,
                                  body: {
                                    name: editSubjectName.trim(),
                                    code: editSubjectCode.trim(),
                                  },
                                })
                              }
                            >
                              Save
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => setEditingSubjectId(null)}
                            >
                              Cancel
                            </Button>
                          </span>
                        ) : (
                          <span className="inline-flex flex-wrap gap-2">
                            <Button
                              variant="ghost"
                              size="sm"
                              disabled={rowBusy}
                              onClick={() => startEditSubject(s)}
                            >
                              Edit
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              disabled={rowBusy}
                              onClick={() =>
                                setPendingDelete({
                                  kind: "subject",
                                  id: s.id,
                                  label: subjectLabel(s),
                                })
                              }
                            >
                              Delete
                            </Button>
                          </span>
                        )}
                      </TD>
                    </TR>
                  );
                })}
              </TBody>
            </Table>
          </CardBody>
        </Card>
      </div>

      <ConfirmDeleteModal
        open={Boolean(pendingDelete)}
        onClose={() => setPendingDelete(null)}
        onConfirm={() => {
          if (pendingDelete) removeMutation.mutate(pendingDelete);
        }}
        title={pendingDelete ? `Delete ${pendingDelete.label}?` : "Delete?"}
        description="This cannot be undone. If the record is still referenced (enrollments, invoices, or assignments), the server will refuse."
        pending={removeMutation.isPending}
      />
    </div>
  );
}
