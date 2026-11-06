"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Badge,
  Card,
  CardBody,
  EmptyState,
  Label,
  Money,
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
import { financeApi, type Invoice } from "@/lib/api/finance";

function statusLabel(status?: string): string {
  if (status === "paid") return "Paid";
  if (status === "partially_paid") return "Partially paid";
  if (status === "unpaid") return "Unpaid";
  return status || "—";
}

function statusVariant(status?: string): "success" | "warning" | "info" {
  if (status === "paid") return "success";
  if (status === "partially_paid") return "warning";
  return "info";
}

function moneyAmount(value?: string): number {
  const parsed = Number(value ?? 0);
  return Number.isFinite(parsed) ? parsed : 0;
}

function termLabel(inv: Invoice): string {
  return [inv.session_name, inv.term_name].filter(Boolean).join(" · ") || "—";
}

export default function BursarInvoicesPage() {
  const [termId, setTermId] = useState("");
  const [classLevelId, setClassLevelId] = useState("");
  const filtering = Boolean(termId || classLevelId);

  const allInvoices = useQuery({
    queryKey: ["finance", "invoices"],
    queryFn: () => financeApi.listInvoices(),
  });
  const filtered = useQuery({
    queryKey: ["finance", "invoices", termId, classLevelId],
    queryFn: () =>
      financeApi.listInvoices({
        ...(termId ? { term: termId } : {}),
        ...(classLevelId ? { class_level: classLevelId } : {}),
      }),
    enabled: filtering,
  });
  const classLevels = useQuery({
    queryKey: ["academics", "class-levels"],
    queryFn: () => academicsApi.classLevels.list(),
    retry: false,
  });

  const rows = filtering ? (filtered.data ?? []) : (allInvoices.data ?? []);
  const listLoading = filtering ? filtered.isLoading : allInvoices.isLoading;
  const listError = filtering ? filtered.error : allInvoices.error;

  const termOptions = useMemo(() => {
    const seen = new Map<string, string>();
    for (const inv of allInvoices.data ?? []) {
      if (!inv.term || seen.has(inv.term)) continue;
      seen.set(inv.term, termLabel(inv));
    }
    return [...seen.entries()];
  }, [allInvoices.data]);

  const showClassFilter = (classLevels.data?.length ?? 0) > 0;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Invoices"
        description="Student bills for this school, with what has been paid and what is still due"
      />

      {termOptions.length > 0 || showClassFilter ? (
        <Card>
          <CardBody className="flex flex-wrap items-end gap-3">
            {termOptions.length > 0 ? (
              <div className="min-w-[12rem] flex-1">
                <Label htmlFor="invoice-term">Term</Label>
                <Select
                  id="invoice-term"
                  value={termId}
                  onChange={(e) => setTermId(e.target.value)}
                >
                  <option value="">All terms</option>
                  {termOptions.map(([id, label]) => (
                    <option key={id} value={id}>
                      {label}
                    </option>
                  ))}
                </Select>
              </div>
            ) : null}
            {showClassFilter ? (
              <div className="min-w-[12rem] flex-1">
                <Label htmlFor="invoice-class">Class</Label>
                <Select
                  id="invoice-class"
                  value={classLevelId}
                  onChange={(e) => setClassLevelId(e.target.value)}
                >
                  <option value="">All classes</option>
                  {(classLevels.data ?? []).map((level) => (
                    <option key={level.id} value={level.id}>
                      {level.name}
                    </option>
                  ))}
                </Select>
              </div>
            ) : null}
          </CardBody>
        </Card>
      ) : null}

      <Card>
        <CardBody className="p-0">
          {listLoading ? (
            <p className="p-4 text-sm text-ink/70">Loading invoices…</p>
          ) : listError ? (
            <p className="p-4 text-sm text-danger">
              {listError instanceof Error ? listError.message : "Failed to load invoices"}
            </p>
          ) : rows.length === 0 ? (
            <div className="p-4">
              <EmptyState
                headline={filtering ? "No matching invoices" : "No invoices yet"}
                body={
                  filtering
                    ? "Try another term or class, or generate invoices for this class and term."
                    : "Generate invoices for a class and term. They will show up in this list."
                }
              />
            </div>
          ) : (
            <Table>
              <THead>
                <TR>
                  <TH>Student</TH>
                  <TH>Term</TH>
                  <TH className="text-right">Amount</TH>
                  <TH className="text-right">Paid</TH>
                  <TH className="text-right">Balance</TH>
                  <TH>Status</TH>
                  <TH />
                </TR>
              </THead>
              <TBody>
                {rows.map((inv) => {
                  const balance = moneyAmount(inv.outstanding_amount);
                  return (
                    <TR key={inv.id}>
                      <TD>
                        <div>{inv.student_name || "Student"}</div>
                        {inv.admission_number ? (
                          <div
                            className="text-xs text-ink/70"
                            style={{ fontFamily: "var(--font-mono)" }}
                          >
                            {inv.admission_number}
                          </div>
                        ) : null}
                      </TD>
                      <TD>{termLabel(inv)}</TD>
                      <TD className="text-right">
                        <Money amount={moneyAmount(inv.total_amount)} />
                      </TD>
                      <TD className="text-right">
                        <Money amount={moneyAmount(inv.amount_paid)} />
                      </TD>
                      <TD className="text-right">
                        <Money amount={balance} />
                      </TD>
                      <TD>
                        <Badge variant={statusVariant(inv.status)}>
                          {statusLabel(inv.status)}
                        </Badge>
                      </TD>
                      <TD className="text-right">
                        {balance > 0 ? (
                          <Link
                            href={`/bursar/payments/manual?invoice=${inv.id}`}
                            className="text-sm font-medium text-ink underline"
                          >
                            Record
                          </Link>
                        ) : null}
                      </TD>
                    </TR>
                  );
                })}
              </TBody>
            </Table>
          )}
        </CardBody>
      </Card>
    </div>
  );
}
