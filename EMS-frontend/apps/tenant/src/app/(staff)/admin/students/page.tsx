"use client";

import { useMemo, useState } from "react";
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
import { ConfirmDeleteModal, Modal } from "@/components/ui/client";
import {
  academicsApi,
  type Guardian,
  type GuardianRelationship,
  type Student,
  type StudentGuardianLinkNested,
} from "@/lib/api/academics";
import { formatApiError } from "@/lib/api/errors";

const RELATIONSHIPS: { value: GuardianRelationship; label: string }[] = [
  { value: "mother", label: "Mother" },
  { value: "father", label: "Father" },
  { value: "guardian", label: "Guardian" },
];

function studentName(s: Pick<Student, "full_name" | "first_name" | "last_name">) {
  return s.full_name || [s.first_name, s.last_name].filter(Boolean).join(" ");
}

function guardianLabel(g: Pick<Guardian, "full_name" | "phone_number" | "user_email">) {
  return g.full_name || g.phone_number || g.user_email || "Guardian";
}

function relationshipLabel(value?: string) {
  return RELATIONSHIPS.find((r) => r.value === value)?.label ?? value ?? "Guardian";
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
  const [guardianName, setGuardianName] = useState("");
  const [guardianPhone, setGuardianPhone] = useState("");
  const [guardianRel, setGuardianRel] = useState<GuardianRelationship>("guardian");
  const [error, setError] = useState<string | null>(null);
  const [created, setCreated] = useState<Student | null>(null);
  const [copiedKey, setCopiedKey] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [editing, setEditing] = useState<Student | null>(null);
  const [editFirstName, setEditFirstName] = useState("");
  const [editLastName, setEditLastName] = useState("");
  const [editDob, setEditDob] = useState("");
  const [editGender, setEditGender] = useState("female");
  const [editAdmission, setEditAdmission] = useState("");
  const [editAdmissionDate, setEditAdmissionDate] = useState("");
  const [editError, setEditError] = useState<string | null>(null);
  const [pendingDelete, setPendingDelete] = useState<Student | null>(null);

  async function copyCode(code: string, key: string) {
    try {
      await navigator.clipboard.writeText(code);
      setError(null);
      setCopiedKey(key);
    } catch {
      setError("Could not copy the linking code.");
    }
  }

  function invalidateStudents() {
    void qc.invalidateQueries({ queryKey: ["academics", "students"] });
    void qc.invalidateQueries({ queryKey: ["academics", "student"] });
    void qc.invalidateQueries({ queryKey: ["academics", "guardians"] });
    void qc.invalidateQueries({ queryKey: ["academics", "guardian-links"] });
  }

  const create = useMutation({
    mutationFn: () => {
      const guardian =
        guardianName.trim() || guardianPhone.trim()
          ? {
              full_name: guardianName.trim(),
              phone_number: guardianPhone.trim(),
              relationship_to_student: guardianRel,
              is_primary_contact: true,
            }
          : undefined;
      return academicsApi.students.create({
        first_name: firstName,
        last_name: lastName,
        date_of_birth: dob,
        gender,
        admission_number: admission,
        admission_date: admissionDate,
        guardian,
      });
    },
    onSuccess: (student) => {
      setFirstName("");
      setLastName("");
      setAdmission("");
      setGuardianName("");
      setGuardianPhone("");
      setGuardianRel("guardian");
      setError(null);
      setCreated(student);
      setCopiedKey(null);
      setSelectedId(student.id);
      invalidateStudents();
    },
    onError: (err) => {
      setError(formatApiError(err, "Create failed"));
    },
  });

  function startEdit(student: Student) {
    setEditing(student);
    setEditFirstName(student.first_name ?? "");
    setEditLastName(student.last_name ?? "");
    setEditDob(student.date_of_birth ?? "");
    setEditGender(student.gender || "female");
    setEditAdmission(student.admission_number ?? "");
    setEditAdmissionDate(student.admission_date ?? "");
    setEditError(null);
  }

  function closeEdit() {
    setEditing(null);
    setEditError(null);
  }

  const updateStudent = useMutation({
    mutationFn: (id: string) =>
      academicsApi.students.update(id, {
        first_name: editFirstName.trim(),
        last_name: editLastName.trim(),
        date_of_birth: editDob,
        gender: editGender,
        admission_number: editAdmission.trim(),
        admission_date: editAdmissionDate,
      }),
    onSuccess: (student) => {
      setCreated((prev) => (prev?.id === student.id ? { ...prev, ...student } : prev));
      closeEdit();
      setError(null);
      invalidateStudents();
    },
    onError: (err) => {
      setEditError(formatApiError(err, "Could not update student"));
    },
  });

  const removeStudent = useMutation({
    mutationFn: (id: string) => academicsApi.students.remove(id),
    onSuccess: (_data, id) => {
      setPendingDelete(null);
      setError(null);
      setCreated((prev) => (prev?.id === id ? null : prev));
      setSelectedId((current) => (current === id ? null : current));
      if (editing?.id === id) closeEdit();
      invalidateStudents();
    },
    onError: (err) => {
      setPendingDelete(null);
      setError(formatApiError(err, "Could not delete student"));
    },
  });

  const regenerate = useMutation({
    mutationFn: (id: string) => academicsApi.students.regenerateLinkingCode(id),
    onSuccess: (student) => {
      setError(null);
      setCreated((prev) => (prev?.id === student.id ? student : prev));
      invalidateStudents();
    },
    onError: (err) => {
      setError(formatApiError(err, "Could not issue a new linking code"));
    },
  });

  return (
    <div className="space-y-6">
      <PageHeader
        title="Students"
        description="Admission numbers, parent contacts, and linking codes"
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
          <div>
            <Label htmlFor="g-name">Guardian name</Label>
            <Input
              id="g-name"
              value={guardianName}
              onChange={(e) => setGuardianName(e.target.value)}
              placeholder="Optional"
            />
          </div>
          <div>
            <Label htmlFor="g-phone">Guardian phone</Label>
            <Input
              id="g-phone"
              value={guardianPhone}
              onChange={(e) => setGuardianPhone(e.target.value)}
              placeholder="Optional"
            />
          </div>
          <div>
            <Label htmlFor="g-rel">Relationship</Label>
            <Select
              id="g-rel"
              value={guardianRel}
              onChange={(e) => setGuardianRel(e.target.value as GuardianRelationship)}
            >
              {RELATIONSHIPS.map((rel) => (
                <option key={rel.value} value={rel.value}>
                  {rel.label}
                </option>
              ))}
            </Select>
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
          ) : (students.data?.length ?? 0) === 0 ? (
            <div className="p-4">
              <EmptyState
                headline="No students yet"
                body="Add a student above. A linking code is issued automatically for the parent."
              />
            </div>
          ) : (
            <Table>
              <THead>
                <TR>
                  <TH>Name</TH>
                  <TH>Admission</TH>
                  <TH>Linking code</TH>
                  <TH>Actions</TH>
                </TR>
              </THead>
              <TBody>
                {(students.data ?? []).map((s) => (
                  <TR
                    key={s.id}
                    className={selectedId === s.id ? "bg-ink/[0.06]" : undefined}
                  >
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
                    <TD>
                      <span className="inline-flex flex-wrap items-center gap-2">
                        <Button
                          variant="ghost"
                          size="sm"
                          disabled={regenerate.isPending}
                          onClick={() => regenerate.mutate(s.id)}
                        >
                          {s.linking_code ? "Reissue" : "Issue new"}
                        </Button>
                        <Button
                          variant={selectedId === s.id ? "secondary" : "ghost"}
                          size="sm"
                          onClick={() =>
                            setSelectedId((current) => (current === s.id ? null : s.id))
                          }
                        >
                          {selectedId === s.id ? "Close" : "Guardians"}
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          disabled={updateStudent.isPending || removeStudent.isPending}
                          onClick={() => startEdit(s)}
                        >
                          Edit
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          disabled={removeStudent.isPending}
                          onClick={() => setPendingDelete(s)}
                        >
                          Delete
                        </Button>
                      </span>
                    </TD>
                  </TR>
                ))}
              </TBody>
            </Table>
          )}
        </CardBody>
      </Card>
      <Modal
        open={Boolean(editing)}
        onClose={closeEdit}
        title={editing ? `Edit ${studentName(editing) || "student"}` : "Edit student"}
        footer={
          <>
            <Button variant="secondary" size="sm" onClick={closeEdit}>
              Cancel
            </Button>
            <Button
              size="sm"
              disabled={
                updateStudent.isPending ||
                !editFirstName.trim() ||
                !editLastName.trim() ||
                !editAdmission.trim() ||
                !editDob ||
                !editAdmissionDate
              }
              onClick={() => {
                if (editing) updateStudent.mutate(editing.id);
              }}
            >
              {updateStudent.isPending ? "Saving…" : "Save"}
            </Button>
          </>
        }
      >
        <div className="grid gap-3">
          <div>
            <Label htmlFor="edit-fn">First name</Label>
            <Input
              id="edit-fn"
              value={editFirstName}
              onChange={(e) => setEditFirstName(e.target.value)}
            />
          </div>
          <div>
            <Label htmlFor="edit-ln">Last name</Label>
            <Input
              id="edit-ln"
              value={editLastName}
              onChange={(e) => setEditLastName(e.target.value)}
            />
          </div>
          <div>
            <Label htmlFor="edit-dob">Date of birth</Label>
            <Input
              id="edit-dob"
              type="date"
              value={editDob}
              onChange={(e) => setEditDob(e.target.value)}
            />
          </div>
          <div>
            <Label htmlFor="edit-gender">Gender</Label>
            <Select
              id="edit-gender"
              value={editGender}
              onChange={(e) => setEditGender(e.target.value)}
            >
              <option value="female">Female</option>
              <option value="male">Male</option>
              <option value="other">Other</option>
            </Select>
          </div>
          <div>
            <Label htmlFor="edit-adm">Admission #</Label>
            <Input
              id="edit-adm"
              value={editAdmission}
              onChange={(e) => setEditAdmission(e.target.value)}
            />
          </div>
          <div>
            <Label htmlFor="edit-adm-date">Admission date</Label>
            <Input
              id="edit-adm-date"
              type="date"
              value={editAdmissionDate}
              onChange={(e) => setEditAdmissionDate(e.target.value)}
            />
          </div>
          {editError ? <p className="text-sm text-danger">{editError}</p> : null}
        </div>
      </Modal>

      <ConfirmDeleteModal
        open={Boolean(pendingDelete)}
        onClose={() => setPendingDelete(null)}
        onConfirm={() => {
          if (pendingDelete) removeStudent.mutate(pendingDelete.id);
        }}
        title={
          pendingDelete
            ? `Delete ${studentName(pendingDelete) || "this student"}?`
            : "Delete student?"
        }
        description="This cannot be undone. Students with invoices or other protected records cannot be deleted."
        pending={removeStudent.isPending}
      />

      {selectedId ? (
        <StudentGuardiansPanel
          studentId={selectedId}
          studentName={studentName(
            students.data?.find((s) => s.id === selectedId) ?? {},
          )}
          linkingCode={
            students.data?.find((s) => s.id === selectedId)?.linking_code ?? null
          }
          onCopyCode={(code) => void copyCode(code, `${selectedId}-panel`)}
          copied={copiedKey === `${selectedId}-panel`}
          onRegenerate={() => regenerate.mutate(selectedId)}
          regenerating={regenerate.isPending}
        />
      ) : null}
    </div>
  );
}

function StudentGuardiansPanel({
  studentId,
  studentName: name,
  linkingCode,
  onCopyCode,
  copied,
  onRegenerate,
  regenerating,
}: {
  studentId: string;
  studentName: string;
  linkingCode: string | null;
  onCopyCode: (code: string) => void;
  copied: boolean;
  onRegenerate: () => void;
  regenerating: boolean;
}) {
  const qc = useQueryClient();
  const [panelError, setPanelError] = useState<string | null>(null);
  const [newName, setNewName] = useState("");
  const [newPhone, setNewPhone] = useState("");
  const [newRel, setNewRel] = useState<GuardianRelationship>("guardian");
  const [newPrimary, setNewPrimary] = useState(false);
  const [existingId, setExistingId] = useState("");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editName, setEditName] = useState("");
  const [editPhone, setEditPhone] = useState("");
  const [editRel, setEditRel] = useState<GuardianRelationship>("guardian");

  const detail = useQuery({
    queryKey: ["academics", "student", studentId],
    queryFn: () => academicsApi.students.get(studentId),
  });
  const guardians = useQuery({
    queryKey: ["academics", "guardians"],
    queryFn: () => academicsApi.guardians.list(),
  });

  const links = detail.data?.guardian_links ?? [];
  const linkedGuardianIds = useMemo(
    () => new Set(links.map((link) => link.guardian)),
    [links],
  );
  const unlinkedGuardians = (guardians.data ?? []).filter(
    (g) => !linkedGuardianIds.has(g.id),
  );

  function invalidate() {
    void qc.invalidateQueries({ queryKey: ["academics", "student", studentId] });
    void qc.invalidateQueries({ queryKey: ["academics", "students"] });
    void qc.invalidateQueries({ queryKey: ["academics", "guardians"] });
    void qc.invalidateQueries({ queryKey: ["academics", "guardian-links"] });
  }

  const addNew = useMutation({
    mutationFn: async () => {
      const guardian = await academicsApi.guardians.create({
        full_name: newName.trim(),
        phone_number: newPhone.trim(),
        relationship_to_student: newRel,
      });
      return academicsApi.guardianLinks.create({
        student: studentId,
        guardian: guardian.id,
        is_primary_contact: newPrimary || links.length === 0,
      });
    },
    onSuccess: () => {
      setNewName("");
      setNewPhone("");
      setNewRel("guardian");
      setNewPrimary(false);
      setPanelError(null);
      invalidate();
    },
    onError: (err) => {
      setPanelError(formatApiError(err, "Could not add guardian"));
    },
  });

  const linkExisting = useMutation({
    mutationFn: () =>
      academicsApi.guardianLinks.create({
        student: studentId,
        guardian: existingId,
        is_primary_contact: links.length === 0,
      }),
    onSuccess: () => {
      setExistingId("");
      setPanelError(null);
      invalidate();
    },
    onError: (err) => {
      setPanelError(formatApiError(err, "Could not link guardian"));
    },
  });

  const unlink = useMutation({
    mutationFn: (linkId: string) => academicsApi.guardianLinks.remove(linkId),
    onSuccess: () => {
      setPanelError(null);
      invalidate();
    },
    onError: (err) => {
      setPanelError(formatApiError(err, "Could not unlink guardian"));
    },
  });

  const setPrimary = useMutation({
    mutationFn: (linkId: string) =>
      academicsApi.guardianLinks.update(linkId, { is_primary_contact: true }),
    onSuccess: () => {
      setPanelError(null);
      invalidate();
    },
    onError: (err) => {
      setPanelError(formatApiError(err, "Could not set primary contact"));
    },
  });

  const saveEdit = useMutation({
    mutationFn: (guardianId: string) =>
      academicsApi.guardians.update(guardianId, {
        full_name: editName.trim(),
        phone_number: editPhone.trim(),
        relationship_to_student: editRel,
      }),
    onSuccess: () => {
      setEditingId(null);
      setPanelError(null);
      invalidate();
    },
    onError: (err) => {
      setPanelError(formatApiError(err, "Could not update guardian"));
    },
  });

  function startEdit(link: StudentGuardianLinkNested) {
    const match = (guardians.data ?? []).find((g) => g.id === link.guardian);
    setEditingId(link.guardian);
    setEditName(match?.full_name || link.guardian_full_name || "");
    setEditPhone(match?.phone_number || link.guardian_phone_number || "");
    setEditRel(
      (match?.relationship_to_student ||
        link.relationship_to_student ||
        "guardian") as GuardianRelationship,
    );
  }

  const code = detail.data?.linking_code ?? linkingCode;
  const busy =
    addNew.isPending ||
    linkExisting.isPending ||
    unlink.isPending ||
    setPrimary.isPending ||
    saveEdit.isPending;

  return (
    <Card>
      <CardHeader>
        <CardTitle>{name ? `Guardians — ${name}` : "Guardians"}</CardTitle>
      </CardHeader>
      <CardBody className="space-y-4">
        <div className="flex flex-wrap items-center gap-3 text-sm">
          <span className="text-ink/70">Linking code</span>
          {code ? (
            <>
              <span className="tracking-wide" style={{ fontFamily: "var(--font-mono)" }}>
                {code}
              </span>
              <Button variant="ghost" size="sm" onClick={() => onCopyCode(code)}>
                {copied ? "Copied" : "Copy"}
              </Button>
            </>
          ) : (
            <span className="text-ink/60">None unused — issue a new code for the parent.</span>
          )}
          <Button
            variant="secondary"
            size="sm"
            disabled={regenerating}
            onClick={onRegenerate}
          >
            {code ? "Reissue code" : "Issue new code"}
          </Button>
        </div>

        {panelError ? <p className="text-sm text-danger">{panelError}</p> : null}

        {detail.isLoading ? (
          <p className="text-sm text-ink/70">Loading guardians…</p>
        ) : links.length === 0 ? (
          <p className="text-sm text-ink/65">No guardians linked yet.</p>
        ) : (
          <Table>
            <THead>
              <TR>
                <TH>Name</TH>
                <TH>Phone</TH>
                <TH>Email</TH>
                <TH>Relationship</TH>
                <TH>Actions</TH>
              </TR>
            </THead>
            <TBody>
              {links.map((link) => (
                <TR key={link.id}>
                  <TD>
                    {editingId === link.guardian ? (
                      <Input
                        value={editName}
                        onChange={(e) => setEditName(e.target.value)}
                        aria-label="Guardian name"
                      />
                    ) : (
                      <span className="inline-flex items-center gap-2">
                        {link.guardian_full_name || "—"}
                        {link.is_primary_contact ? (
                          <Badge variant="info">primary</Badge>
                        ) : null}
                      </span>
                    )}
                  </TD>
                  <TD>
                    {editingId === link.guardian ? (
                      <Input
                        value={editPhone}
                        onChange={(e) => setEditPhone(e.target.value)}
                        aria-label="Guardian phone"
                      />
                    ) : (
                      <span style={{ fontFamily: "var(--font-mono)" }}>
                        {link.guardian_phone_number || "—"}
                      </span>
                    )}
                  </TD>
                  <TD className="text-sm">{link.user_email || "—"}</TD>
                  <TD>
                    {editingId === link.guardian ? (
                      <Select
                        value={editRel}
                        onChange={(e) =>
                          setEditRel(e.target.value as GuardianRelationship)
                        }
                        aria-label="Relationship"
                      >
                        {RELATIONSHIPS.map((rel) => (
                          <option key={rel.value} value={rel.value}>
                            {rel.label}
                          </option>
                        ))}
                      </Select>
                    ) : (
                      relationshipLabel(link.relationship_to_student)
                    )}
                  </TD>
                  <TD>
                    {editingId === link.guardian ? (
                      <span className="inline-flex flex-wrap gap-2">
                        <Button
                          size="sm"
                          disabled={saveEdit.isPending || (!editName.trim() && !editPhone.trim())}
                          onClick={() => saveEdit.mutate(link.guardian)}
                        >
                          Save
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => setEditingId(null)}
                        >
                          Cancel
                        </Button>
                      </span>
                    ) : (
                      <span className="inline-flex flex-wrap gap-2">
                        <Button
                          variant="ghost"
                          size="sm"
                          disabled={busy}
                          onClick={() => startEdit(link)}
                        >
                          Edit
                        </Button>
                        {!link.is_primary_contact ? (
                          <Button
                            variant="ghost"
                            size="sm"
                            disabled={busy}
                            onClick={() => setPrimary.mutate(link.id)}
                          >
                            Set primary
                          </Button>
                        ) : null}
                        <Button
                          variant="ghost"
                          size="sm"
                          disabled={busy}
                          onClick={() => unlink.mutate(link.id)}
                        >
                          Unlink
                        </Button>
                      </span>
                    )}
                  </TD>
                </TR>
              ))}
            </TBody>
          </Table>
        )}

        <div className="grid gap-3 border-t border-ink/15 pt-4 sm:grid-cols-4">
          <div>
            <Label htmlFor="add-g-name">New guardian</Label>
            <Input
              id="add-g-name"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              placeholder="Full name"
            />
          </div>
          <div>
            <Label htmlFor="add-g-phone">Phone</Label>
            <Input
              id="add-g-phone"
              value={newPhone}
              onChange={(e) => setNewPhone(e.target.value)}
              placeholder="Phone"
            />
          </div>
          <div>
            <Label htmlFor="add-g-rel">Relationship</Label>
            <Select
              id="add-g-rel"
              value={newRel}
              onChange={(e) => setNewRel(e.target.value as GuardianRelationship)}
            >
              {RELATIONSHIPS.map((rel) => (
                <option key={rel.value} value={rel.value}>
                  {rel.label}
                </option>
              ))}
            </Select>
          </div>
          <div className="flex items-end gap-3">
            <label className="flex items-center gap-2 text-sm text-ink/80">
              <input
                type="checkbox"
                checked={newPrimary}
                onChange={(e) => setNewPrimary(e.target.checked)}
              />
              Primary
            </label>
            <Button
              size="sm"
              disabled={addNew.isPending || (!newName.trim() && !newPhone.trim())}
              onClick={() => addNew.mutate()}
            >
              Add & link
            </Button>
          </div>
        </div>

        {unlinkedGuardians.length > 0 ? (
          <div className="grid gap-3 sm:grid-cols-4">
            <div className="sm:col-span-3">
              <Label htmlFor="link-existing">Link existing guardian</Label>
              <Select
                id="link-existing"
                value={existingId}
                onChange={(e) => setExistingId(e.target.value)}
              >
                <option value="">Select a guardian</option>
                {unlinkedGuardians.map((g) => (
                  <option key={g.id} value={g.id}>
                    {guardianLabel(g)}
                    {g.phone_number ? ` · ${g.phone_number}` : ""}
                  </option>
                ))}
              </Select>
            </div>
            <div className="flex items-end">
              <Button
                variant="secondary"
                size="sm"
                disabled={linkExisting.isPending || !existingId}
                onClick={() => linkExisting.mutate()}
              >
                Link
              </Button>
            </div>
          </div>
        ) : null}
      </CardBody>
    </Card>
  );
}
