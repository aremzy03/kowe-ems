"use client";

import {
  Fragment,
  useEffect,
  useRef,
  useState,
  type FormEvent,
  type ReactNode,
} from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Badge,
  Button,
  Card,
  CardBody,
  EmptyState,
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
  currentTerm,
  type Arm,
  type ClassLevel,
  type Session,
  type Subject,
  type Term,
} from "@/lib/api/academics";
import { ApiRequestError } from "@/lib/api/client";
import { formatApiError, mapDrfErrors } from "@/lib/api/errors";
import { cn } from "@/lib/cn";

type DeleteKind = "session" | "term" | "level" | "arm" | "subject";

type PendingDelete = {
  kind: DeleteKind;
  id: string;
  label: string;
};

type TermDraft = {
  session: string;
  name: string;
  start_date: string;
  end_date: string;
  total_school_days?: number;
};

const TERM_NAMES = ["1st", "2nd", "3rd"] as const;
type TermName = (typeof TERM_NAMES)[number];

function isTermName(value: string): value is TermName {
  return (TERM_NAMES as readonly string[]).includes(value);
}

function termRank(name: string): number {
  const index = TERM_NAMES.indexOf(name as TermName);
  return index < 0 ? TERM_NAMES.length : index;
}

function termsOnSession(terms: Term[], sessionId: string): Term[] {
  return terms
    .filter((term) => term.session === sessionId)
    .slice()
    .sort((a, b) => termRank(a.name) - termRank(b.name));
}

function nextTermName(sessionId: string, terms: Term[]): TermName | null {
  const taken = new Set(
    terms.filter((term) => term.session === sessionId).map((term) => term.name),
  );
  return TERM_NAMES.find((name) => !taken.has(name)) ?? null;
}

function parseSchoolDays(raw: string): number | undefined {
  const trimmed = raw.trim();
  if (!/^\d+$/.test(trimmed)) return undefined;
  return Number(trimmed);
}

function sessionLabel(session: Session) {
  return session.name || "Session";
}

function termLabel(term: Term) {
  return [term.session_name, term.name].filter(Boolean).join(" · ") || term.name;
}

function termHeading(term: Term, sessions: Session[]): string {
  const sessionName =
    term.session_name ||
    sessions.find((session) => session.id === term.session)?.name ||
    "Session";
  return `${sessionName} · ${term.name}`;
}

function levelLabel(level: ClassLevel) {
  return level.name || "Class level";
}

function armLabel(arm: Arm, levels: ClassLevel[]) {
  const level = levels.find((item) => item.id === arm.class_level);
  return level ? `${level.name}${arm.name}` : arm.name;
}

function subjectLabel(subject: Subject) {
  return subject.code ? `${subject.code} — ${subject.name}` : subject.name;
}

function subjectStatus(subject: Pick<Subject, "code" | "name">, verb: "added" | "saved") {
  const label = subject.code?.trim() || subject.name;
  return `${label} ${verb}.`;
}

function termStatus(
  termName: string,
  sessionName: string | undefined,
  verb: "added" | "saved",
) {
  if (!sessionName) return `${termName} term ${verb}.`;
  return verb === "added"
    ? `${termName} term added to ${sessionName}.`
    : `${termName} term saved on ${sessionName}.`;
}

function armStatus(armName: string, levelName: string | undefined, verb: "added" | "saved") {
  if (!levelName) return `Arm ${armName} ${verb}.`;
  return verb === "added"
    ? `Arm ${armName} added to ${levelName}.`
    : `Arm ${armName} saved on ${levelName}.`;
}

function upsertCached<T extends { id: string }>(
  current: T[] | undefined,
  created: T,
  position: "start" | "end",
): T[] {
  const list = current ?? [];
  if (list.some((item) => item.id === created.id)) return list;
  return position === "start" ? [created, ...list] : [...list, created];
}

function ActionRow({ children }: { children: ReactNode }) {
  return <span className="inline-flex flex-wrap items-center gap-2">{children}</span>;
}

function dateRange(start?: string, end?: string) {
  return [start, end].filter(Boolean).join(" → ") || "—";
}

/** Darker than --color-danger so error text clears 4.5:1 on paper and paper-card. */
const ERROR_INK = "#8B2424";

/** Primary add actions: 44px tall, full width while the form is one column. */
const addActionClass = "min-h-11 w-full sm:w-auto";
/** Inline Save. 44px tall, and it stays beside Cancel. */
const saveActionClass = "min-h-11";

const SCHOOL_DAYS_HELP =
  "Instructional days in this term. Attendance percentage uses this number as the denominator. There is no holiday calendar in this version.";

const editGridClass = "grid min-w-0 gap-3 sm:grid-cols-2 [&>*]:min-w-0";

/** Form under a summary row. The table rule bounds it; this is not a nested card. */
function TableEditSheet({
  colSpan,
  children,
}: {
  colSpan: number;
  children: ReactNode;
}) {
  return (
    <TR>
      <TD colSpan={colSpan} className="bg-paper-field align-top">
        <div className="w-0 min-w-full">{children}</div>
      </TD>
    </TR>
  );
}

const LOAD_COPY = {
  sessions: "Could not load sessions. Refresh the page and try again.",
  terms: "Could not load terms. Refresh the page and try again.",
  classes: "Could not load classes. Refresh the page and try again.",
  arms: "Could not load arms. Refresh the page and try again.",
  subjects: "Could not load subjects. Refresh the page and try again.",
} as const;

type SectionId = "session" | "term" | "level" | "arm" | "subject";
type ErrorPlace = "create" | "edit" | "section";

type SectionError = {
  place: ErrorPlace;
  message?: string;
  fields: Record<string, string>;
};

type DuplicateContext = {
  name?: string;
  termName?: string;
  sessionName?: string;
  levelName?: string;
  armName?: string;
  code?: string;
};

const UNIQUE_RE = /unique set|already exists|must be unique/i;
const SHOWN_FIELDS = new Set([
  "name",
  "start_date",
  "end_date",
  "code",
  "session",
  "class_level",
  "total_school_days",
]);

function duplicateCopy(section: SectionId, ctx: DuplicateContext): string {
  if (section === "session") {
    const name = ctx.name?.trim();
    return name
      ? `A session named ${name} already exists. Use a different name.`
      : "A session with that name already exists. Use a different name.";
  }
  if (section === "term") {
    const term = ctx.termName?.trim() || "That term";
    const session = ctx.sessionName?.trim() || "that session";
    return `${term} is already on ${session}. Edit that term, or choose another.`;
  }
  if (section === "level") {
    const name = ctx.name?.trim();
    return name
      ? `A class named ${name} already exists.`
      : "A class with that name already exists.";
  }
  if (section === "arm") {
    const arm = ctx.armName?.trim() || "That arm";
    const level = ctx.levelName?.trim() || "that class";
    return `${arm} is already an arm of ${level}.`;
  }
  const code = ctx.code?.trim();
  return code
    ? `The code ${code} is already used. Each subject needs its own code.`
    : "That subject code is already used. Each subject needs its own code.";
}

function fallbackCopy(section: SectionId): string {
  if (section === "session") {
    return "Could not save the session. Check the name and dates, then try again.";
  }
  if (section === "term") {
    return "Could not save the term. Check the session, dates, and school days, then try again.";
  }
  if (section === "level") {
    return "Could not save the class. Check the name, then try again.";
  }
  if (section === "arm") {
    return "Could not save the arm. Check the class and arm name, then try again.";
  }
  return "Could not save the subject. Check the code and name, then try again.";
}

function polishField(key: string, raw: string): string {
  if (key === "end_date") return "End date must be on or after the start date.";
  if (key === "total_school_days") return "School days must be a whole number.";
  return raw;
}

function isUnique(text: string | undefined): boolean {
  return Boolean(text && UNIQUE_RE.test(text));
}

function explainFailure(
  section: SectionId,
  err: unknown,
  ctx: DuplicateContext,
  fallback?: string,
): Omit<SectionError, "place"> {
  const safeFallback = fallback ?? fallbackCopy(section);
  if (!(err instanceof ApiRequestError)) {
    const message = err instanceof Error && err.message ? err.message : safeFallback;
    return { message: isUnique(message) ? duplicateCopy(section, ctx) : message, fields: {} };
  }
  const mapped = mapDrfErrors(err.data);
  const pieces = [mapped.form, ...Object.values(mapped.fields)];
  if (pieces.some((piece) => isUnique(piece))) {
    return { message: duplicateCopy(section, ctx), fields: {} };
  }
  const fields: Record<string, string> = {};
  const leftovers: string[] = [];
  for (const [key, value] of Object.entries(mapped.fields)) {
    if (!value) continue;
    if (SHOWN_FIELDS.has(key)) fields[key] = polishField(key, value);
    else leftovers.push(value);
  }
  let message: string | undefined;
  if (mapped.form && mapped.form !== "Request failed") message = mapped.form;
  if (leftovers.length) {
    message = [message, ...leftovers].filter(Boolean).join(" ");
  }
  if (!message && Object.keys(fields).length === 0) {
    message = formatApiError(err, safeFallback);
  }
  return { message, fields };
}

function deleteRefusal(err: unknown, label: string): string {
  const name = label.trim() || "This record";
  const detail = formatApiError(err, "");
  const refused =
    (err instanceof ApiRequestError && err.status === 409) ||
    /referenced|protected|cannot be deleted/i.test(detail);
  if (refused) {
    return `${name} is still used by other records, so it cannot be deleted. Remove the enrollments, invoices, or assignments that use it, then try again.`;
  }
  return detail || `Could not delete ${name}. Try again.`;
}

function FormAlert({ children }: { children: ReactNode }) {
  return (
    <p role="alert" className="text-sm font-medium" style={{ color: ERROR_INK }}>
      {children}
    </p>
  );
}

function FieldError({
  id,
  message,
  live = false,
}: {
  id: string;
  message?: string;
  live?: boolean;
}) {
  if (!message) return null;
  return (
    <p
      id={id}
      role={live ? "alert" : undefined}
      className="mt-1.5 text-sm font-medium"
      style={{ color: ERROR_INK }}
    >
      {message}
    </p>
  );
}

function loneField(error: SectionError | undefined, key: string): boolean {
  if (!error || error.message) return false;
  const keys = Object.keys(error.fields).filter((name) => error.fields[name]);
  return keys.length === 1 && keys[0] === key;
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
  const [termName, setTermName] = useState<TermName>("1st");
  const [termStart, setTermStart] = useState("");
  const [termEnd, setTermEnd] = useState("");
  const [schoolDays, setSchoolDays] = useState("");
  const [levelName, setLevelName] = useState("");
  const [armLevel, setArmLevel] = useState("");
  const [armName, setArmName] = useState("");
  const [sectionErrors, setSectionErrors] = useState<Partial<Record<SectionId, SectionError>>>(
    {},
  );
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const [editingSessionId, setEditingSessionId] = useState<string | null>(null);
  const [editSessionName, setEditSessionName] = useState("");
  const [editSessionStart, setEditSessionStart] = useState("");
  const [editSessionEnd, setEditSessionEnd] = useState("");

  const [editingTermId, setEditingTermId] = useState<string | null>(null);
  const [editTermSession, setEditTermSession] = useState("");
  const [editTermName, setEditTermName] = useState<string>("1st");
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
  const [statusText, setStatusText] = useState("");
  const statusSeq = useRef(0);

  const termStartRef = useRef<HTMLInputElement>(null);
  const armNameRef = useRef<HTMLInputElement>(null);
  const pendingTermFocus = useRef(false);
  const pendingArmFocusId = useRef<string | null>(null);
  const sessionBootstrapped = useRef(false);
  const levelBootstrapped = useRef(false);
  const pendingEditFocus = useRef<string | null>(null);

  const sessionList = sessions.data ?? [];
  const termList = terms.data ?? [];
  const levelList = levels.data ?? [];
  const armList = arms.data ?? [];
  const subjectList = subjects.data ?? [];

  function invalidateAcademics() {
    void qc.invalidateQueries({ queryKey: ["academics"] });
  }

  function announce(message: string) {
    const seq = statusSeq.current + 1;
    statusSeq.current = seq;
    setStatusText("");
    window.setTimeout(() => {
      if (statusSeq.current !== seq) return;
      setStatusText(message);
    }, 40);
    window.setTimeout(() => {
      if (statusSeq.current !== seq) return;
      setStatusText("");
    }, 2840);
  }

  function sessionNameFor(sessionId: string | undefined, fallback?: string) {
    const named = fallback?.trim();
    if (named) return named;
    if (!sessionId) return undefined;
    return sessionList.find((session) => session.id === sessionId)?.name;
  }

  function levelNameFor(levelId: string | undefined) {
    if (!levelId) return undefined;
    return levelList.find((level) => level.id === levelId)?.name;
  }

  function pickSession(sessionId: string, moveFocus: boolean) {
    setTermSession(sessionId);
    if (!sessionId) {
      setTermName("1st");
    } else {
      setTermName(nextTermName(sessionId, termList) ?? "3rd");
    }
    setTermStart("");
    setTermEnd("");
    setSchoolDays("");
    if (moveFocus) pendingTermFocus.current = true;
  }

  useEffect(() => {
    if (sessionBootstrapped.current || !sessions.isSuccess || !terms.isSuccess) return;
    sessionBootstrapped.current = true;
    if (termSession || sessionList.length === 0) return;
    const preferred = sessionList.find((session) => session.is_active) ?? sessionList[0];
    setTermSession(preferred.id);
    const next = nextTermName(preferred.id, termList);
    if (next) setTermName(next);
  }, [sessions.isSuccess, terms.isSuccess, termSession, sessionList, termList]);

  useEffect(() => {
    if (levelBootstrapped.current || !levels.isSuccess) return;
    levelBootstrapped.current = true;
    if (armLevel || levelList.length === 0) return;
    setArmLevel(levelList[0].id);
  }, [levels.isSuccess, armLevel, levelList]);

  useEffect(() => {
    if (!pendingTermFocus.current || !termStartRef.current) return;
    termStartRef.current.focus();
    pendingTermFocus.current = false;
  }, [termSession, termName, termStart]);

  useEffect(() => {
    const target = pendingArmFocusId.current;
    if (!target || target !== armLevel || !armNameRef.current) return;
    armNameRef.current.focus();
    pendingArmFocusId.current = null;
  }, [armLevel, levels.data, arms.data]);

  useEffect(() => {
    const id = pendingEditFocus.current;
    if (!id) return;
    const node = document.getElementById(id);
    if (!node) return;
    node.focus();
    pendingEditFocus.current = null;
  }, [editingSessionId, editingTermId, editingSubjectId, editingArmId]);

  function startEditSession(session: Session) {
    setEditingSessionId(session.id);
    setEditSessionName(session.name);
    setEditSessionStart(session.start_date ?? "");
    setEditSessionEnd(session.end_date ?? "");
    pendingEditFocus.current = `edit-session-name-${session.id}`;
  }

  function startEditTerm(term: Term) {
    setEditingTermId(term.id);
    setEditTermSession(term.session);
    setEditTermName(isTermName(term.name) ? term.name : "1st");
    setEditTermStart(term.start_date ?? "");
    setEditTermEnd(term.end_date ?? "");
    setEditSchoolDays(
      term.total_school_days != null ? String(term.total_school_days) : "",
    );
    pendingEditFocus.current = `edit-term-session-${term.id}`;
  }

  function startEditLevel(level: ClassLevel) {
    setEditingLevelId(level.id);
    setEditLevelName(level.name);
  }

  function startEditArm(arm: Arm) {
    setEditingArmId(arm.id);
    setEditArmLevel(arm.class_level);
    setEditArmName(arm.name);
    pendingEditFocus.current = `edit-arm-level-${arm.id}`;
  }

  function startEditSubject(subject: Subject) {
    setEditingSubjectId(subject.id);
    setEditSubjectCode(subject.code ?? "");
    setEditSubjectName(subject.name);
    pendingEditFocus.current = `edit-subject-code-${subject.id}`;
  }

  const createSession = useMutation({
    mutationFn: () =>
      academicsApi.sessions.create({
        name: sessionName.trim(),
        start_date: sessionStart,
        end_date: sessionEnd,
        is_active: false,
      }),
    onSuccess: (created) => {
      qc.setQueryData<Session[]>(["academics", "sessions"], (current) =>
        upsertCached(current, created, "start"),
      );
      setSessionName("");
      setTermSession(created.id);
      setTermName("1st");
      setTermStart("");
      setTermEnd("");
      setSchoolDays("");
      clearError("session");
      pendingTermFocus.current = true;
      announce(`${created.name} added.`);
      invalidateAcademics();
    },
    onError: (err) =>
      reportError("session", err, { name: sessionName.trim() }, "create"),
  });

  const updateSession = useMutation({
    mutationFn: ({ id, body }: { id: string; body: Partial<Session> }) =>
      academicsApi.sessions.update(id, body),
    onSuccess: (updated, variables) => {
      if (variables.body.name !== undefined) {
        setEditingSessionId((current) => (current === variables.id ? null : current));
        announce(`${updated.name} saved.`);
      } else if (variables.body.is_active !== undefined) {
        announce(
          `${updated.name} is now ${variables.body.is_active ? "active" : "inactive"}.`,
        );
      }
      clearError("session");
      invalidateAcademics();
    },
    onError: (err, variables) =>
      reportError(
        "session",
        err,
        { name: variables.body.name ?? editSessionName.trim() },
        variables.body.name ? "edit" : "section",
      ),
  });

  const createTerm = useMutation({
    mutationFn: (draft: TermDraft) =>
      academicsApi.terms.create({ ...draft, is_active: false }),
    onSuccess: (created, draft) => {
      qc.setQueryData<Term[]>(["academics", "terms"], (current) =>
        upsertCached(current, created, "end"),
      );
      const taken = new Set(
        (qc.getQueryData<Term[]>(["academics", "terms"]) ?? [])
          .filter((term) => term.session === draft.session)
          .map((term) => term.name),
      );
      const advanced = TERM_NAMES.find((name) => !taken.has(name));
      setTermSession(draft.session);
      setTermName(advanced ?? (isTermName(draft.name) ? draft.name : "3rd"));
      setTermStart("");
      setTermEnd("");
      setSchoolDays("");
      clearError("term");
      pendingTermFocus.current = true;
      announce(
        termStatus(created.name, sessionNameFor(draft.session, created.session_name), "added"),
      );
      invalidateAcademics();
    },
    onError: (err, draft) =>
      reportError(
        "term",
        err,
        {
          termName: draft.name,
          sessionName: sessionList.find((item) => item.id === draft.session)?.name,
        },
        "create",
      ),
  });

  const updateTerm = useMutation({
    mutationFn: ({ id, body }: { id: string; body: Partial<Term> }) =>
      academicsApi.terms.update(id, body),
    onSuccess: (updated) => {
      setEditingTermId((current) => (current === updated.id ? null : current));
      clearError("term");
      announce(termStatus(updated.name, sessionNameFor(updated.session, updated.session_name), "saved"));
      invalidateAcademics();
    },
    onError: (err, variables) =>
      reportError(
        "term",
        err,
        {
          termName: variables.body.name,
          sessionName: sessionList.find((item) => item.id === variables.body.session)?.name,
        },
        "edit",
      ),
  });

  const makeCurrentTerm = useMutation({
    mutationFn: async (term: Term) => {
      const list = qc.getQueryData<Term[]>(["academics", "terms"]) ?? termList;
      if (!term.is_active) {
        await academicsApi.terms.update(term.id, { is_active: true });
      }
      const others = list.filter((item) => item.id !== term.id && item.is_active);
      await Promise.all(
        others.map((item) =>
          academicsApi.terms.update(item.id, { is_active: false }),
        ),
      );
    },
    onSuccess: (_data, term) => {
      qc.setQueryData<Term[]>(["academics", "terms"], (current) =>
        (current ?? []).map((item) => ({
          ...item,
          is_active: item.id === term.id,
        })),
      );
      clearError("term");
      announce(`${term.name} term is now the current term.`);
      invalidateAcademics();
    },
    onError: (err, term) => {
      reportError(
        "term",
        err,
        { termName: term.name, sessionName: term.session_name },
        "section",
        "Could not mark this term as current. Try again.",
      );
      invalidateAcademics();
    },
  });

  const createLevel = useMutation({
    mutationFn: () => academicsApi.classLevels.create({ name: levelName.trim() }),
    onSuccess: (created) => {
      qc.setQueryData<ClassLevel[]>(["academics", "class-levels"], (current) =>
        upsertCached(current, created, "end"),
      );
      setLevelName("");
      setArmLevel(created.id);
      setArmName("");
      pendingArmFocusId.current = created.id;
      clearError("level");
      announce(`${created.name} added.`);
      invalidateAcademics();
    },
    onError: (err) => reportError("level", err, { name: levelName.trim() }, "create"),
  });

  const updateLevel = useMutation({
    mutationFn: ({ id, body }: { id: string; body: Partial<ClassLevel> }) =>
      academicsApi.classLevels.update(id, body),
    onSuccess: (updated) => {
      setEditingLevelId((current) => (current === updated.id ? null : current));
      clearError("level");
      announce(`${updated.name} saved.`);
      invalidateAcademics();
    },
    onError: (err, variables) =>
      reportError("level", err, { name: variables.body.name }, "edit"),
  });

  const createArm = useMutation({
    mutationFn: () =>
      academicsApi.arms.create({ class_level: armLevel, name: armName.trim() }),
    onSuccess: (created) => {
      qc.setQueryData<Arm[]>(["academics", "arms"], (current) =>
        upsertCached(current, created, "end"),
      );
      setArmName("");
      clearError("arm");
      pendingArmFocusId.current = armLevel;
      announce(armStatus(created.name, levelNameFor(created.class_level), "added"));
      invalidateAcademics();
    },
    onError: (err) =>
      reportError(
        "arm",
        err,
        {
          armName: armName.trim(),
          levelName: levelList.find((level) => level.id === armLevel)?.name,
        },
        "create",
      ),
  });

  const updateArm = useMutation({
    mutationFn: ({ id, body }: { id: string; body: Partial<Arm> }) =>
      academicsApi.arms.update(id, body),
    onSuccess: (updated) => {
      setEditingArmId((current) => (current === updated.id ? null : current));
      clearError("arm");
      announce(armStatus(updated.name, levelNameFor(updated.class_level), "saved"));
      invalidateAcademics();
    },
    onError: (err, variables) =>
      reportError(
        "arm",
        err,
        {
          armName: variables.body.name,
          levelName: levelList.find((level) => level.id === variables.body.class_level)?.name,
        },
        "edit",
      ),
  });

  const createSubject = useMutation({
    mutationFn: () =>
      academicsApi.subjects.create({
        name: subjectName.trim(),
        code: subjectCode.trim(),
      }),
    onSuccess: (created) => {
      setSubjectName("");
      setSubjectCode("");
      clearError("subject");
      announce(subjectStatus(created, "added"));
      invalidateAcademics();
    },
    onError: (err) =>
      reportError(
        "subject",
        err,
        { code: subjectCode.trim(), name: subjectName.trim() },
        "create",
      ),
  });

  const updateSubject = useMutation({
    mutationFn: ({ id, body }: { id: string; body: Partial<Subject> }) =>
      academicsApi.subjects.update(id, body),
    onSuccess: (updated) => {
      setEditingSubjectId((current) => (current === updated.id ? null : current));
      clearError("subject");
      announce(subjectStatus(updated, "saved"));
      invalidateAcademics();
    },
    onError: (err, variables) =>
      reportError(
        "subject",
        err,
        { code: variables.body.code, name: variables.body.name },
        "edit",
      ),
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
      setDeleteError(null);
      if (target.kind === "session") {
        setEditingSessionId((current) => (current === target.id ? null : current));
        if (target.id === termSession) {
          const remaining = sessionList.filter((session) => session.id !== target.id);
          const next =
            remaining.find((session) => session.is_active) ?? remaining[0];
          if (next) {
            const remainingTerms = termList.filter((term) => term.session !== target.id);
            setTermSession(next.id);
            setTermName(nextTermName(next.id, remainingTerms) ?? "3rd");
            setTermStart("");
            setTermEnd("");
            setSchoolDays("");
          } else {
            setTermSession("");
            setTermName("1st");
          }
        }
      } else if (target.kind === "term") {
        setEditingTermId((current) => (current === target.id ? null : current));
      } else if (target.kind === "level") {
        setEditingLevelId((current) => (current === target.id ? null : current));
        if (target.id === armLevel) {
          const remaining = levelList.filter((level) => level.id !== target.id);
          setArmLevel(remaining[0]?.id ?? "");
          setArmName("");
        }
      } else if (target.kind === "arm") {
        setEditingArmId((current) => (current === target.id ? null : current));
      } else {
        setEditingSubjectId((current) => (current === target.id ? null : current));
      }
      invalidateAcademics();
    },
    onError: (err, target) => {
      setDeleteError(deleteRefusal(err, target.label));
    },
  });

  function recordBusy(kind: DeleteKind, id: string) {
    if (
      removeMutation.isPending &&
      removeMutation.variables?.kind === kind &&
      removeMutation.variables.id === id
    ) {
      return true;
    }
    if (kind === "session") {
      return updateSession.isPending && updateSession.variables?.id === id;
    }
    if (kind === "term") {
      return (
        (updateTerm.isPending && updateTerm.variables?.id === id) ||
        (makeCurrentTerm.isPending && makeCurrentTerm.variables?.id === id)
      );
    }
    if (kind === "level") {
      return updateLevel.isPending && updateLevel.variables?.id === id;
    }
    if (kind === "arm") {
      return updateArm.isPending && updateArm.variables?.id === id;
    }
    return updateSubject.isPending && updateSubject.variables?.id === id;
  }

  const selectedSession = sessionList.find((session) => session.id === termSession);
  const selectedTerms = termSession ? termsOnSession(termList, termSession) : [];
  const termNameTaken = selectedTerms.some((term) => term.name === termName);
  const schoolDaysInvalid = schoolDays.trim() !== "" && parseSchoolDays(schoolDays) === undefined;
  const termDatesInvalid = Boolean(termStart && termEnd && termEnd < termStart);
  const sessionDatesInvalid = Boolean(
    sessionStart && sessionEnd && sessionEnd < sessionStart,
  );
  const armNameTaken = Boolean(
    armLevel &&
      armName.trim() &&
      armList.some(
        (arm) => arm.class_level === armLevel && arm.name === armName.trim(),
      ),
  );
  const activeTerms = termList.filter((term) => term.is_active);
  const markedCurrent = currentTerm(termList);
  const classesPending = levels.isPending || arms.isPending;
  const sessionCreate = placedError("session", "create");
  const sessionEdit = placedError("session", "edit");
  const sessionSection = placedError("session", "section");
  const termCreate = placedError("term", "create");
  const termEdit = placedError("term", "edit");
  const termSection = placedError("term", "section");
  const levelCreate = placedError("level", "create");
  const levelEdit = placedError("level", "edit");
  const armCreate = placedError("arm", "create");
  const armEdit = placedError("arm", "edit");
  const subjectCreate = placedError("subject", "create");
  const subjectEdit = placedError("subject", "edit");

  function clearError(section: SectionId) {
    setSectionErrors((current) => {
      if (!current[section]) return current;
      const next = { ...current };
      delete next[section];
      return next;
    });
  }

  function reportError(
    section: SectionId,
    err: unknown,
    ctx: DuplicateContext,
    place: ErrorPlace,
    fallback?: string,
  ) {
    setSectionErrors((current) => ({
      ...current,
      [section]: { ...explainFailure(section, err, ctx, fallback), place },
    }));
  }

  function placedError(section: SectionId, place: ErrorPlace): SectionError | undefined {
    const current = sectionErrors[section];
    if (!current || current.place !== place) return undefined;
    return current;
  }

  function askDelete(target: PendingDelete) {
    setDeleteError(null);
    setPendingDelete(target);
  }

  function submitSession(event: FormEvent) {
    event.preventDefault();
    if (
      sessions.isError ||
      !sessionName.trim() ||
      !sessionStart ||
      !sessionEnd ||
      sessionDatesInvalid ||
      createSession.isPending
    ) {
      return;
    }
    clearError("session");
    createSession.mutate();
  }

  function submitTerm(event: FormEvent) {
    event.preventDefault();
    const days = parseSchoolDays(schoolDays);
    if (
      terms.isError ||
      !termSession ||
      !termStart ||
      !termEnd ||
      termDatesInvalid ||
      termNameTaken ||
      schoolDaysInvalid ||
      createTerm.isPending
    ) {
      return;
    }
    clearError("term");
    createTerm.mutate({
      session: termSession,
      name: termName,
      start_date: termStart,
      end_date: termEnd,
      ...(days !== undefined ? { total_school_days: days } : {}),
    });
  }

  function submitLevel(event: FormEvent) {
    event.preventDefault();
    if (levels.isError || !levelName.trim() || createLevel.isPending) return;
    clearError("level");
    createLevel.mutate();
  }

  function submitArm(event: FormEvent) {
    event.preventDefault();
    if (arms.isError || !armLevel || !armName.trim() || armNameTaken || createArm.isPending) return;
    clearError("arm");
    createArm.mutate();
  }

  function submitSubject(event: FormEvent) {
    event.preventDefault();
    if (subjects.isError || !subjectCode.trim() || !subjectName.trim() || createSubject.isPending) {
      return;
    }
    clearError("subject");
    createSubject.mutate();
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Academics"
        description="Set up the year in order: the session, its three terms, each class with its arms, then subjects."
      />

      <p
        role="status"
        aria-live="polite"
        aria-atomic="true"
        className={
          statusText
            ? "sticky top-0 z-10 rounded-[var(--radius-nb)] border border-rule bg-paper px-3 py-2 text-sm font-medium text-ink"
            : "sr-only"
        }
      >
        {statusText}
      </p>

      <Card>
        <CardBody className="space-y-10">
          <section
            className="space-y-4"
            aria-labelledby="academics-session"
            aria-busy={sessions.isPending}
          >
            <div className="space-y-1">
              <h2 id="academics-session" className="text-lg font-bold">
                Session
              </h2>
              <p className="max-w-2xl text-sm leading-relaxed text-ink/70">
                The academic year, for example 2026/2027. Adding a session selects it so you can add its terms next.
              </p>
            </div>
            {sessionSection?.message ? <FormAlert>{sessionSection.message}</FormAlert> : null}
            {sessions.isError ? <FormAlert>{LOAD_COPY.sessions}</FormAlert> : null}
            <form onSubmit={submitSession}>
              <fieldset
                disabled={sessions.isError}
                className="m-0 space-y-3 border-0 p-0 [min-inline-size:0]"
              >
              <div className="grid min-w-0 gap-3 sm:grid-cols-2 [&>*]:min-w-0">
                <div className="sm:col-span-2">
                  <Label htmlFor="session-name">Session name</Label>
                  <Input
                    id="session-name"
                    className="min-w-0"
                    value={sessionName}
                    onChange={(event) => setSessionName(event.target.value)}
                    placeholder="2026/2027"
                    autoComplete="off"
                    aria-invalid={Boolean(sessionCreate?.fields.name) || undefined}
                    aria-describedby={sessionCreate?.fields.name ? "session-name-error" : undefined}
                  />
                  <FieldError
                    id="session-name-error"
                    message={sessionCreate?.fields.name}
                    live={loneField(sessionCreate, "name")}
                  />
                </div>
                <div>
                  <Label htmlFor="session-start">Start</Label>
                  <Input
                    id="session-start"
                    className="min-w-0"
                    type="date"
                    value={sessionStart}
                    onChange={(event) => setSessionStart(event.target.value)}
                    aria-invalid={Boolean(sessionCreate?.fields.start_date) || undefined}
                    aria-describedby={
                      sessionCreate?.fields.start_date ? "session-start-error" : undefined
                    }
                  />
                  <FieldError
                    id="session-start-error"
                    message={sessionCreate?.fields.start_date}
                    live={loneField(sessionCreate, "start_date")}
                  />
                </div>
                <div>
                  <Label htmlFor="session-end">End</Label>
                  <Input
                    id="session-end"
                    className="min-w-0"
                    type="date"
                    value={sessionEnd}
                    onChange={(event) => setSessionEnd(event.target.value)}
                    aria-invalid={Boolean(sessionCreate?.fields.end_date) || undefined}
                    aria-describedby={
                      sessionCreate?.fields.end_date ? "session-end-error" : undefined
                    }
                  />
                  <FieldError
                    id="session-end-error"
                    message={sessionCreate?.fields.end_date}
                    live={loneField(sessionCreate, "end_date")}
                  />
                </div>
              </div>
              {sessionDatesInvalid ? (
                <FormAlert>End date must be on or after the start date.</FormAlert>
              ) : null}
              {sessionCreate?.message ? <FormAlert>{sessionCreate.message}</FormAlert> : null}
              <Button
                type="submit"
                size="sm"
                className={addActionClass}
                disabled={
                  sessions.isError ||
                  !sessionName.trim() ||
                  !sessionStart ||
                  !sessionEnd ||
                  sessionDatesInvalid ||
                  createSession.isPending
                }
              >
                {createSession.isPending ? "Adding…" : "Add session"}
              </Button>
              </fieldset>
            </form>
            {sessions.isPending ? <p className="text-sm text-ink/70">Loading…</p> : null}
            {sessions.isSuccess && sessionList.length === 0 ? (
              <EmptyState
                headline="No session exists yet"
                body="Add the academic year in the form above, for example 2026/2027, because terms attach to it."
              />
            ) : null}
            {sessionList.length > 0 ? (
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
                  {sessionList.map((session) => {
                    const editing = editingSessionId === session.id;
                    const selected = session.id === termSession;
                    const busy = recordBusy("session", session.id);
                    const savingForm =
                      updateSession.isPending &&
                      updateSession.variables?.id === session.id &&
                      updateSession.variables.body.name !== undefined;
                    const flipping =
                      updateSession.isPending &&
                      updateSession.variables?.id === session.id &&
                      !savingForm;
                    return (
                      <Fragment key={session.id}>
                        <TR className={selected ? "bg-paper-tint" : undefined}>
                          <TD>{session.name}</TD>
                          <TD>
                            <span className="text-sm" style={{ fontFamily: "var(--font-mono)" }}>
                              {dateRange(session.start_date, session.end_date)}
                            </span>
                          </TD>
                          <TD>
                            <Badge variant={session.is_active ? "success" : "default"}>
                              {session.is_active ? "active" : "inactive"}
                            </Badge>
                          </TD>
                          <TD>
                            <ActionRow>
                              {selected ? (
                                <span className="px-1 text-sm font-medium">Selected</span>
                              ) : (
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  disabled={busy}
                                  onClick={() => pickSession(session.id, true)}
                                >
                                  Select
                                </Button>
                              )}
                              <Button
                                variant="ghost"
                                size="sm"
                                disabled={busy}
                                onClick={() =>
                                  updateSession.mutate({
                                    id: session.id,
                                    body: { is_active: !session.is_active },
                                  })
                                }
                              >
                                {flipping ? "Saving…" : session.is_active ? "Deactivate" : "Activate"}
                              </Button>
                              <Button
                                variant="ghost"
                                size="sm"
                                disabled={busy}
                                aria-expanded={editing}
                                aria-controls={
                                  editing ? `edit-session-${session.id}` : undefined
                                }
                                onClick={() => {
                                  if (!editing) startEditSession(session);
                                }}
                              >
                                Edit
                              </Button>
                              <Button
                                variant="ghost"
                                size="sm"
                                disabled={busy}
                                onClick={() =>
                                  askDelete({
                                    kind: "session",
                                    id: session.id,
                                    label: sessionLabel(session),
                                  })
                                }
                              >
                                Delete
                              </Button>
                            </ActionRow>
                          </TD>
                        </TR>
                        {editing ? (
                          <TableEditSheet colSpan={4}>
                            <form
                              id={`edit-session-${session.id}`}
                              className="min-w-0 space-y-3"
                              aria-label={`Edit ${sessionLabel(session)}`}
                              onSubmit={(event) => {
                                event.preventDefault();
                                if (
                                  busy ||
                                  !editSessionName.trim() ||
                                  !editSessionStart ||
                                  !editSessionEnd
                                ) {
                                  return;
                                }
                                clearError("session");
                                updateSession.mutate({
                                  id: session.id,
                                  body: {
                                    name: editSessionName.trim(),
                                    start_date: editSessionStart,
                                    end_date: editSessionEnd,
                                  },
                                });
                              }}
                            >
                              <div className={editGridClass}>
                                <div className="sm:col-span-2">
                                  <Label htmlFor={`edit-session-name-${session.id}`}>
                                    Session name
                                  </Label>
                                  <Input
                                    id={`edit-session-name-${session.id}`}
                                    className="min-w-0"
                                    value={editSessionName}
                                    onChange={(event) => setEditSessionName(event.target.value)}
                                    aria-invalid={Boolean(sessionEdit?.fields.name) || undefined}
                                    aria-describedby={
                                      sessionEdit?.fields.name
                                        ? `edit-session-name-error-${session.id}`
                                        : undefined
                                    }
                                  />
                                  <FieldError
                                    id={`edit-session-name-error-${session.id}`}
                                    message={sessionEdit?.fields.name}
                                    live={loneField(sessionEdit, "name")}
                                  />
                                </div>
                                <div>
                                  <Label htmlFor={`edit-session-start-${session.id}`}>Start</Label>
                                  <Input
                                    id={`edit-session-start-${session.id}`}
                                    className="min-w-0"
                                    type="date"
                                    value={editSessionStart}
                                    onChange={(event) => setEditSessionStart(event.target.value)}
                                    aria-invalid={
                                      Boolean(sessionEdit?.fields.start_date) || undefined
                                    }
                                    aria-describedby={
                                      sessionEdit?.fields.start_date
                                        ? `edit-session-start-error-${session.id}`
                                        : undefined
                                    }
                                  />
                                  <FieldError
                                    id={`edit-session-start-error-${session.id}`}
                                    message={sessionEdit?.fields.start_date}
                                    live={loneField(sessionEdit, "start_date")}
                                  />
                                </div>
                                <div>
                                  <Label htmlFor={`edit-session-end-${session.id}`}>End</Label>
                                  <Input
                                    id={`edit-session-end-${session.id}`}
                                    className="min-w-0"
                                    type="date"
                                    value={editSessionEnd}
                                    onChange={(event) => setEditSessionEnd(event.target.value)}
                                    aria-invalid={
                                      Boolean(sessionEdit?.fields.end_date) || undefined
                                    }
                                    aria-describedby={
                                      sessionEdit?.fields.end_date
                                        ? `edit-session-end-error-${session.id}`
                                        : undefined
                                    }
                                  />
                                  <FieldError
                                    id={`edit-session-end-error-${session.id}`}
                                    message={sessionEdit?.fields.end_date}
                                    live={loneField(sessionEdit, "end_date")}
                                  />
                                </div>
                              </div>
                              {sessionEdit?.message ? (
                                <FormAlert>{sessionEdit.message}</FormAlert>
                              ) : null}
                              <ActionRow>
                                <Button
                                  type="submit"
                                  size="sm"
                                  className={saveActionClass}
                                  disabled={
                                    busy ||
                                    !editSessionName.trim() ||
                                    !editSessionStart ||
                                    !editSessionEnd
                                  }
                                >
                                  {savingForm ? "Saving…" : "Save"}
                                </Button>
                                <Button
                                  type="button"
                                  variant="ghost"
                                  size="sm"
                                  onClick={() => setEditingSessionId(null)}
                                >
                                  Cancel
                                </Button>
                              </ActionRow>
                            </form>
                          </TableEditSheet>
                        ) : null}
                      </Fragment>
                    );
                  })}
                </TBody>
              </Table>
            ) : null}
          </section>

          <section
            className="space-y-4 border-t border-dashed border-rule pt-10"
            aria-labelledby="academics-terms"
            aria-busy={terms.isPending}
          >
            <div className="space-y-1">
              <h2 id="academics-terms" className="text-lg font-bold">
                Terms
              </h2>
              <p className="max-w-2xl text-sm leading-relaxed text-ink/70">
                Add 1st, then 2nd, then 3rd on the selected session. The current term is what Fees and Attendance use. Marking one current turns the others off.
              </p>
            </div>
            {termSection?.message ? <FormAlert>{termSection.message}</FormAlert> : null}
            {terms.isError ? <FormAlert>{LOAD_COPY.terms}</FormAlert> : null}
            {terms.isSuccess ? (
              <p className="text-sm text-ink">
                {activeTerms.length === 0 || !markedCurrent
                  ? "No term is current yet."
                  : activeTerms.length > 1
                    ? `Fees and Attendance are using ${termHeading(markedCurrent, sessionList)} until you choose a single current term.`
                    : `Current term: ${termHeading(markedCurrent, sessionList)}.`}
              </p>
            ) : null}
            <form onSubmit={submitTerm}>
              <fieldset
                disabled={terms.isError}
                className="m-0 space-y-3 border-0 p-0 [min-inline-size:0]"
              >
              <div className="grid min-w-0 gap-3 sm:grid-cols-2 [&>*]:min-w-0">
                <div>
                  <Label htmlFor="term-session">Session</Label>
                  <Select
                    id="term-session"
                    className="min-w-0"
                    value={termSession}
                    onChange={(event) => pickSession(event.target.value, false)}
                    disabled={sessionList.length === 0}
                    aria-invalid={Boolean(termCreate?.fields.session) || undefined}
                    aria-describedby={termCreate?.fields.session ? "term-session-error" : undefined}
                  >
                    {!termSession ? <option value="">Select a session</option> : null}
                    {sessionList.map((session) => (
                      <option key={session.id} value={session.id}>
                        {session.name}
                      </option>
                    ))}
                  </Select>
                  <FieldError
                    id="term-session-error"
                    message={termCreate?.fields.session}
                    live={loneField(termCreate, "session")}
                  />
                </div>
                <div>
                  <Label htmlFor="term-name">Term name</Label>
                  <Select
                    id="term-name"
                    className="min-w-0"
                    value={termName}
                    onChange={(event) => {
                      const value = event.target.value;
                      if (isTermName(value)) setTermName(value);
                    }}
                    disabled={!termSession}
                    aria-invalid={Boolean(termCreate?.fields.name) || undefined}
                    aria-describedby={
                      [
                        termNameTaken ? "term-name-taken" : null,
                        termCreate?.fields.name ? "term-name-error" : null,
                      ]
                        .filter(Boolean)
                        .join(" ") || undefined
                    }
                  >
                    {TERM_NAMES.map((name) => {
                      const taken = selectedTerms.some((term) => term.name === name);
                      return (
                        <option key={name} value={name}>
                          {taken ? `${name} already added` : name}
                        </option>
                      );
                    })}
                  </Select>
                  <FieldError
                    id="term-name-error"
                    message={termCreate?.fields.name}
                    live={loneField(termCreate, "name")}
                  />
                </div>
                <div>
                  <Label htmlFor="term-start">Start</Label>
                  <Input
                    id="term-start"
                    ref={termStartRef}
                    className="min-w-0"
                    type="date"
                    value={termStart}
                    onChange={(event) => setTermStart(event.target.value)}
                    disabled={!termSession}
                    aria-invalid={Boolean(termCreate?.fields.start_date) || undefined}
                    aria-describedby={
                      termCreate?.fields.start_date ? "term-start-error" : undefined
                    }
                  />
                  <FieldError
                    id="term-start-error"
                    message={termCreate?.fields.start_date}
                    live={loneField(termCreate, "start_date")}
                  />
                </div>
                <div>
                  <Label htmlFor="term-end">End</Label>
                  <Input
                    id="term-end"
                    className="min-w-0"
                    type="date"
                    value={termEnd}
                    onChange={(event) => setTermEnd(event.target.value)}
                    disabled={!termSession}
                    aria-invalid={Boolean(termCreate?.fields.end_date) || undefined}
                    aria-describedby={termCreate?.fields.end_date ? "term-end-error" : undefined}
                  />
                  <FieldError
                    id="term-end-error"
                    message={termCreate?.fields.end_date}
                    live={loneField(termCreate, "end_date")}
                  />
                </div>
                <div>
                  <Label htmlFor="term-days">School days</Label>
                  <Input
                    id="term-days"
                    className="min-w-0"
                    inputMode="numeric"
                    value={schoolDays}
                    onChange={(event) => setSchoolDays(event.target.value)}
                    disabled={!termSession}
                    aria-invalid={Boolean(termCreate?.fields.total_school_days) || undefined}
                    aria-describedby={
                      [
                        "term-days-help",
                        termCreate?.fields.total_school_days ? "term-days-error" : null,
                      ]
                        .filter(Boolean)
                        .join(" ")
                    }
                  />
                  <p id="term-days-help" className="mt-1.5 max-w-2xl text-sm text-ink">
                    {SCHOOL_DAYS_HELP}
                  </p>
                  <FieldError
                    id="term-days-error"
                    message={termCreate?.fields.total_school_days}
                    live={loneField(termCreate, "total_school_days")}
                  />
                </div>
              </div>
              {termNameTaken ? (
                <p id="term-name-taken" className="text-sm text-ink/70">
                  {termName} is already on {selectedSession?.name ?? "this session"}.
                </p>
              ) : null}
              {termDatesInvalid ? (
                <FormAlert>End date must be on or after the start date.</FormAlert>
              ) : null}
              {schoolDaysInvalid ? (
                <FormAlert>School days must be a whole number.</FormAlert>
              ) : null}
              {termCreate?.message ? <FormAlert>{termCreate.message}</FormAlert> : null}
              {!termSession && sessions.isSuccess ? (
                <p className="text-sm text-ink/70">Add or select a session before adding terms.</p>
              ) : null}
              {termSession && !nextTermName(termSession, termList) ? (
                <p className="text-sm text-ink/70">
                  {selectedSession?.name ?? "This session"} already has 1st, 2nd, and 3rd.
                </p>
              ) : null}
              <Button
                type="submit"
                size="sm"
                className={addActionClass}
                disabled={
                  terms.isError ||
                  !termSession ||
                  !termStart ||
                  !termEnd ||
                  termDatesInvalid ||
                  termNameTaken ||
                  schoolDaysInvalid ||
                  createTerm.isPending
                }
              >
                {createTerm.isPending ? "Adding…" : `Add ${termName}`}
              </Button>
              </fieldset>
            </form>
            {terms.isPending ? <p className="text-sm text-ink/70">Loading…</p> : null}
            {termSession && terms.isSuccess && selectedTerms.length === 0 ? (
              <EmptyState
                headline={`${selectedSession?.name ?? "This session"} has no terms`}
                body={`Add 1st, then 2nd, then 3rd on ${selectedSession?.name ?? "the selected session"}.`}
                aside="Fees and Attendance follow the current term."
              />
            ) : null}
            {selectedTerms.length > 0 ? (
              <Table>
                <THead>
                  <TR>
                    <TH>Term</TH>
                    <TH>Dates</TH>
                    <TH>Current</TH>
                    <TH>Actions</TH>
                  </TR>
                </THead>
                <TBody>
                  {selectedTerms.map((term) => {
                    const editing = editingTermId === term.id;
                    const sole = Boolean(term.is_active) && activeTerms.length === 1;
                    const daysHelpId = `edit-term-days-help-${term.id}`;
                    const busy = recordBusy("term", term.id);
                    const savingForm =
                      updateTerm.isPending && updateTerm.variables?.id === term.id;
                    const marking =
                      makeCurrentTerm.isPending && makeCurrentTerm.variables?.id === term.id;
                    return (
                      <Fragment key={term.id}>
                        <TR>
                          <TD>
                            <div>
                              <div>{term.name}</div>
                              {term.total_school_days != null ? (
                                <div
                                  className="text-xs text-ink/70"
                                  style={{ fontFamily: "var(--font-mono)" }}
                                >
                                  {term.total_school_days} school days
                                </div>
                              ) : null}
                            </div>
                          </TD>
                          <TD>
                            <span className="text-sm" style={{ fontFamily: "var(--font-mono)" }}>
                              {dateRange(term.start_date, term.end_date)}
                            </span>
                          </TD>
                          <TD>
                            {term.is_active ? (
                              <Badge variant="success">Current</Badge>
                            ) : (
                              <span className="text-sm text-ink/70">—</span>
                            )}
                          </TD>
                          <TD>
                            <ActionRow>
                              {sole ? null : (
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  disabled={busy}
                                  onClick={() => makeCurrentTerm.mutate(term)}
                                >
                                  {marking ? "Saving…" : "Make current"}
                                </Button>
                              )}
                              <Button
                                variant="ghost"
                                size="sm"
                                disabled={busy}
                                aria-expanded={editing}
                                aria-controls={editing ? `edit-term-${term.id}` : undefined}
                                onClick={() => {
                                  if (!editing) startEditTerm(term);
                                }}
                              >
                                Edit
                              </Button>
                              <Button
                                variant="ghost"
                                size="sm"
                                disabled={busy}
                                onClick={() =>
                                  askDelete({
                                    kind: "term",
                                    id: term.id,
                                    label: termLabel(term),
                                  })
                                }
                              >
                                Delete
                              </Button>
                            </ActionRow>
                          </TD>
                        </TR>
                        {editing ? (
                          <TableEditSheet colSpan={4}>
                            <form
                              id={`edit-term-${term.id}`}
                              className="min-w-0 space-y-3"
                              aria-label={`Edit ${termLabel(term)}`}
                              onSubmit={(event) => {
                                event.preventDefault();
                                if (
                                  busy ||
                                  !editTermSession ||
                                  !editTermName ||
                                  !editTermStart ||
                                  !editTermEnd
                                ) {
                                  return;
                                }
                                clearError("term");
                                updateTerm.mutate({
                                  id: term.id,
                                  body: {
                                    session: editTermSession,
                                    name: editTermName,
                                    start_date: editTermStart,
                                    end_date: editTermEnd,
                                    ...(editSchoolDays.trim()
                                      ? { total_school_days: Number(editSchoolDays) }
                                      : {}),
                                  },
                                });
                              }}
                            >
                              <div className={editGridClass}>
                                <div>
                                  <Label htmlFor={`edit-term-session-${term.id}`}>Session</Label>
                                  <Select
                                    id={`edit-term-session-${term.id}`}
                                    className="min-w-0"
                                    value={editTermSession}
                                    onChange={(event) => setEditTermSession(event.target.value)}
                                    aria-invalid={Boolean(termEdit?.fields.session) || undefined}
                                    aria-describedby={
                                      termEdit?.fields.session
                                        ? `edit-term-session-error-${term.id}`
                                        : undefined
                                    }
                                  >
                                    {sessionList.map((session) => (
                                      <option key={session.id} value={session.id}>
                                        {session.name}
                                      </option>
                                    ))}
                                  </Select>
                                  <FieldError
                                    id={`edit-term-session-error-${term.id}`}
                                    message={termEdit?.fields.session}
                                    live={loneField(termEdit, "session")}
                                  />
                                </div>
                                <div>
                                  <Label htmlFor={`edit-term-name-${term.id}`}>Term name</Label>
                                  <Select
                                    id={`edit-term-name-${term.id}`}
                                    className="min-w-0"
                                    value={editTermName}
                                    onChange={(event) => setEditTermName(event.target.value)}
                                    aria-invalid={Boolean(termEdit?.fields.name) || undefined}
                                    aria-describedby={
                                      termEdit?.fields.name
                                        ? `edit-term-name-error-${term.id}`
                                        : undefined
                                    }
                                  >
                                    {TERM_NAMES.map((name) => (
                                      <option key={name} value={name}>
                                        {name}
                                      </option>
                                    ))}
                                  </Select>
                                  <FieldError
                                    id={`edit-term-name-error-${term.id}`}
                                    message={termEdit?.fields.name}
                                    live={loneField(termEdit, "name")}
                                  />
                                </div>
                                <div>
                                  <Label htmlFor={`edit-term-start-${term.id}`}>Start</Label>
                                  <Input
                                    id={`edit-term-start-${term.id}`}
                                    className="min-w-0"
                                    type="date"
                                    value={editTermStart}
                                    onChange={(event) => setEditTermStart(event.target.value)}
                                    aria-invalid={
                                      Boolean(termEdit?.fields.start_date) || undefined
                                    }
                                    aria-describedby={
                                      termEdit?.fields.start_date
                                        ? `edit-term-start-error-${term.id}`
                                        : undefined
                                    }
                                  />
                                  <FieldError
                                    id={`edit-term-start-error-${term.id}`}
                                    message={termEdit?.fields.start_date}
                                    live={loneField(termEdit, "start_date")}
                                  />
                                </div>
                                <div>
                                  <Label htmlFor={`edit-term-end-${term.id}`}>End</Label>
                                  <Input
                                    id={`edit-term-end-${term.id}`}
                                    className="min-w-0"
                                    type="date"
                                    value={editTermEnd}
                                    onChange={(event) => setEditTermEnd(event.target.value)}
                                    aria-invalid={Boolean(termEdit?.fields.end_date) || undefined}
                                    aria-describedby={
                                      termEdit?.fields.end_date
                                        ? `edit-term-end-error-${term.id}`
                                        : undefined
                                    }
                                  />
                                  <FieldError
                                    id={`edit-term-end-error-${term.id}`}
                                    message={termEdit?.fields.end_date}
                                    live={loneField(termEdit, "end_date")}
                                  />
                                </div>
                                <div>
                                  <Label htmlFor={`edit-term-days-${term.id}`}>School days</Label>
                                  <Input
                                    id={`edit-term-days-${term.id}`}
                                    className="min-w-0"
                                    inputMode="numeric"
                                    value={editSchoolDays}
                                    onChange={(event) => setEditSchoolDays(event.target.value)}
                                    aria-invalid={
                                      Boolean(termEdit?.fields.total_school_days) || undefined
                                    }
                                    aria-describedby={
                                      [
                                        daysHelpId,
                                        termEdit?.fields.total_school_days
                                          ? `edit-term-days-error-${term.id}`
                                          : null,
                                      ]
                                        .filter(Boolean)
                                        .join(" ")
                                    }
                                  />
                                  <p id={daysHelpId} className="mt-1.5 max-w-2xl text-sm text-ink">
                                    {SCHOOL_DAYS_HELP}
                                  </p>
                                  <FieldError
                                    id={`edit-term-days-error-${term.id}`}
                                    message={termEdit?.fields.total_school_days}
                                    live={loneField(termEdit, "total_school_days")}
                                  />
                                </div>
                              </div>
                              {termEdit?.message ? (
                                <FormAlert>{termEdit.message}</FormAlert>
                              ) : null}
                              <ActionRow>
                                <Button
                                  type="submit"
                                  size="sm"
                                  className={saveActionClass}
                                  disabled={
                                    busy ||
                                    !editTermSession ||
                                    !editTermName ||
                                    !editTermStart ||
                                    !editTermEnd
                                  }
                                >
                                  {savingForm ? "Saving…" : "Save"}
                                </Button>
                                <Button
                                  type="button"
                                  variant="ghost"
                                  size="sm"
                                  onClick={() => setEditingTermId(null)}
                                >
                                  Cancel
                                </Button>
                              </ActionRow>
                            </form>
                          </TableEditSheet>
                        ) : null}
                      </Fragment>
                    );
                  })}
                </TBody>
              </Table>
            ) : null}
          </section>

          <section
            className="space-y-4 border-t border-dashed border-rule pt-10"
            aria-labelledby="academics-classes"
            aria-busy={classesPending}
          >
            <div className="space-y-1">
              <h2 id="academics-classes" className="text-lg font-bold">
                Classes
              </h2>
              <p className="max-w-2xl text-sm leading-relaxed text-ink/70">
                A class is the level plus its arms. JSS1 with arm A is JSS1A. Adding a level selects it so you can add the arm next.
              </p>
            </div>
            {levels.isError ? <FormAlert>{LOAD_COPY.classes}</FormAlert> : null}
            {arms.isError ? <FormAlert>{LOAD_COPY.arms}</FormAlert> : null}
            <form onSubmit={submitLevel}>
              <fieldset
                disabled={levels.isError}
                className="m-0 space-y-3 border-0 p-0 [min-inline-size:0]"
              >
              <div className="flex flex-wrap items-end gap-3">
                <div className="min-w-0 w-full sm:min-w-48 sm:w-auto sm:flex-1">
                  <Label htmlFor="level-name">Class level name</Label>
                  <Input
                    id="level-name"
                    className="min-w-0"
                    value={levelName}
                    onChange={(event) => setLevelName(event.target.value)}
                    placeholder="JSS1"
                    autoComplete="off"
                    aria-invalid={Boolean(levelCreate?.fields.name) || undefined}
                    aria-describedby={levelCreate?.fields.name ? "level-name-error" : undefined}
                  />
                  <FieldError
                    id="level-name-error"
                    message={levelCreate?.fields.name}
                    live={loneField(levelCreate, "name")}
                  />
                </div>
                <Button
                  type="submit"
                  size="sm"
                  className={addActionClass}
                  disabled={levels.isError || !levelName.trim() || createLevel.isPending}
                >
                  {createLevel.isPending ? "Adding…" : "Add class"}
                </Button>
              </div>
              {levelCreate?.message ? <FormAlert>{levelCreate.message}</FormAlert> : null}
              </fieldset>
            </form>
            {classesPending ? <p className="text-sm text-ink/70">Loading…</p> : null}
            {levels.isSuccess && !arms.isPending && levelList.length === 0 ? (
              <EmptyState
                headline="No class exists yet"
                body="Add a level such as JSS1, then its arms (A, B) on that class."
                aside="Enrollment places each student on an arm."
              />
            ) : null}
            {!classesPending && levelList.length > 0 ? (
              <ul className="space-y-3">
                {levelList.map((level) => {
                  const selected = level.id === armLevel;
                  const editing = editingLevelId === level.id;
                  const levelArms = armList.filter((arm) => arm.class_level === level.id);
                  const busy = recordBusy("level", level.id);
                  const savingForm =
                    updateLevel.isPending && updateLevel.variables?.id === level.id;
                  return (
                    <li
                      key={level.id}
                      className={cn(
                        "rounded-[var(--radius-nb-sm)] border border-rule",
                        selected && "bg-paper-tint",
                      )}
                    >
                      <div className="flex flex-wrap items-center justify-between gap-2 px-3 py-3">
                        <div className="min-w-0 flex-1">
                          {editing ? (
                            <div className="min-w-0">
                              <Label htmlFor={`edit-level-name-${level.id}`}>Class level name</Label>
                              <Input
                                id={`edit-level-name-${level.id}`}
                                form={`edit-level-${level.id}`}
                                className="min-w-0"
                                value={editLevelName}
                                onChange={(event) => setEditLevelName(event.target.value)}
                                aria-invalid={Boolean(levelEdit?.fields.name) || undefined}
                                aria-describedby={
                                  levelEdit?.fields.name
                                    ? `edit-level-name-error-${level.id}`
                                    : undefined
                                }
                              />
                              <FieldError
                                id={`edit-level-name-error-${level.id}`}
                                message={levelEdit?.fields.name}
                                live={loneField(levelEdit, "name")}
                              />
                            </div>
                          ) : (
                            <button
                              type="button"
                              className="text-left text-base font-semibold"
                              aria-pressed={selected}
                              onClick={() => setArmLevel(level.id)}
                            >
                              {level.name}
                              {selected ? (
                                <span className="ml-2 text-sm font-medium text-ink/70">
                                  Selected
                                </span>
                              ) : null}
                            </button>
                          )}
                        </div>
                        {editing ? (
                          <form
                            id={`edit-level-${level.id}`}
                            className="space-y-2"
                            onSubmit={(event) => {
                              event.preventDefault();
                              if (busy || !editLevelName.trim()) return;
                              clearError("level");
                              updateLevel.mutate({
                                id: level.id,
                                body: { name: editLevelName.trim() },
                              });
                            }}
                          >
                            {levelEdit?.message ? <FormAlert>{levelEdit.message}</FormAlert> : null}
                            <ActionRow>
                              <Button
                                type="submit"
                                size="sm"
                                className={saveActionClass}
                                disabled={busy || !editLevelName.trim()}
                              >
                                {savingForm ? "Saving…" : "Save"}
                              </Button>
                              <Button
                                type="button"
                                variant="ghost"
                                size="sm"
                                onClick={() => setEditingLevelId(null)}
                              >
                                Cancel
                              </Button>
                            </ActionRow>
                          </form>
                        ) : (
                          <ActionRow>
                            <Button
                              variant="ghost"
                              size="sm"
                              disabled={busy}
                              onClick={() => startEditLevel(level)}
                            >
                              Edit
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              disabled={busy}
                              onClick={() =>
                                askDelete({
                                  kind: "level",
                                  id: level.id,
                                  label: levelLabel(level),
                                })
                              }
                            >
                              Delete
                            </Button>
                          </ActionRow>
                        )}
                      </div>
                      <ul className="border-t border-rule">
                        {levelArms.length === 0 ? (
                          <li className="px-3 py-2 text-sm text-ink/70">No arms yet.</li>
                        ) : (
                          levelArms.map((arm) => {
                            const editingArm = editingArmId === arm.id;
                            const busy = recordBusy("arm", arm.id);
                            const savingForm =
                              updateArm.isPending && updateArm.variables?.id === arm.id;
                            return (
                              <li
                                key={arm.id}
                                className="border-b border-rule last:border-b-0"
                              >
                                <div className="flex flex-wrap items-center justify-between gap-2 px-3 py-2">
                                  <span>
                                    <span className="text-ink/70">Arm </span>
                                    <span style={{ fontFamily: "var(--font-mono)" }}>{arm.name}</span>
                                  </span>
                                  <ActionRow>
                                    <Button
                                      variant="ghost"
                                      size="sm"
                                      disabled={busy}
                                      aria-expanded={editingArm}
                                      aria-controls={
                                        editingArm ? `edit-arm-${arm.id}` : undefined
                                      }
                                      onClick={() => {
                                        if (!editingArm) startEditArm(arm);
                                      }}
                                    >
                                      Edit
                                    </Button>
                                    <Button
                                      variant="ghost"
                                      size="sm"
                                      disabled={busy}
                                      onClick={() =>
                                        askDelete({
                                          kind: "arm",
                                          id: arm.id,
                                          label: armLabel(arm, levelList),
                                        })
                                      }
                                    >
                                      Delete
                                    </Button>
                                  </ActionRow>
                                </div>
                                {editingArm ? (
                                  <form
                                    id={`edit-arm-${arm.id}`}
                                    className="min-w-0 space-y-3 border-t border-rule bg-paper-field px-3 py-3"
                                    aria-label={`Edit ${armLabel(arm, levelList)}`}
                                    onSubmit={(event) => {
                                      event.preventDefault();
                                      if (busy || !editArmLevel || !editArmName.trim()) {
                                        return;
                                      }
                                      clearError("arm");
                                      updateArm.mutate({
                                        id: arm.id,
                                        body: {
                                          class_level: editArmLevel,
                                          name: editArmName.trim(),
                                        },
                                      });
                                    }}
                                  >
                                    <div className={editGridClass}>
                                      <div>
                                        <Label htmlFor={`edit-arm-level-${arm.id}`}>
                                          Class level
                                        </Label>
                                        <Select
                                          id={`edit-arm-level-${arm.id}`}
                                          className="min-w-0"
                                          value={editArmLevel}
                                          onChange={(event) => setEditArmLevel(event.target.value)}
                                          aria-invalid={
                                            Boolean(armEdit?.fields.class_level) || undefined
                                          }
                                          aria-describedby={
                                            armEdit?.fields.class_level
                                              ? `edit-arm-level-error-${arm.id}`
                                              : undefined
                                          }
                                        >
                                          {levelList.map((option) => (
                                            <option key={option.id} value={option.id}>
                                              {option.name}
                                            </option>
                                          ))}
                                        </Select>
                                        <FieldError
                                          id={`edit-arm-level-error-${arm.id}`}
                                          message={armEdit?.fields.class_level}
                                          live={loneField(armEdit, "class_level")}
                                        />
                                      </div>
                                      <div>
                                        <Label htmlFor={`edit-arm-name-${arm.id}`}>Arm name</Label>
                                        <Input
                                          id={`edit-arm-name-${arm.id}`}
                                          className="min-w-0"
                                          value={editArmName}
                                          onChange={(event) => setEditArmName(event.target.value)}
                                          aria-invalid={Boolean(armEdit?.fields.name) || undefined}
                                          aria-describedby={
                                            armEdit?.fields.name
                                              ? `edit-arm-name-error-${arm.id}`
                                              : undefined
                                          }
                                        />
                                        <FieldError
                                          id={`edit-arm-name-error-${arm.id}`}
                                          message={armEdit?.fields.name}
                                          live={loneField(armEdit, "name")}
                                        />
                                      </div>
                                    </div>
                                    {armEdit?.message ? (
                                      <FormAlert>{armEdit.message}</FormAlert>
                                    ) : null}
                                    <ActionRow>
                                      <Button
                                        type="submit"
                                        size="sm"
                                        className={saveActionClass}
                                        disabled={busy || !editArmLevel || !editArmName.trim()}
                                      >
                                        {savingForm ? "Saving…" : "Save"}
                                      </Button>
                                      <Button
                                        type="button"
                                        variant="ghost"
                                        size="sm"
                                        onClick={() => setEditingArmId(null)}
                                      >
                                        Cancel
                                      </Button>
                                    </ActionRow>
                                  </form>
                                ) : null}
                              </li>
                            );
                          })
                        )}
                      </ul>
                      {selected ? (
                        <form className="border-t border-rule px-3 py-3" onSubmit={submitArm}>
                          <fieldset
                            disabled={arms.isError}
                            className="m-0 border-0 p-0 [min-inline-size:0]"
                          >
                          <div className="flex flex-wrap items-end gap-3">
                            <div className="min-w-0 w-full sm:min-w-48 sm:w-auto sm:flex-1">
                              <Label htmlFor={`arm-name-${level.id}`}>
                                Arm name for {level.name}
                              </Label>
                              <Input
                                id={`arm-name-${level.id}`}
                                ref={armNameRef}
                                className="min-w-0"
                                value={armName}
                                onChange={(event) => setArmName(event.target.value)}
                                placeholder="A"
                                autoComplete="off"
                                aria-invalid={
                                  Boolean(armCreate?.fields.name || armCreate?.fields.class_level) ||
                                  undefined
                                }
                                aria-describedby={
                                  [
                                    armCreate?.fields.name ? "arm-name-error" : null,
                                    armCreate?.fields.class_level ? "arm-level-error" : null,
                                  ]
                                    .filter(Boolean)
                                    .join(" ") || undefined
                                }
                              />
                              <FieldError
                                id="arm-name-error"
                                message={armCreate?.fields.name}
                                live={loneField(armCreate, "name")}
                              />
                              <FieldError
                                id="arm-level-error"
                                message={armCreate?.fields.class_level}
                                live={loneField(armCreate, "class_level")}
                              />
                            </div>
                            <Button
                              type="submit"
                              size="sm"
                              className={addActionClass}
                              disabled={
                                arms.isError ||
                                !armName.trim() ||
                                armNameTaken ||
                                createArm.isPending
                              }
                            >
                              {createArm.isPending ? "Adding…" : "Add arm"}
                            </Button>
                          </div>
                          {armNameTaken ? (
                            <p className="mt-2 text-sm text-ink/70">
                              {armName.trim()} is already on {level.name}.
                            </p>
                          ) : null}
                          {armCreate?.message ? (
                            <div className="mt-2">
                              <FormAlert>{armCreate.message}</FormAlert>
                            </div>
                          ) : null}
                          </fieldset>
                        </form>
                      ) : null}
                    </li>
                  );
                })}
              </ul>
            ) : null}
          </section>

          <section
            className="space-y-4 border-t border-dashed border-rule pt-10"
            aria-labelledby="academics-subjects"
            aria-busy={subjects.isPending}
          >
            <div className="space-y-1">
              <h2 id="academics-subjects" className="text-lg font-bold">
                Subjects
              </h2>
              <p className="max-w-2xl text-sm leading-relaxed text-ink/70">
                Each subject needs a code and a name.
              </p>
            </div>
            {subjects.isError ? <FormAlert>{LOAD_COPY.subjects}</FormAlert> : null}
            <form onSubmit={submitSubject}>
              <fieldset
                disabled={subjects.isError}
                className="m-0 space-y-3 border-0 p-0 [min-inline-size:0]"
              >
              <div className="grid min-w-0 gap-3 sm:grid-cols-3 [&>*]:min-w-0">
                <div>
                  <Label htmlFor="subject-code">Subject code</Label>
                  <Input
                    id="subject-code"
                    className="min-w-0"
                    value={subjectCode}
                    onChange={(event) => setSubjectCode(event.target.value)}
                    autoComplete="off"
                    style={{ fontFamily: "var(--font-mono)" }}
                    aria-invalid={Boolean(subjectCreate?.fields.code) || undefined}
                    aria-describedby={
                      subjectCreate?.fields.code ? "subject-code-error" : undefined
                    }
                  />
                  <FieldError
                    id="subject-code-error"
                    message={subjectCreate?.fields.code}
                    live={loneField(subjectCreate, "code")}
                  />
                </div>
                <div className="sm:col-span-2">
                  <Label htmlFor="subject-name">Subject name</Label>
                  <Input
                    id="subject-name"
                    className="min-w-0"
                    value={subjectName}
                    onChange={(event) => setSubjectName(event.target.value)}
                    autoComplete="off"
                    aria-invalid={Boolean(subjectCreate?.fields.name) || undefined}
                    aria-describedby={
                      subjectCreate?.fields.name ? "subject-name-error" : undefined
                    }
                  />
                  <FieldError
                    id="subject-name-error"
                    message={subjectCreate?.fields.name}
                    live={loneField(subjectCreate, "name")}
                  />
                </div>
              </div>
              {subjectCreate?.message ? <FormAlert>{subjectCreate.message}</FormAlert> : null}
              <Button
                type="submit"
                size="sm"
                className={addActionClass}
                disabled={
                  subjects.isError ||
                  !subjectCode.trim() ||
                  !subjectName.trim() ||
                  createSubject.isPending
                }
              >
                {createSubject.isPending ? "Adding…" : "Add subject"}
              </Button>
              </fieldset>
            </form>
            {subjects.isPending ? <p className="text-sm text-ink/70">Loading…</p> : null}
            {subjects.isSuccess && subjectList.length === 0 ? (
              <EmptyState
                headline="No subject exists yet"
                body="Add a code and a name, for example MTH and Mathematics."
                aside="Results list the code next to the subject name."
              />
            ) : null}
            {subjectList.length > 0 ? (
              <Table>
                <THead>
                  <TR>
                    <TH>Code</TH>
                    <TH>Name</TH>
                    <TH>Actions</TH>
                  </TR>
                </THead>
                <TBody>
                  {subjectList.map((subject) => {
                    const editing = editingSubjectId === subject.id;
                    const busy = recordBusy("subject", subject.id);
                    const savingForm =
                      updateSubject.isPending && updateSubject.variables?.id === subject.id;
                    return (
                      <Fragment key={subject.id}>
                        <TR>
                          <TD>
                            <span style={{ fontFamily: "var(--font-mono)" }}>{subject.code}</span>
                          </TD>
                          <TD>{subject.name}</TD>
                          <TD>
                            <ActionRow>
                              <Button
                                variant="ghost"
                                size="sm"
                                disabled={busy}
                                aria-expanded={editing}
                                aria-controls={
                                  editing ? `edit-subject-${subject.id}` : undefined
                                }
                                onClick={() => {
                                  if (!editing) startEditSubject(subject);
                                }}
                              >
                                Edit
                              </Button>
                              <Button
                                variant="ghost"
                                size="sm"
                                disabled={busy}
                                onClick={() =>
                                  askDelete({
                                    kind: "subject",
                                    id: subject.id,
                                    label: subjectLabel(subject),
                                  })
                                }
                              >
                                Delete
                              </Button>
                            </ActionRow>
                          </TD>
                        </TR>
                        {editing ? (
                          <TableEditSheet colSpan={3}>
                            <form
                              id={`edit-subject-${subject.id}`}
                              className="min-w-0 space-y-3"
                              aria-label={`Edit ${subjectLabel(subject)}`}
                              onSubmit={(event) => {
                                event.preventDefault();
                                if (busy || !editSubjectName.trim() || !editSubjectCode.trim()) {
                                  return;
                                }
                                clearError("subject");
                                updateSubject.mutate({
                                  id: subject.id,
                                  body: {
                                    name: editSubjectName.trim(),
                                    code: editSubjectCode.trim(),
                                  },
                                });
                              }}
                            >
                              <div className="grid min-w-0 gap-3 sm:grid-cols-3 [&>*]:min-w-0">
                                <div>
                                  <Label htmlFor={`edit-subject-code-${subject.id}`}>
                                    Subject code
                                  </Label>
                                  <Input
                                    id={`edit-subject-code-${subject.id}`}
                                    className="min-w-0"
                                    value={editSubjectCode}
                                    onChange={(event) => setEditSubjectCode(event.target.value)}
                                    style={{ fontFamily: "var(--font-mono)" }}
                                    aria-invalid={Boolean(subjectEdit?.fields.code) || undefined}
                                    aria-describedby={
                                      subjectEdit?.fields.code
                                        ? `edit-subject-code-error-${subject.id}`
                                        : undefined
                                    }
                                  />
                                  <FieldError
                                    id={`edit-subject-code-error-${subject.id}`}
                                    message={subjectEdit?.fields.code}
                                    live={loneField(subjectEdit, "code")}
                                  />
                                </div>
                                <div className="sm:col-span-2">
                                  <Label htmlFor={`edit-subject-name-${subject.id}`}>
                                    Subject name
                                  </Label>
                                  <Input
                                    id={`edit-subject-name-${subject.id}`}
                                    className="min-w-0"
                                    value={editSubjectName}
                                    onChange={(event) => setEditSubjectName(event.target.value)}
                                    aria-invalid={Boolean(subjectEdit?.fields.name) || undefined}
                                    aria-describedby={
                                      subjectEdit?.fields.name
                                        ? `edit-subject-name-error-${subject.id}`
                                        : undefined
                                    }
                                  />
                                  <FieldError
                                    id={`edit-subject-name-error-${subject.id}`}
                                    message={subjectEdit?.fields.name}
                                    live={loneField(subjectEdit, "name")}
                                  />
                                </div>
                              </div>
                              {subjectEdit?.message ? (
                                <FormAlert>{subjectEdit.message}</FormAlert>
                              ) : null}
                              <ActionRow>
                                <Button
                                  type="submit"
                                  size="sm"
                                  className={saveActionClass}
                                  disabled={
                                    busy || !editSubjectName.trim() || !editSubjectCode.trim()
                                  }
                                >
                                  {savingForm ? "Saving…" : "Save"}
                                </Button>
                                <Button
                                  type="button"
                                  variant="ghost"
                                  size="sm"
                                  onClick={() => setEditingSubjectId(null)}
                                >
                                  Cancel
                                </Button>
                              </ActionRow>
                            </form>
                          </TableEditSheet>
                        ) : null}
                      </Fragment>
                    );
                  })}
                </TBody>
              </Table>
            ) : null}
          </section>
        </CardBody>
      </Card>

      <ConfirmDeleteModal
        open={Boolean(pendingDelete)}
        onClose={() => {
          setPendingDelete(null);
          setDeleteError(null);
        }}
        onConfirm={() => {
          if (pendingDelete) removeMutation.mutate(pendingDelete);
        }}
        title={pendingDelete ? `Delete ${pendingDelete.label}?` : "Delete?"}
        description="This cannot be undone."
        error={deleteError}
        pending={removeMutation.isPending}
      />
    </div>
  );
}
