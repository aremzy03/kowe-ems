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
import { academicsApi } from "@/lib/api/academics";
import { financeApi } from "@/lib/api/finance";
import { ApiRequestError } from "@/lib/api/client";
import { mapDrfErrors } from "@/lib/api/errors";

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
      setError(
        err instanceof ApiRequestError
          ? mapDrfErrors(err.data).form ?? err.message
          : "Failed",
      );
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
