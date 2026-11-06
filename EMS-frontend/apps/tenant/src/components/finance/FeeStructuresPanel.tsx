"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Button,
  Card,
  CardBody,
  EmptyState,
  Input,
  Label,
  Money,
  Select,
  Table,
  TBody,
  TD,
  TH,
  THead,
  TR,
} from "@/components/ui";
import { ConfirmDeleteModal, Modal } from "@/components/ui/client";
import { academicsApi } from "@/lib/api/academics";
import { financeApi, type FeeStructure } from "@/lib/api/finance";
import { formatApiError } from "@/lib/api/errors";

function moneyAmount(value?: string): number {
  const parsed = Number(value ?? 0);
  return Number.isFinite(parsed) ? parsed : 0;
}

function termOptionLabel(
  term: { id: string; name: string; session: string; session_name?: string },
  sessions: { id: string; name: string }[],
): string {
  const sessionName =
    term.session_name ||
    sessions.find((s) => s.id === term.session)?.name ||
    "Session";
  return `${sessionName} · ${term.name}`;
}

type FeeStructuresPanelProps = {
  /** When false, omit the outer section heading (page already has PageHeader). */
  showHeading?: boolean;
};

/** Create + list fee structures for admin or bursar. */
export function FeeStructuresPanel({ showHeading = true }: FeeStructuresPanelProps) {
  const qc = useQueryClient();
  const list = useQuery({
    queryKey: ["finance", "fee-structures"],
    queryFn: () => financeApi.feeStructures.list(),
  });
  const classLevels = useQuery({
    queryKey: ["academics", "class-levels"],
    queryFn: () => academicsApi.classLevels.list(),
  });
  const terms = useQuery({
    queryKey: ["academics", "terms"],
    queryFn: () => academicsApi.terms.list(),
  });
  const sessions = useQuery({
    queryKey: ["academics", "sessions"],
    queryFn: () => academicsApi.sessions.list(),
  });

  const [name, setName] = useState("");
  const [amount, setAmount] = useState("");
  const [classLevel, setClassLevel] = useState("");
  const [term, setTerm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState<FeeStructure | null>(null);
  const [editName, setEditName] = useState("");
  const [editAmount, setEditAmount] = useState("");
  const [editClassLevel, setEditClassLevel] = useState("");
  const [editTerm, setEditTerm] = useState("");
  const [editError, setEditError] = useState<string | null>(null);
  const [pendingDelete, setPendingDelete] = useState<FeeStructure | null>(null);

  const create = useMutation({
    mutationFn: () =>
      financeApi.feeStructures.create({
        name: name.trim(),
        amount,
        class_level: classLevel,
        term,
      }),
    onSuccess: () => {
      setName("");
      setAmount("");
      setClassLevel("");
      setTerm("");
      setError(null);
      void qc.invalidateQueries({ queryKey: ["finance", "fee-structures"] });
    },
    onError: (err) => {
      setError(formatApiError(err, "Could not create fee structure"));
    },
  });

  function startEdit(fs: FeeStructure) {
    setEditing(fs);
    setEditName(fs.name);
    setEditAmount(fs.amount);
    setEditClassLevel(fs.class_level);
    setEditTerm(fs.term);
    setEditError(null);
  }

  function closeEdit() {
    setEditing(null);
    setEditError(null);
  }

  const update = useMutation({
    mutationFn: (id: string) =>
      financeApi.feeStructures.update(id, {
        name: editName.trim(),
        amount: editAmount,
        class_level: editClassLevel,
        term: editTerm,
      }),
    onSuccess: () => {
      closeEdit();
      setError(null);
      void qc.invalidateQueries({ queryKey: ["finance", "fee-structures"] });
    },
    onError: (err) => {
      setEditError(formatApiError(err, "Could not update fee structure"));
    },
  });

  const remove = useMutation({
    mutationFn: (id: string) => financeApi.feeStructures.remove(id),
    onSuccess: () => {
      setPendingDelete(null);
      setError(null);
      void qc.invalidateQueries({ queryKey: ["finance", "fee-structures"] });
    },
    onError: (err) => {
      setPendingDelete(null);
      setError(formatApiError(err, "Could not delete fee structure"));
    },
  });

  const canCreate =
    Boolean(name.trim()) &&
    Boolean(amount) &&
    Boolean(classLevel) &&
    Boolean(term) &&
    !create.isPending;

  const catalogsLoading =
    classLevels.isLoading || terms.isLoading || sessions.isLoading;

  return (
    <div className="space-y-4">
      {showHeading ? (
        <h2
          className="text-lg font-bold tracking-tight"
          style={{ fontFamily: "var(--font-heading)" }}
        >
          Fee structures
        </h2>
      ) : null}
      {error ? <p className="text-sm text-danger">{error}</p> : null}
      <Card>
        <CardBody className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <div>
            <Label htmlFor="fs-name">Name</Label>
            <Input
              id="fs-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Tuition"
            />
          </div>
          <div>
            <Label htmlFor="fs-amount">Amount (₦)</Label>
            <Input
              id="fs-amount"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              placeholder="150000.00"
              inputMode="decimal"
              style={{ fontFamily: "var(--font-mono)" }}
            />
          </div>
          <div>
            <Label htmlFor="fs-class">Class level</Label>
            <Select
              id="fs-class"
              value={classLevel}
              disabled={catalogsLoading}
              onChange={(e) => setClassLevel(e.target.value)}
            >
              <option value="">
                {classLevels.isLoading ? "Loading…" : "Choose class"}
              </option>
              {(classLevels.data ?? []).map((level) => (
                <option key={level.id} value={level.id}>
                  {level.name}
                </option>
              ))}
            </Select>
          </div>
          <div>
            <Label htmlFor="fs-term">Term</Label>
            <Select
              id="fs-term"
              value={term}
              disabled={catalogsLoading}
              onChange={(e) => setTerm(e.target.value)}
            >
              <option value="">
                {terms.isLoading ? "Loading…" : "Choose term"}
              </option>
              {(terms.data ?? []).map((t) => (
                <option key={t.id} value={t.id}>
                  {termOptionLabel(t, sessions.data ?? [])}
                </option>
              ))}
            </Select>
          </div>
          <div className="sm:col-span-2 lg:col-span-4">
            <Button size="sm" disabled={!canCreate} onClick={() => create.mutate()}>
              {create.isPending ? "Creating…" : "Create fee structure"}
            </Button>
          </div>
        </CardBody>
      </Card>
      <Card>
        <CardBody className="p-0">
          {list.isLoading ? (
            <p className="p-4 text-sm text-ink/70">Loading…</p>
          ) : (list.data?.length ?? 0) === 0 ? (
            <div className="p-4">
              <EmptyState
                headline="No fee structures"
                body="Create a structure to begin invoicing."
              />
            </div>
          ) : (
            <Table>
              <THead>
                <TR>
                  <TH>Name</TH>
                  <TH>Class</TH>
                  <TH>Term</TH>
                  <TH>Amount</TH>
                  <TH>Actions</TH>
                </TR>
              </THead>
              <TBody>
                {(list.data ?? []).map((fs) => (
                  <TR key={fs.id}>
                    <TD>{fs.name}</TD>
                    <TD>{fs.class_level_name ?? "—"}</TD>
                    <TD>
                      {[fs.session_name, fs.term_name]
                        .filter(Boolean)
                        .join(" · ") || "—"}
                    </TD>
                    <TD style={{ fontFamily: "var(--font-mono)" }}>
                      <Money amount={moneyAmount(fs.amount)} />
                    </TD>
                    <TD>
                      <span className="inline-flex flex-wrap gap-2">
                        <Button
                          variant="ghost"
                          size="sm"
                          disabled={update.isPending || remove.isPending}
                          onClick={() => startEdit(fs)}
                        >
                          Edit
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          disabled={remove.isPending}
                          onClick={() => setPendingDelete(fs)}
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
        title={editing ? `Edit ${editing.name}` : "Edit fee structure"}
        footer={
          <>
            <Button variant="secondary" size="sm" onClick={closeEdit}>
              Cancel
            </Button>
            <Button
              size="sm"
              disabled={
                update.isPending ||
                !editName.trim() ||
                !editAmount ||
                !editClassLevel ||
                !editTerm
              }
              onClick={() => {
                if (editing) update.mutate(editing.id);
              }}
            >
              {update.isPending ? "Saving…" : "Save"}
            </Button>
          </>
        }
      >
        <div className="grid gap-3">
          <div>
            <Label htmlFor="edit-fs-name">Name</Label>
            <Input
              id="edit-fs-name"
              value={editName}
              onChange={(e) => setEditName(e.target.value)}
            />
          </div>
          <div>
            <Label htmlFor="edit-fs-amount">Amount (₦)</Label>
            <Input
              id="edit-fs-amount"
              value={editAmount}
              onChange={(e) => setEditAmount(e.target.value)}
              inputMode="decimal"
              style={{ fontFamily: "var(--font-mono)" }}
            />
          </div>
          <div>
            <Label htmlFor="edit-fs-class">Class level</Label>
            <Select
              id="edit-fs-class"
              value={editClassLevel}
              onChange={(e) => setEditClassLevel(e.target.value)}
            >
              <option value="">Choose class</option>
              {(classLevels.data ?? []).map((level) => (
                <option key={level.id} value={level.id}>
                  {level.name}
                </option>
              ))}
            </Select>
          </div>
          <div>
            <Label htmlFor="edit-fs-term">Term</Label>
            <Select
              id="edit-fs-term"
              value={editTerm}
              onChange={(e) => setEditTerm(e.target.value)}
            >
              <option value="">Choose term</option>
              {(terms.data ?? []).map((t) => (
                <option key={t.id} value={t.id}>
                  {termOptionLabel(t, sessions.data ?? [])}
                </option>
              ))}
            </Select>
          </div>
          {editError ? <p className="text-sm text-danger">{editError}</p> : null}
        </div>
      </Modal>

      <ConfirmDeleteModal
        open={Boolean(pendingDelete)}
        onClose={() => setPendingDelete(null)}
        onConfirm={() => {
          if (pendingDelete) remove.mutate(pendingDelete.id);
        }}
        title={
          pendingDelete
            ? `Delete ${pendingDelete.name}?`
            : "Delete fee structure?"
        }
        description="Fee structures referenced by issued invoices cannot be deleted."
        pending={remove.isPending}
      />
    </div>
  );
}
