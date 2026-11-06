"use client";

import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Badge,
  Button,
  Card,
  CardBody,
  CardHeader,
  CardTitle,
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
import { ConfirmDeleteModal, Toast } from "@/components/ui/client";
import {
  academicsApi,
  type ClassLevel,
  type ClassSubjectAssignment,
  type Subject,
  type Term,
} from "@/lib/api/academics";
import {
  assessmentApi,
  type AssessmentComponent,
} from "@/lib/api/assessment";
import { formatApiError } from "@/lib/api/errors";

type DraftRow = {
  key: string;
  name: string;
  weight: string;
  maxScore: string;
};

type Scope = {
  subject: string;
  class_level: string;
  term: string;
};

type SchemeGroup = {
  key: string;
  subject: string;
  class_level: string;
  term: string;
  subject_name: string;
  class_level_name: string;
  term_name: string;
  count: number;
  weight: number;
};

const STANDARD_SCHEME: Omit<DraftRow, "key">[] = [
  { name: "1st CA", weight: "20", maxScore: "100" },
  { name: "2nd CA", weight: "20", maxScore: "100" },
  { name: "Exam", weight: "60", maxScore: "100" },
];

function newKey() {
  return crypto.randomUUID();
}

function standardDraft(): DraftRow[] {
  return STANDARD_SCHEME.map((row) => ({ ...row, key: newKey() }));
}

function fromComponents(components: AssessmentComponent[]): DraftRow[] {
  if (!components.length) return standardDraft();
  return components.map((c) => ({
    key: c.id,
    name: c.name,
    weight: String(c.weight_percentage),
    maxScore: c.max_score != null ? String(c.max_score) : "100",
  }));
}

function parseAmount(value: string): number {
  const n = Number(value);
  if (!Number.isFinite(n)) return 0;
  return Math.round(n * 100) / 100;
}

function sumWeights(rows: { weight: string }[]): number {
  return Math.round(rows.reduce((total, row) => total + parseAmount(row.weight), 0) * 100) / 100;
}

function formatWeight(value: string | number | undefined): string {
  if (value == null || value === "") return "—";
  const n = Number(value);
  if (!Number.isFinite(n)) return String(value);
  return Number.isInteger(n) ? String(n) : n.toFixed(2);
}

function termOptionLabel(term: Term, sessionNames: Map<string, string>) {
  const sessionName = term.session_name || sessionNames.get(term.session);
  return sessionName ? `${term.name} · ${sessionName}` : term.name;
}

function subjectOptionLabel(subject: Subject) {
  return subject.code ? `${subject.code} — ${subject.name}` : subject.name;
}

function assignmentLabel(assignment: ClassSubjectAssignment): string {
  const subject = assignment.subject_name || assignment.subject;
  const klass = [assignment.class_level_name, assignment.arm_name]
    .filter(Boolean)
    .join(" ");
  const term = assignment.term_name || assignment.term;
  const teacher = assignment.teacher_email;
  return [subject, klass, term, teacher].filter(Boolean).join(" · ");
}

function schemeKey(scope: Scope) {
  return `${scope.subject}|${scope.class_level}|${scope.term}`;
}

function groupSchemes(components: AssessmentComponent[]): SchemeGroup[] {
  const groups = new Map<string, SchemeGroup>();
  for (const c of components) {
    if (!c.subject || !c.class_level || !c.term) continue;
    const key = schemeKey({
      subject: c.subject,
      class_level: c.class_level,
      term: c.term,
    });
    const existing = groups.get(key);
    const weight = parseAmount(String(c.weight_percentage ?? 0));
    if (existing) {
      existing.count += 1;
      existing.weight =
        Math.round((existing.weight + weight) * 100) / 100;
      continue;
    }
    groups.set(key, {
      key,
      subject: c.subject,
      class_level: c.class_level,
      term: c.term,
      subject_name: c.subject_name || c.subject_code || "Subject",
      class_level_name: c.class_level_name || "Class",
      term_name: c.term_name || "Term",
      count: 1,
      weight,
    });
  }
  return [...groups.values()].sort((a, b) => {
    const byClass = a.class_level_name.localeCompare(b.class_level_name);
    if (byClass !== 0) return byClass;
    const bySubject = a.subject_name.localeCompare(b.subject_name);
    if (bySubject !== 0) return bySubject;
    return a.term_name.localeCompare(b.term_name);
  });
}

export default function AdminAssessmentSchemePage() {
  const qc = useQueryClient();
  const levels = useQuery({
    queryKey: ["academics", "class-levels"],
    queryFn: () => academicsApi.classLevels.list(),
  });
  const subjects = useQuery({
    queryKey: ["academics", "subjects"],
    queryFn: () => academicsApi.subjects.list(),
  });
  const terms = useQuery({
    queryKey: ["academics", "terms"],
    queryFn: () => academicsApi.terms.list(),
  });
  const sessions = useQuery({
    queryKey: ["academics", "sessions"],
    queryFn: () => academicsApi.sessions.list(),
  });
  const assignments = useQuery({
    queryKey: ["academics", "class-subject-assignments"],
    queryFn: () => academicsApi.classSubjectAssignments.list(),
  });
  const allComponents = useQuery({
    queryKey: ["assessment", "components"],
    queryFn: () => assessmentApi.components.list(),
  });

  const [classLevel, setClassLevel] = useState("");
  const [subject, setSubject] = useState("");
  const [term, setTerm] = useState("");
  const [assignmentId, setAssignmentId] = useState("");
  const [sourceClassLevel, setSourceClassLevel] = useState("");
  const [sourceSubject, setSourceSubject] = useState("");
  const [sourceTerm, setSourceTerm] = useState("");
  const [overwrite, setOverwrite] = useState(false);
  const [draft, setDraft] = useState<DraftRow[]>(standardDraft);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editName, setEditName] = useState("");
  const [editWeight, setEditWeight] = useState("");
  const [editMax, setEditMax] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [pendingDelete, setPendingDelete] = useState<AssessmentComponent | null>(
    null,
  );

  const scoped = Boolean(classLevel && subject && term);
  const components = useQuery({
    queryKey: ["assessment", "components", subject, classLevel, term],
    queryFn: () =>
      assessmentApi.components.list({
        subject,
        class_level: classLevel,
        term,
      }),
    enabled: scoped,
  });

  const sessionNames = useMemo(() => {
    return new Map((sessions.data ?? []).map((s) => [s.id, s.name]));
  }, [sessions.data]);

  const levelOptions = useMemo(() => {
    return [...(levels.data ?? [])].sort((a: ClassLevel, b: ClassLevel) => {
      const byOrder = (a.order ?? 0) - (b.order ?? 0);
      if (byOrder !== 0) return byOrder;
      return a.name.localeCompare(b.name);
    });
  }, [levels.data]);

  const subjectOptions = useMemo(() => {
    return [...(subjects.data ?? [])].sort((a, b) =>
      subjectOptionLabel(a).localeCompare(subjectOptionLabel(b)),
    );
  }, [subjects.data]);

  const currentRows = components.data ?? [];
  const currentTotal = useMemo(
    () =>
      Math.round(
        currentRows.reduce(
          (total, row) => total + parseAmount(String(row.weight_percentage ?? 0)),
          0,
        ) * 100,
      ) / 100,
    [currentRows],
  );
  const draftTotal = sumWeights(draft);
  const draftReady =
    scoped &&
    draft.length > 0 &&
    draft.every((row) => row.name.trim() && parseAmount(row.weight) > 0 && parseAmount(row.maxScore) > 0) &&
    draftTotal === 100;

  const existingSchemes = useMemo(
    () => groupSchemes(allComponents.data ?? []),
    [allComponents.data],
  );

  const catalogsLoading =
    levels.isLoading || subjects.isLoading || terms.isLoading;
  const catalogError = levels.error ?? subjects.error ?? terms.error;

  useEffect(() => {
    if (!scoped || components.isFetching) return;
    setDraft(fromComponents(components.data ?? []));
    setEditingId(null);
  }, [scoped, subject, classLevel, term, components.data, components.isFetching]);

  function applyAssignment(id: string) {
    setAssignmentId(id);
    const assignment = (assignments.data ?? []).find((a) => a.id === id);
    if (!assignment) return;
    setSubject(assignment.subject);
    setClassLevel(assignment.class_level);
    setTerm(assignment.term);
    setError(null);
  }

  function applyScope(next: Scope) {
    setSubject(next.subject);
    setClassLevel(next.class_level);
    setTerm(next.term);
    const match = (assignments.data ?? []).find(
      (a) =>
        a.subject === next.subject &&
        a.class_level === next.class_level &&
        a.term === next.term,
    );
    setAssignmentId(match?.id ?? "");
    setError(null);
  }

  function invalidateSchemes() {
    void qc.invalidateQueries({ queryKey: ["assessment", "components"] });
    void qc.invalidateQueries({ queryKey: ["assessment", "my-components"] });
  }

  const saveScheme = useMutation({
    mutationFn: () =>
      assessmentApi.setScheme({
        subject,
        class_level: classLevel,
        term,
        components: draft.map((row) => ({
          name: row.name.trim(),
          weight_percentage: row.weight,
          max_score: row.maxScore,
        })),
      }),
    onSuccess: (data) => {
      setError(null);
      setToast(
        data.count === 0
          ? "Scheme cleared."
          : `Scheme saved (${data.count} ${data.count === 1 ? "component" : "components"}).`,
      );
      invalidateSchemes();
    },
    onError: (err) => {
      setError(formatApiError(err, "Could not save scheme"));
    },
  });

  const clearScheme = useMutation({
    mutationFn: () =>
      assessmentApi.setScheme({
        subject,
        class_level: classLevel,
        term,
        components: [],
      }),
    onSuccess: () => {
      setError(null);
      setToast("Scheme cleared.");
      invalidateSchemes();
    },
    onError: (err) => {
      setError(formatApiError(err, "Could not clear scheme"));
    },
  });

  const clone = useMutation({
    mutationFn: () =>
      assessmentApi.cloneScheme({
        source_subject: sourceSubject,
        source_class_level: sourceClassLevel,
        source_term: sourceTerm,
        target_subject: subject,
        target_class_level: classLevel,
        target_term: term,
        overwrite,
      }),
    onSuccess: (data) => {
      setError(null);
      setToast(
        data.detail ||
          `Scheme cloned (${data.count} ${data.count === 1 ? "component" : "components"}).`,
      );
      invalidateSchemes();
    },
    onError: (err) => {
      setError(formatApiError(err, "Could not clone scheme"));
    },
  });

  const updateComponent = useMutation({
    mutationFn: () =>
      assessmentApi.components.update(editingId!, {
        name: editName.trim(),
        weight_percentage: editWeight,
        max_score: editMax,
      }),
    onSuccess: () => {
      setEditingId(null);
      setError(null);
      setToast("Component updated.");
      invalidateSchemes();
    },
    onError: (err) => {
      setError(formatApiError(err, "Could not update component"));
    },
  });

  const removeComponent = useMutation({
    mutationFn: (id: string) => assessmentApi.components.remove(id),
    onSuccess: () => {
      setPendingDelete(null);
      setError(null);
      setToast("Component deleted.");
      invalidateSchemes();
    },
    onError: (err) => {
      setPendingDelete(null);
      setError(formatApiError(err, "Could not delete component"));
    },
  });

  function startEdit(row: AssessmentComponent) {
    setEditingId(row.id);
    setEditName(row.name);
    setEditWeight(String(row.weight_percentage));
    setEditMax(row.max_score != null ? String(row.max_score) : "100");
    setError(null);
  }

  const cloneReady =
    scoped &&
    Boolean(sourceSubject && sourceClassLevel && sourceTerm) &&
    !(
      sourceSubject === subject &&
      sourceClassLevel === classLevel &&
      sourceTerm === term
    );

  const remainingAfterDelete = pendingDelete
    ? Math.round(
        (currentTotal - parseAmount(String(pendingDelete.weight_percentage ?? 0))) *
          100,
      ) / 100
    : 0;
  const deleteWouldBreakWeights =
    Boolean(pendingDelete) &&
    remainingAfterDelete !== 0 &&
    remainingAfterDelete !== 100;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Assessment scheme"
        description="Set CA and exam weights for a subject, class, and term. Teachers enter marks against this scheme."
      />

      {catalogError ? (
        <p className="text-sm text-danger">
          {formatApiError(catalogError, "Could not load classes and subjects.")}
        </p>
      ) : null}
      {error ? (
        <p className="text-sm text-danger" role="alert">
          {error}
        </p>
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle>Subject, class, and term</CardTitle>
        </CardHeader>
        <CardBody className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <div className="sm:col-span-2 lg:col-span-4">
            <Label htmlFor="scheme-assignment">Fill from assignment</Label>
            <Select
              id="scheme-assignment"
              value={assignmentId}
              disabled={assignments.isLoading}
              onChange={(event) => applyAssignment(event.target.value)}
            >
              <option value="">
                {assignments.isLoading
                  ? "Loading…"
                  : "Optional — pick a class–subject assignment"}
              </option>
              {(assignments.data ?? []).map((a) => (
                <option key={a.id} value={a.id}>
                  {assignmentLabel(a)}
                </option>
              ))}
            </Select>
            <p className="mt-1 text-xs text-ink/60">
              Schemes are per subject, class level, and term — not per arm.
            </p>
          </div>
          <div>
            <Label htmlFor="scheme-class-level">Class level</Label>
            <Select
              id="scheme-class-level"
              value={classLevel}
              disabled={catalogsLoading}
              onChange={(event) => {
                setClassLevel(event.target.value);
                setAssignmentId("");
              }}
            >
              <option value="">
                {catalogsLoading ? "Loading…" : "Select class level"}
              </option>
              {levelOptions.map((level) => (
                <option key={level.id} value={level.id}>
                  {level.name}
                </option>
              ))}
            </Select>
          </div>
          <div>
            <Label htmlFor="scheme-subject">Subject</Label>
            <Select
              id="scheme-subject"
              value={subject}
              disabled={catalogsLoading}
              onChange={(event) => {
                setSubject(event.target.value);
                setAssignmentId("");
              }}
            >
              <option value="">
                {catalogsLoading ? "Loading…" : "Select subject"}
              </option>
              {subjectOptions.map((item) => (
                <option key={item.id} value={item.id}>
                  {subjectOptionLabel(item)}
                </option>
              ))}
            </Select>
          </div>
          <div>
            <Label htmlFor="scheme-term">Term</Label>
            <Select
              id="scheme-term"
              value={term}
              disabled={catalogsLoading}
              onChange={(event) => {
                setTerm(event.target.value);
                setAssignmentId("");
              }}
            >
              <option value="">
                {catalogsLoading ? "Loading…" : "Select term"}
              </option>
              {(terms.data ?? []).map((item) => (
                <option key={item.id} value={item.id}>
                  {termOptionLabel(item, sessionNames)}
                </option>
              ))}
            </Select>
          </div>
        </CardBody>
      </Card>

      <Card>
        <CardHeader className="flex flex-wrap items-center justify-between gap-2">
          <CardTitle>Current components</CardTitle>
          {scoped && currentRows.length > 0 ? (
            <Badge variant={currentTotal === 100 ? "success" : "warning"}>
              {currentTotal === 100
                ? "Weights 100%"
                : `Weights ${formatWeight(currentTotal)}%`}
            </Badge>
          ) : null}
        </CardHeader>
        <CardBody className="p-0">
          {!scoped ? (
            <div className="p-4">
              <EmptyState
                headline="Pick a scheme"
                body="Choose class level, subject, and term to view or replace components."
              />
            </div>
          ) : components.isLoading ? (
            <p className="p-4 text-sm text-ink/70">Loading…</p>
          ) : components.isError ? (
            <p className="p-4 text-sm text-danger">
              {formatApiError(components.error, "Failed to load components")}
            </p>
          ) : currentRows.length === 0 ? (
            <div className="p-4">
              <EmptyState
                headline="No scheme yet"
                body="Save a 100% scheme below, or clone one from another subject or term. Teachers cannot enter marks until this exists."
              />
            </div>
          ) : (
            <Table>
              <THead>
                <TR>
                  <TH>Name</TH>
                  <TH>Weight %</TH>
                  <TH>Max score</TH>
                  <TH>Actions</TH>
                </TR>
              </THead>
              <TBody>
                {currentRows.map((row) => {
                  const editing = editingId === row.id;
                  return (
                    <TR key={row.id}>
                      <TD>
                        {editing ? (
                          <Input
                            value={editName}
                            onChange={(event) => setEditName(event.target.value)}
                            aria-label="Component name"
                          />
                        ) : (
                          row.name
                        )}
                      </TD>
                      <TD style={{ fontFamily: "var(--font-mono)" }}>
                        {editing ? (
                          <Input
                            type="number"
                            min="0.01"
                            step="0.01"
                            value={editWeight}
                            onChange={(event) => setEditWeight(event.target.value)}
                            aria-label="Weight percentage"
                          />
                        ) : (
                          formatWeight(row.weight_percentage)
                        )}
                      </TD>
                      <TD style={{ fontFamily: "var(--font-mono)" }}>
                        {editing ? (
                          <Input
                            type="number"
                            min="0.01"
                            step="0.01"
                            value={editMax}
                            onChange={(event) => setEditMax(event.target.value)}
                            aria-label="Max score"
                          />
                        ) : row.max_score != null ? (
                          String(row.max_score)
                        ) : (
                          "—"
                        )}
                      </TD>
                      <TD>
                        {editing ? (
                          <div className="flex flex-wrap gap-2">
                            <Button
                              size="sm"
                              disabled={
                                updateComponent.isPending || !editName.trim()
                              }
                              onClick={() => updateComponent.mutate()}
                            >
                              {updateComponent.isPending ? "Saving…" : "Save"}
                            </Button>
                            <Button
                              size="sm"
                              variant="ghost"
                              disabled={updateComponent.isPending}
                              onClick={() => setEditingId(null)}
                            >
                              Cancel
                            </Button>
                          </div>
                        ) : (
                          <div className="flex flex-wrap gap-2">
                            <Button
                              size="sm"
                              variant="ghost"
                              onClick={() => startEdit(row)}
                            >
                              Edit
                            </Button>
                            <Button
                              size="sm"
                              variant="ghost"
                              onClick={() => setPendingDelete(row)}
                            >
                              Delete
                            </Button>
                          </div>
                        )}
                      </TD>
                    </TR>
                  );
                })}
              </TBody>
            </Table>
          )}
        </CardBody>
        {scoped && currentRows.length > 0 ? (
          <CardBody className="space-y-3 border-t border-ink/10">
            <p className="text-sm text-ink/70">
              Deleting one piece is blocked unless the rest still total 100%, or
              this is the last component. To drop a CA or change the split, replace
              the whole scheme below.
            </p>
            <Button
              size="sm"
              variant="secondary"
              disabled={clearScheme.isPending || saveScheme.isPending}
              onClick={() => clearScheme.mutate()}
            >
              {clearScheme.isPending ? "Clearing…" : "Clear scheme"}
            </Button>
          </CardBody>
        ) : null}
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Set or replace scheme</CardTitle>
        </CardHeader>
        <CardBody className="space-y-4">
          <p className="text-sm text-ink/70">
            Replaces every component for this subject, class, and term in one
            save. Weights must sum to 100%.
          </p>
          <div className="flex flex-wrap gap-2">
            <Button
              size="sm"
              variant="secondary"
              disabled={!scoped}
              onClick={() => setDraft(standardDraft())}
            >
              Load 20 / 20 / 60
            </Button>
            <Button
              size="sm"
              variant="ghost"
              disabled={!scoped}
              onClick={() =>
                setDraft((rows) => [
                  ...rows,
                  { key: newKey(), name: "", weight: "", maxScore: "100" },
                ])
              }
            >
              Add component
            </Button>
          </div>
          <div className="overflow-x-auto">
            <Table>
              <THead>
                <TR>
                  <TH>Name</TH>
                  <TH>Weight %</TH>
                  <TH>Max score</TH>
                  <TH />
                </TR>
              </THead>
              <TBody>
                {draft.map((row) => (
                  <TR key={row.key}>
                    <TD>
                      <Input
                        value={row.name}
                        disabled={!scoped}
                        onChange={(event) =>
                          setDraft((rows) =>
                            rows.map((item) =>
                              item.key === row.key
                                ? { ...item, name: event.target.value }
                                : item,
                            ),
                          )
                        }
                        aria-label="Draft component name"
                      />
                    </TD>
                    <TD>
                      <Input
                        type="number"
                        min="0.01"
                        step="0.01"
                        value={row.weight}
                        disabled={!scoped}
                        onChange={(event) =>
                          setDraft((rows) =>
                            rows.map((item) =>
                              item.key === row.key
                                ? { ...item, weight: event.target.value }
                                : item,
                            ),
                          )
                        }
                        aria-label="Draft weight percentage"
                      />
                    </TD>
                    <TD>
                      <Input
                        type="number"
                        min="0.01"
                        step="0.01"
                        value={row.maxScore}
                        disabled={!scoped}
                        onChange={(event) =>
                          setDraft((rows) =>
                            rows.map((item) =>
                              item.key === row.key
                                ? { ...item, maxScore: event.target.value }
                                : item,
                            ),
                          )
                        }
                        aria-label="Draft max score"
                      />
                    </TD>
                    <TD>
                      <Button
                        size="sm"
                        variant="ghost"
                        disabled={!scoped || draft.length <= 1}
                        onClick={() =>
                          setDraft((rows) =>
                            rows.filter((item) => item.key !== row.key),
                          )
                        }
                      >
                        Remove
                      </Button>
                    </TD>
                  </TR>
                ))}
              </TBody>
            </Table>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <Button
              size="sm"
              disabled={!draftReady || saveScheme.isPending || catalogsLoading}
              onClick={() => saveScheme.mutate()}
            >
              {saveScheme.isPending ? "Saving…" : "Save scheme"}
            </Button>
            <p
              className={`text-sm ${draftTotal === 100 ? "text-ink/70" : "text-danger"}`}
              style={{ fontFamily: "var(--font-mono)" }}
            >
              Total {formatWeight(draftTotal)}%
              {draftTotal === 100 ? "" : " — must equal 100%"}
            </p>
          </div>
        </CardBody>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Clone from another scheme</CardTitle>
        </CardHeader>
        <CardBody className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4 lg:items-end">
          <div>
            <Label htmlFor="clone-class-level">Source class</Label>
            <Select
              id="clone-class-level"
              value={sourceClassLevel}
              disabled={!scoped || catalogsLoading}
              onChange={(event) => setSourceClassLevel(event.target.value)}
            >
              <option value="">Select class level</option>
              {levelOptions.map((level) => (
                <option key={level.id} value={level.id}>
                  {level.name}
                </option>
              ))}
            </Select>
          </div>
          <div>
            <Label htmlFor="clone-subject">Source subject</Label>
            <Select
              id="clone-subject"
              value={sourceSubject}
              disabled={!scoped || catalogsLoading}
              onChange={(event) => setSourceSubject(event.target.value)}
            >
              <option value="">Select subject</option>
              {subjectOptions.map((item) => (
                <option key={item.id} value={item.id}>
                  {subjectOptionLabel(item)}
                </option>
              ))}
            </Select>
          </div>
          <div>
            <Label htmlFor="clone-term">Source term</Label>
            <Select
              id="clone-term"
              value={sourceTerm}
              disabled={!scoped || catalogsLoading}
              onChange={(event) => setSourceTerm(event.target.value)}
            >
              <option value="">Select term</option>
              {(terms.data ?? []).map((item) => (
                <option key={item.id} value={item.id}>
                  {termOptionLabel(item, sessionNames)}
                </option>
              ))}
            </Select>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <label className="flex items-center gap-2 text-sm text-ink/80">
              <input
                type="checkbox"
                checked={overwrite}
                disabled={!scoped}
                onChange={(event) => setOverwrite(event.target.checked)}
              />
              Overwrite existing
            </label>
            <Button
              size="sm"
              disabled={!cloneReady || clone.isPending}
              onClick={() => clone.mutate()}
            >
              {clone.isPending ? "Cloning…" : "Clone scheme"}
            </Button>
          </div>
          <p className="text-sm text-ink/70 sm:col-span-2 lg:col-span-4">
            Copies names, weights, and max scores onto the scheme selected above.
            If the target already has components, tick overwrite.
          </p>
        </CardBody>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Existing schemes</CardTitle>
        </CardHeader>
        <CardBody className="p-0">
          {allComponents.isLoading ? (
            <p className="p-4 text-sm text-ink/70">Loading…</p>
          ) : allComponents.isError ? (
            <p className="p-4 text-sm text-danger">
              {formatApiError(allComponents.error, "Failed to load schemes")}
            </p>
          ) : existingSchemes.length === 0 ? (
            <div className="p-4">
              <EmptyState
                headline="No schemes yet"
                body="Nothing is configured. Pick a class, subject, and term, then save a scheme."
              />
            </div>
          ) : (
            <Table>
              <THead>
                <TR>
                  <TH>Class</TH>
                  <TH>Subject</TH>
                  <TH>Term</TH>
                  <TH>Components</TH>
                  <TH>Weight</TH>
                  <TH />
                </TR>
              </THead>
              <TBody>
                {existingSchemes.map((group) => (
                  <TR key={group.key}>
                    <TD>{group.class_level_name}</TD>
                    <TD>{group.subject_name}</TD>
                    <TD>{group.term_name}</TD>
                    <TD style={{ fontFamily: "var(--font-mono)" }}>
                      {group.count}
                    </TD>
                    <TD style={{ fontFamily: "var(--font-mono)" }}>
                      {formatWeight(group.weight)}%
                    </TD>
                    <TD>
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() =>
                          applyScope({
                            subject: group.subject,
                            class_level: group.class_level,
                            term: group.term,
                          })
                        }
                      >
                        Open
                      </Button>
                    </TD>
                  </TR>
                ))}
              </TBody>
            </Table>
          )}
        </CardBody>
      </Card>

      <ConfirmDeleteModal
        open={Boolean(pendingDelete)}
        onClose={() => setPendingDelete(null)}
        onConfirm={() => {
          if (pendingDelete) removeComponent.mutate(pendingDelete.id);
        }}
        title={
          pendingDelete
            ? `Delete ${pendingDelete.name}?`
            : "Delete component?"
        }
        description={
          deleteWouldBreakWeights
            ? `Remaining weights would be ${formatWeight(remainingAfterDelete)}%, not 100%. The API will reject this. Replace the whole scheme instead, or delete the last remaining component.`
            : remainingAfterDelete === 0
              ? "This is the last component. Deleting it clears the scheme for this subject, class, and term."
              : "This removes one component. Remaining weights must still total 100%."
        }
        pending={removeComponent.isPending}
      />

      <Toast
        open={Boolean(toast)}
        onClose={() => setToast(null)}
        message={toast ?? ""}
      />
    </div>
  );
}
